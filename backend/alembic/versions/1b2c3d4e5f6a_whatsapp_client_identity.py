"""Canal WhatsApp client : identifiant BSUID et nom affiché du compte.

- `channel_identities.external_id` passe de 64 à 160 caractères : le BSUID de
  Meta (code pays, un point, jusqu'à 128 caractères) n'y tenait pas.
- `accounts.display_name` : nom choisi par un client WhatsApp, qui n'a pas de
  profil historique dans `bot_users`.

Aucune donnée existante n'est modifiée. Le retour arrière refuse de raccourcir
la colonne si un identifiant plus long que 64 caractères existe déjà : il
échouerait au milieu, ou tronquerait une identité.

Revision ID: 1b2c3d4e5f6a
Revises: b7c8d9e0f1a2
Create Date: 2026-11-07
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "1b2c3d4e5f6a"
down_revision: Union[str, Sequence[str], None] = "b7c8d9e0f1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "channel_identities",
        "external_id",
        existing_type=sa.String(length=64),
        type_=sa.String(length=160),
        existing_nullable=False,
    )
    op.add_column("accounts", sa.Column("display_name", sa.String(length=100), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    too_long = bind.execute(
        sa.text("SELECT COUNT(*) FROM channel_identities WHERE length(external_id) > 64")
    ).scalar_one()
    if too_long:
        raise RuntimeError(
            f"{too_long} identité(s) de canal dépassent 64 caractères (WhatsApp) : "
            "retour arrière refusé pour ne rien tronquer"
        )
    op.drop_column("accounts", "display_name")
    op.alter_column(
        "channel_identities",
        "external_id",
        existing_type=sa.String(length=160),
        type_=sa.String(length=64),
        existing_nullable=False,
    )
