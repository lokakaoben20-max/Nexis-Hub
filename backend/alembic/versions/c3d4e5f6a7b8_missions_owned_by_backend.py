"""Missions créées par le backend

- `bot_missions.mission_id` : numéro attribué par le backend (séquence), plus
  par le canal. La séquence repart après le plus grand numéro existant.
- `bot_missions.creation_key` : clé d'idempotence de la demande de création,
  unique par compte client.
- `mission_media` : photos et notes vocales, rangées avec leur canal.
- `mission_alerts` : prestataires prévenus d'une mission.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-11-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SEQUENCE = "bot_missions_mission_id_seq"


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(f"CREATE SEQUENCE {SEQUENCE} OWNED BY bot_missions.mission_id")
        op.execute(
            f"SELECT setval('{SEQUENCE}', COALESCE((SELECT MAX(mission_id) FROM bot_missions), 0) + 1, false)"
        )
        op.execute(f"ALTER TABLE bot_missions ALTER COLUMN mission_id SET DEFAULT nextval('{SEQUENCE}')")

    op.add_column("bot_missions", sa.Column("creation_key", sa.String(length=64), nullable=True))
    op.create_unique_constraint(
        "uq_bot_missions_client_creation_key", "bot_missions", ["client_account_id", "creation_key"]
    )

    op.create_table(
        "mission_media",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("mission_id", sa.Integer(), sa.ForeignKey("bot_missions.mission_id"), nullable=False),
        sa.Column("channel", sa.String(length=20), nullable=False),
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
    )
    op.create_index("ix_mission_media_mission_id", "mission_media", ["mission_id"])

    op.create_table(
        "mission_alerts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("mission_id", sa.Integer(), sa.ForeignKey("bot_missions.mission_id"), nullable=False),
        sa.Column("provider_account_id", sa.Integer(), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("alerted_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("mission_id", "provider_account_id", name="uq_mission_alerts_mission_provider"),
    )
    op.create_index("ix_mission_alerts_mission_id", "mission_alerts", ["mission_id"])
    op.create_index("ix_mission_alerts_provider_account_id", "mission_alerts", ["provider_account_id"])


def downgrade() -> None:
    op.drop_index("ix_mission_alerts_provider_account_id", table_name="mission_alerts")
    op.drop_index("ix_mission_alerts_mission_id", table_name="mission_alerts")
    op.drop_table("mission_alerts")
    op.drop_index("ix_mission_media_mission_id", table_name="mission_media")
    op.drop_table("mission_media")
    op.drop_constraint("uq_bot_missions_client_creation_key", "bot_missions", type_="unique")
    op.drop_column("bot_missions", "creation_key")
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TABLE bot_missions ALTER COLUMN mission_id DROP DEFAULT")
        op.execute(f"DROP SEQUENCE {SEQUENCE}")
