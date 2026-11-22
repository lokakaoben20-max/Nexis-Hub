"""Mobile Money : notre référence unique, envois de versement comptés

Avant de brancher un vrai agrégateur (SerdiPay, choisi le 2026-11-19) :

- `payment_intents.reference` et `payouts.reference` : notre référence,
  unique dans toute l'histoire de Nexis Hub, envoyée à l'agrégateur, qui s'en
  sert pour le statut et refuse un second ordre qui la porte. Elle remplace
  l'identifiant numérique de la ligne, qui se répète d'une base à l'autre
  (production, test, poste de développement).
- `payouts.last_sent_at` et `payouts.send_count` : un versement que
  l'agrégateur ne connaît pas est renvoyé (même référence) après un délai,
  un nombre limité de fois.

Lignes existantes : elles n'ont jamais touché un vrai agrégateur (paiement
simulé uniquement). Chacune reçoit une référence neuve ; un retrait déjà
envoyé compte un envoi, à l'heure de sa dernière mise à jour.

Revision ID: e7f8a9b0c1d2
Revises: d5e6f7a8b9c0
Create Date: 2026-11-19
"""
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "e7f8a9b0c1d2"
down_revision: Union[str, Sequence[str], None] = "d5e6f7a8b9c0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SENT_PAYOUT_STATUSES = ("processing", "succeeded", "failed")


def _fill_references(table: str, prefix: str) -> None:
    connection = op.get_bind()
    ids = connection.execute(sa.text(f"SELECT id FROM {table} WHERE reference IS NULL")).scalars().all()
    for row_id in ids:
        connection.execute(
            sa.text(f"UPDATE {table} SET reference = :reference WHERE id = :id"),
            {"reference": f"{prefix}{uuid.uuid4().hex.upper()}", "id": row_id},
        )


def upgrade() -> None:
    with op.batch_alter_table("payment_intents") as batch:
        batch.add_column(sa.Column("reference", sa.String(length=40), nullable=True))
    with op.batch_alter_table("payouts") as batch:
        batch.add_column(sa.Column("reference", sa.String(length=40), nullable=True))
        batch.add_column(sa.Column("last_sent_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("send_count", sa.Integer(), nullable=False, server_default="0"))

    _fill_references("payment_intents", "NXI")
    _fill_references("payouts", "NXO")
    op.get_bind().execute(
        sa.text("UPDATE payouts SET send_count = 1, last_sent_at = updated_at WHERE status IN :statuses").bindparams(
            sa.bindparam("statuses", expanding=True)
        ),
        {"statuses": list(SENT_PAYOUT_STATUSES)},
    )

    with op.batch_alter_table("payment_intents") as batch:
        batch.alter_column("reference", existing_type=sa.String(length=40), nullable=False)
        batch.create_unique_constraint("uq_payment_intents_reference", ["reference"])
    with op.batch_alter_table("payouts") as batch:
        batch.alter_column("reference", existing_type=sa.String(length=40), nullable=False)
        batch.create_unique_constraint("uq_payouts_reference", ["reference"])


def downgrade() -> None:
    with op.batch_alter_table("payouts") as batch:
        batch.drop_constraint("uq_payouts_reference", type_="unique")
        batch.drop_column("send_count")
        batch.drop_column("last_sent_at")
        batch.drop_column("reference")
    with op.batch_alter_table("payment_intents") as batch:
        batch.drop_constraint("uq_payment_intents_reference", type_="unique")
        batch.drop_column("reference")
