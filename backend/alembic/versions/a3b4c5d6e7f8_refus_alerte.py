"""Refus d'une alerte de mission enregistré sur l'alerte

`mission_alerts.declined_at` : le prestataire a répondu « pas disponible » à
cette alerte. Posé une seule fois, il rend le refus idempotent : un même
appui rejoué ne compte jamais deux refus.

Revision ID: a3b4c5d6e7f8
Revises: f2a3b4c5d6e7
Create Date: 2026-11-13
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "a3b4c5d6e7f8"
down_revision: Union[str, Sequence[str], None] = "f2a3b4c5d6e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("mission_alerts", sa.Column("declined_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("mission_alerts", "declined_at")
