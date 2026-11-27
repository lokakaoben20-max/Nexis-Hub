"""Numéros de retrait enregistrés.

Préalable des comptes entreprises, utile à tous : un retrait ne part plus
vers un numéro saisi au moment du retrait, mais vers un des numéros que la
personne a enregistrés (`payout_destinations`, 4 au plus, sans contrôle du
nom du titulaire). Un numéro ajouté alors que le compte en a déjà eu un
attend 72 h (`usable_after`).

`payouts.destination_id` : numéro choisi (vide pour les retraits d'avant
cette migration, qui gardent leur numéro recopié).

Aucun numéro n'est créé à partir des numéros de profil : la personne choisit
elle-même ceux qui reçoivent son argent.

Retour arrière refusé dès qu'un retrait désigne un numéro enregistré : on ne
perd jamais ce lien.

Revision ID: c6d7e8f9a0b1
Revises: b5c6d7e8f9a0
Create Date: 2026-11-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c6d7e8f9a0b1"
down_revision: Union[str, Sequence[str], None] = "b5c6d7e8f9a0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ACTIVE = "status = 'active'"


def upgrade() -> None:
    op.create_table(
        "payout_destinations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("operator", sa.String(20), nullable=False),
        sa.Column("phone", sa.String(32), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("usable_after", sa.DateTime(), nullable=True),
        sa.Column("removed_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("status IN ('active', 'removed')", name="ck_payout_destinations_status"),
        sa.CheckConstraint("kind IN ('mobile_money')", name="ck_payout_destinations_kind"),
        sa.CheckConstraint(
            "(status = 'active' AND removed_at IS NULL) OR (status = 'removed' AND removed_at IS NOT NULL)",
            name="ck_payout_destinations_removed",
        ),
    )
    op.create_index("ix_payout_destinations_account_id", "payout_destinations", ["account_id"])
    op.create_index(
        "uq_payout_destinations_active",
        "payout_destinations",
        ["account_id", "operator", "phone"],
        unique=True,
        postgresql_where=sa.text(ACTIVE),
        sqlite_where=sa.text(ACTIVE),
    )
    with op.batch_alter_table("payouts") as batch:
        batch.add_column(sa.Column("destination_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_payouts_destination_id_payout_destinations", "payout_destinations", ["destination_id"], ["id"]
        )
        batch.create_index("ix_payouts_destination_id", ["destination_id"])


def downgrade() -> None:
    linked = op.get_bind().execute(sa.text("SELECT count(*) FROM payouts WHERE destination_id IS NOT NULL")).scalar()
    if linked:
        raise RuntimeError(
            f"{linked} retrait(s) liés à un numéro enregistré : retour arrière impossible sans perdre ce lien."
        )
    with op.batch_alter_table("payouts") as batch:
        batch.drop_index("ix_payouts_destination_id")
        batch.drop_constraint("fk_payouts_destination_id_payout_destinations", type_="foreignkey")
        batch.drop_column("destination_id")
    op.drop_index("uq_payout_destinations_active", table_name="payout_destinations")
    op.drop_index("ix_payout_destinations_account_id", table_name="payout_destinations")
    op.drop_table("payout_destinations")
