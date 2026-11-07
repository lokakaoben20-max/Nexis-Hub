"""Lieu exact de la mission

- `bot_missions.destination_latitude`, `destination_longitude` : point exact
  où le service est rendu (degrés décimaux, 6 décimales).
- `bot_missions.destination_landmark` : repère écrit par le client (à
  Kinshasa, l'adresse seule ne suffit pas).

Les trois sont vides pour les missions créées avant cette étape, et toujours
remplis ensemble ensuite (contrainte `ck_bot_missions_destination_complete`).
Le lieu n'est jamais renvoyé avec la mission : il a sa propre route, réservée
au client, à l'admin et au prestataire d'une mission payée
(CONCEPTION_MISSIONS.md, « Lieu exact de la mission »).

Revision ID: b7c8d9e0f1a2
Revises: 0a1b2c3d4e5f
Create Date: 2026-11-07
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b7c8d9e0f1a2"
down_revision: Union[str, Sequence[str], None] = "0a1b2c3d4e5f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CHECK = "ck_bot_missions_destination_complete"
CHECK_SQL = (
    "(destination_latitude IS NULL AND destination_longitude IS NULL AND destination_landmark IS NULL)"
    " OR (destination_latitude IS NOT NULL AND destination_longitude IS NOT NULL AND destination_landmark IS NOT NULL)"
)


def upgrade() -> None:
    op.add_column("bot_missions", sa.Column("destination_latitude", sa.Float(), nullable=True))
    op.add_column("bot_missions", sa.Column("destination_longitude", sa.Float(), nullable=True))
    op.add_column("bot_missions", sa.Column("destination_landmark", sa.String(length=300), nullable=True))
    op.create_check_constraint(CHECK, "bot_missions", CHECK_SQL)


def downgrade() -> None:
    op.drop_constraint(CHECK, "bot_missions", type_="check")
    op.drop_column("bot_missions", "destination_landmark")
    op.drop_column("bot_missions", "destination_longitude")
    op.drop_column("bot_missions", "destination_latitude")
