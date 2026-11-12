"""Index sur le statut des devis

Le modèle déclare `bot_quotes.status` indexé (lecture des devis en attente
d'une mission), mais aucune migration ne créait l'index : une base montée par
Alembic, comme la production, ne l'avait pas. Trouvé par `alembic check`, que
la CI lance désormais à chaque modification.

Migration additive : l'ancien code tourne sur le nouveau schéma.

Revision ID: c8d9e0f1a2b3
Revises: 1b2c3d4e5f6a
Create Date: 2026-11-07
"""
from typing import Sequence, Union

from alembic import op


revision: str = "c8d9e0f1a2b3"
down_revision: Union[str, Sequence[str], None] = "1b2c3d4e5f6a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(op.f("ix_bot_quotes_status"), "bot_quotes", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_bot_quotes_status"), table_name="bot_quotes")
