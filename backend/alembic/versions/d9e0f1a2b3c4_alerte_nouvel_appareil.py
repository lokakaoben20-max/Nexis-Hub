"""Alerte « Nouvel appareil » en boîte d'envoi

L'alerte Telegram envoyée quand un téléphone est ajouté à un compte existant
partait par une tâche Celery lancée après la connexion : si le courtier était
indisponible, elle était perdue. Elle est désormais posée sur le téléphone
(`alert_due_at`) dans la même transaction que sa création, et la tâche
planifiée `alertes-nouvel-appareil` l'envoie et réessaie.

Migration additive : les téléphones existants n'ont aucune alerte en attente
(`alert_due_at` NULL), l'ancien code tourne sur le nouveau schéma.

Revision ID: d9e0f1a2b3c4
Revises: c8d9e0f1a2b3
Create Date: 2026-11-12
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "d9e0f1a2b3c4"
down_revision: Union[str, Sequence[str], None] = "c8d9e0f1a2b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("devices") as batch:
        batch.add_column(sa.Column("alert_due_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("alert_sent_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("alert_attempts", sa.Integer(), server_default="0", nullable=False))
    op.create_index(op.f("ix_devices_alert_due_at"), "devices", ["alert_due_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_devices_alert_due_at"), table_name="devices")
    with op.batch_alter_table("devices") as batch:
        batch.drop_column("alert_attempts")
        batch.drop_column("alert_sent_at")
        batch.drop_column("alert_due_at")
