"""Notifications fiables : boîte d'envoi en base (étape 3 WhatsApp).

Nouvelle table `notifications` (backend/app/notifications.py), écrite dans la
transaction de chaque événement. L'alerte « Nouvel appareil », qui avait sa
propre boîte d'envoi sur le téléphone (`devices.alert_due_at`), passe par
cette table comme toutes les autres :

1. les alertes encore à envoyer deviennent des notifications `pending`, avec
   le même contenu (appareil, date et heure de Kinshasa, bouton « Ce n'est
   pas moi ») ;
2. les trois colonnes de l'ancienne boîte d'envoi sont supprimées : il n'y a
   plus qu'une seule source pour savoir si une alerte est partie.

Revision ID: b0c1d2e3f4a5
Revises: a9b0c1d2e3f4
Create Date: 2026-11-22
"""

from datetime import datetime, timedelta
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b0c1d2e3f4a5"
down_revision: Union[str, Sequence[str], None] = "a9b0c1d2e3f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

KINSHASA_OFFSET = timedelta(hours=1)


def _notifications_table() -> sa.Table:
    return sa.table(
        "notifications",
        sa.column("event_key", sa.String),
        sa.column("recipient_account_id", sa.Integer),
        sa.column("channel", sa.String),
        sa.column("message_key", sa.String),
        sa.column("params", sa.JSON),
        sa.column("buttons", sa.JSON),
        sa.column("status", sa.String),
        sa.column("attempts", sa.Integer),
        sa.column("uncertain_count", sa.Integer),
        sa.column("created_at", sa.DateTime),
        sa.column("next_attempt_at", sa.DateTime),
        sa.column("last_error", sa.String),
    )


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_key", sa.String(length=120), nullable=False),
        sa.Column("recipient_account_id", sa.Integer(), nullable=False),
        sa.Column("channel", sa.String(length=16), nullable=True),
        sa.Column("message_key", sa.String(length=80), nullable=False),
        sa.Column("params", sa.JSON(), nullable=False),
        sa.Column("buttons", sa.JSON(), nullable=False),
        sa.Column("media", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=12), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("uncertain_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(), nullable=True),
        sa.Column("claimed_at", sa.DateTime(), nullable=True),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("provider_message_id", sa.String(length=200), nullable=True),
        sa.Column("last_error", sa.String(length=200), nullable=True),
        sa.ForeignKeyConstraint(["recipient_account_id"], ["accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_key", "recipient_account_id", name="uq_notifications_event_recipient"),
        sa.CheckConstraint(
            "status IN ('pending', 'sending', 'sent', 'uncertain', 'failed')", name="ck_notifications_status"
        ),
        sa.CheckConstraint(
            "channel IS NULL OR channel IN ('telegram', 'whatsapp')", name="ck_notifications_channel"
        ),
        sa.CheckConstraint("attempts >= 0 AND uncertain_count >= 0", name="ck_notifications_counters"),
        sa.CheckConstraint("(status = 'sent') = (sent_at IS NOT NULL)", name="ck_notifications_sent_at"),
    )
    op.create_index("ix_notifications_due", "notifications", ["status", "next_attempt_at"])
    op.create_index(op.f("ix_notifications_recipient_account_id"), "notifications", ["recipient_account_id"])

    connection = op.get_bind()
    pending = connection.execute(
        sa.text("SELECT id, account_id, label, created_at FROM devices WHERE alert_due_at IS NOT NULL ORDER BY id")
    ).all()
    now = datetime.utcnow()
    rows = []
    for device_id, account_id, label, created_at in pending:
        channels = {
            channel
            for (channel,) in connection.execute(
                sa.text(
                    "SELECT channel FROM channel_identities WHERE account_id = :account_id "
                    "AND channel IN ('telegram', 'whatsapp')"
                ),
                {"account_id": account_id},
            )
        }
        channel = "telegram" if "telegram" in channels else ("whatsapp" if "whatsapp" in channels else None)
        local = created_at + KINSHASA_OFFSET
        rows.append(
            {
                "event_key": f"new_device:{device_id}",
                "recipient_account_id": account_id,
                "channel": channel,
                "message_key": "app_new_device_alert",
                "params": {
                    "device": label if label else {"$message": "app_device_unnamed"},
                    "date": local.strftime("%d/%m/%Y"),
                    "time": local.strftime("%H:%M"),
                },
                "buttons": [[{"label": "button_app_not_me", "action": f"app_not_me_{device_id}"}]],
                "status": "pending" if channel else "failed",
                "attempts": 0,
                "uncertain_count": 0,
                "created_at": now,
                "next_attempt_at": now if channel else None,
                "last_error": None if channel else "no_channel",
            }
        )
    if rows:
        op.bulk_insert(_notifications_table(), rows)

    op.drop_index(op.f("ix_devices_alert_due_at"), table_name="devices")
    with op.batch_alter_table("devices") as batch:
        batch.drop_column("alert_attempts")
        batch.drop_column("alert_sent_at")
        batch.drop_column("alert_due_at")


def downgrade() -> None:
    with op.batch_alter_table("devices") as batch:
        batch.add_column(sa.Column("alert_due_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("alert_sent_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("alert_attempts", sa.Integer(), server_default="0", nullable=False))
    op.create_index(op.f("ix_devices_alert_due_at"), "devices", ["alert_due_at"], unique=False)
    connection = op.get_bind()
    # Les alertes pas encore parties retournent dans l'ancienne boîte d'envoi.
    for event_key, sent_at, status in connection.execute(
        sa.text("SELECT event_key, sent_at, status FROM notifications WHERE event_key LIKE 'new_device:%'")
    ).all():
        device_id = int(event_key.split(":", 1)[1])
        if status == "sent":
            connection.execute(
                sa.text("UPDATE devices SET alert_sent_at = :sent_at WHERE id = :id"), {"sent_at": sent_at, "id": device_id}
            )
        elif status != "failed":
            connection.execute(
                sa.text("UPDATE devices SET alert_due_at = :now WHERE id = :id"), {"now": datetime.utcnow(), "id": device_id}
            )
    op.drop_index(op.f("ix_notifications_recipient_account_id"), table_name="notifications")
    op.drop_index("ix_notifications_due", table_name="notifications")
    op.drop_table("notifications")
