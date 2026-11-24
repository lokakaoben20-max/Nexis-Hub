"""Mise en file d'envoi des alertes des missions créées depuis l'app."""

import sqlalchemy as sa
from alembic import op

revision = "b0c1d2e3f4a5"
down_revision = "a9b0c1d2e3f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("mission_alerts", sa.Column("delivery_due_at", sa.DateTime(), nullable=True))
    op.create_index("ix_mission_alerts_delivery_due_at", "mission_alerts", ["delivery_due_at"])


def downgrade() -> None:
    op.drop_index("ix_mission_alerts_delivery_due_at", table_name="mission_alerts")
    op.drop_column("mission_alerts", "delivery_due_at")
