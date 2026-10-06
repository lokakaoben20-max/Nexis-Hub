"""Mobile Money réel : intentions de paiement et retraits

Voir CONCEPTION_MOBILE_MONEY.md. Deux tables neuves, aucune donnée existante
touchée : le registre (money_operations, ledger_entries) gagne seulement de
nouveaux types de comptes (payout_pending, fees), sans changement de schéma.

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
Create Date: 2026-10-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f7a8b9c0d1e2"
down_revision: Union[str, Sequence[str], None] = "e6f7a8b9c0d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "payment_intents",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("mission_id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("gateway", sa.String(length=30), nullable=False),
        sa.Column("gateway_reference", sa.String(length=64), nullable=True),
        sa.Column("operator", sa.String(length=20), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=False),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("funding_request", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("failure_reason", sa.String(length=255), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["mission_id"], ["bot_missions.mission_id"]),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("gateway", "gateway_reference", name="uq_payment_intents_gateway_reference"),
    )
    op.create_index("ix_payment_intents_mission_id", "payment_intents", ["mission_id"])
    op.create_index("ix_payment_intents_account_id", "payment_intents", ["account_id"])
    op.create_index("ix_payment_intents_status", "payment_intents", ["status"])
    op.create_index(
        "uq_payment_intents_open_per_mission",
        "payment_intents",
        ["mission_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('created', 'pending')"),
        sqlite_where=sa.text("status IN ('created', 'pending')"),
    )
    op.create_table(
        "payouts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("requested_by_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("gateway", sa.String(length=30), nullable=False),
        sa.Column("gateway_reference", sa.String(length=64), nullable=True),
        sa.Column("operator", sa.String(length=20), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=False),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("fee", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("needs_review_reason", sa.String(length=64), nullable=True),
        sa.Column("decided_by_telegram_id", sa.BigInteger(), nullable=True),
        sa.Column("failure_reason", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("gateway", "gateway_reference", name="uq_payouts_gateway_reference"),
    )
    op.create_index("ix_payouts_account_id", "payouts", ["account_id"])
    op.create_index("ix_payouts_status", "payouts", ["status"])


def downgrade() -> None:
    op.drop_index("ix_payouts_status", table_name="payouts")
    op.drop_index("ix_payouts_account_id", table_name="payouts")
    op.drop_table("payouts")
    op.drop_index("uq_payment_intents_open_per_mission", table_name="payment_intents")
    op.drop_index("ix_payment_intents_status", table_name="payment_intents")
    op.drop_index("ix_payment_intents_account_id", table_name="payment_intents")
    op.drop_index("ix_payment_intents_mission_id", table_name="payment_intents")
    op.drop_table("payment_intents")
