"""Application mobile : appareils, sessions, codes de connexion

- `devices` : téléphones reliés à un compte (clé publique, intégrité,
  délai avant toute action d'argent sortante, coupure définitive).
- `app_sessions` : jetons hachés, familles de renouvellement.
- `login_challenges` : demandes de code, liées à la clé de l'appareil.
- `request_nonces` : anti-rejeu des demandes signées.
- `auth_events` : journal d'audit des connexions, en ajout seul.

Le canal `app` de `channel_identities` ne demande aucun changement de schéma.
Aucune table d'argent n'est touchée.

Plan : app-mobile/plan-etape1-connexion-api-2026-11-07.md, section 4.

Revision ID: 0a1b2c3d4e5f
Revises: c3d4e5f6a7b8
Create Date: 2026-11-07
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0a1b2c3d4e5f"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

REVOCATION_REASON_CHECK = (
    "(revoked_at IS NULL AND revoked_reason IS NULL) OR (revoked_at IS NOT NULL AND revoked_reason IS NOT NULL)"
)


def upgrade() -> None:
    op.create_table(
        "devices",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("platform", sa.String(length=10), nullable=False),
        sa.Column("public_key", sa.Text(), nullable=False),
        sa.Column("key_thumbprint", sa.String(length=64), nullable=False),
        sa.Column("attestation", sa.String(length=12), nullable=False),
        sa.Column("label", sa.String(length=100), nullable=True),
        sa.Column("app_version", sa.String(length=20), nullable=False),
        sa.Column("money_unlocked_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_reason", sa.String(length=30), nullable=True),
        sa.UniqueConstraint("key_thumbprint", name="uq_devices_key_thumbprint"),
        sa.CheckConstraint("platform IN ('android', 'ios')", name="ck_devices_platform"),
        sa.CheckConstraint("attestation IN ('verified', 'unverified')", name="ck_devices_attestation"),
        sa.CheckConstraint(REVOCATION_REASON_CHECK, name="ck_devices_revocation_reason"),
        sa.CheckConstraint("money_unlocked_at >= created_at", name="ck_devices_money_unlock_after_creation"),
    )
    op.create_index("ix_devices_account_id", "devices", ["account_id"])

    op.create_table(
        "app_sessions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("device_id", sa.Integer(), sa.ForeignKey("devices.id"), nullable=False),
        sa.Column("family_id", sa.String(length=32), nullable=False),
        sa.Column("access_hash", sa.String(length=64), nullable=False),
        sa.Column("access_expires_at", sa.DateTime(), nullable=False),
        sa.Column("refresh_hash", sa.String(length=64), nullable=False),
        sa.Column("refresh_expires_at", sa.DateTime(), nullable=False),
        sa.Column("replaced_by_id", sa.Integer(), sa.ForeignKey("app_sessions.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_reason", sa.String(length=30), nullable=True),
        sa.UniqueConstraint("access_hash", name="uq_app_sessions_access_hash"),
        sa.UniqueConstraint("refresh_hash", name="uq_app_sessions_refresh_hash"),
        sa.UniqueConstraint("replaced_by_id", name="uq_app_sessions_replaced_by_id"),
        sa.CheckConstraint("access_expires_at > created_at", name="ck_app_sessions_access_expiry"),
        sa.CheckConstraint("refresh_expires_at >= access_expires_at", name="ck_app_sessions_refresh_expiry"),
        sa.CheckConstraint(REVOCATION_REASON_CHECK, name="ck_app_sessions_revocation_reason"),
    )
    op.create_index("ix_app_sessions_device_id", "app_sessions", ["device_id"])
    op.create_index("ix_app_sessions_family_id", "app_sessions", ["family_id"])

    op.create_table(
        "login_challenges",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("public_id", sa.String(length=32), nullable=False),
        sa.Column("phone_e164", sa.String(length=32), nullable=False),
        sa.Column("purpose", sa.String(length=10), nullable=False),
        sa.Column("delivery", sa.String(length=10), nullable=False),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id"), nullable=True),
        sa.Column("device_key_thumbprint", sa.String(length=64), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=True),
        sa.Column("telegram_start_hash", sa.String(length=64), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ip_hash", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("consumed_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("public_id", name="uq_login_challenges_public_id"),
        sa.UniqueConstraint("telegram_start_hash", name="uq_login_challenges_telegram_start_hash"),
        sa.CheckConstraint("purpose IN ('signup', 'login')", name="ck_login_challenges_purpose"),
        sa.CheckConstraint("delivery IN ('whatsapp', 'telegram')", name="ck_login_challenges_delivery"),
        sa.CheckConstraint("attempts >= 0 AND attempts <= 5", name="ck_login_challenges_attempts"),
        sa.CheckConstraint("expires_at > created_at", name="ck_login_challenges_expiry"),
        sa.CheckConstraint("consumed_at IS NULL OR code_hash IS NOT NULL", name="ck_login_challenges_consumed_needs_code"),
    )
    op.create_index("ix_login_challenges_account_id", "login_challenges", ["account_id"])
    op.create_index("ix_login_challenges_phone_created", "login_challenges", ["phone_e164", "created_at"])
    op.create_index("ix_login_challenges_device_created", "login_challenges", ["device_key_thumbprint", "created_at"])

    op.create_table(
        "request_nonces",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("device_id", sa.Integer(), sa.ForeignKey("devices.id"), nullable=False),
        sa.Column("nonce", sa.String(length=64), nullable=False),
        sa.Column("seen_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("device_id", "nonce", name="uq_request_nonces_device_nonce"),
    )
    op.create_index("ix_request_nonces_seen_at", "request_nonces", ["seen_at"])

    op.create_table(
        "auth_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id"), nullable=True),
        sa.Column("device_id", sa.Integer(), sa.ForeignKey("devices.id"), nullable=True),
        sa.Column("type", sa.String(length=40), nullable=False),
        sa.Column("result", sa.String(length=20), nullable=False),
        sa.Column("ip_hash", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_auth_events_account_id", "auth_events", ["account_id"])
    op.create_index("ix_auth_events_device_id", "auth_events", ["device_id"])
    op.create_index("ix_auth_events_created_at", "auth_events", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_auth_events_created_at", table_name="auth_events")
    op.drop_index("ix_auth_events_device_id", table_name="auth_events")
    op.drop_index("ix_auth_events_account_id", table_name="auth_events")
    op.drop_table("auth_events")
    op.drop_index("ix_request_nonces_seen_at", table_name="request_nonces")
    op.drop_table("request_nonces")
    op.drop_index("ix_login_challenges_device_created", table_name="login_challenges")
    op.drop_index("ix_login_challenges_phone_created", table_name="login_challenges")
    op.drop_index("ix_login_challenges_account_id", table_name="login_challenges")
    op.drop_table("login_challenges")
    op.drop_index("ix_app_sessions_family_id", table_name="app_sessions")
    op.drop_index("ix_app_sessions_device_id", table_name="app_sessions")
    op.drop_table("app_sessions")
    op.drop_index("ix_devices_account_id", table_name="devices")
    op.drop_table("devices")
