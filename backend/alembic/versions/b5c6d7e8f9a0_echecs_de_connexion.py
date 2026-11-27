"""Codes de connexion faux, par numéro (étape 8 WhatsApp, seconde partie).

`login_failures` : un code faux par ligne, pour le numéro de la demande,
tous canaux confondus. 5 codes faux en 10 minutes bloquent le numéro
15 minutes. Table nouvelle, en ajout seul ; le retour arrière la supprime
(elle ne sert qu'à un blocage de quelques minutes).

Revision ID: b5c6d7e8f9a0
Revises: a4b5c6d7e8f9
Create Date: 2026-11-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b5c6d7e8f9a0"
down_revision: Union[str, Sequence[str], None] = "a4b5c6d7e8f9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "login_failures",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("phone_e164", sa.String(length=32), nullable=False),
        sa.Column("failed_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_login_failures_phone_failed", "login_failures", ["phone_e164", "failed_at"])


def downgrade() -> None:
    op.drop_index("ix_login_failures_phone_failed", table_name="login_failures")
    op.drop_table("login_failures")
