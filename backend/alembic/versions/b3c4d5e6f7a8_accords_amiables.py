"""Accord amiable sur un litige (« On s'est arrangés »)

Le client d'une mission en litige propose un arrangement (le prestataire
repasse, le client paie tout, est remboursé, ou partage), le prestataire
accepte ou refuse. Une proposition acceptée règle tout de suite, sans délai
de contestation (règles du 2026-11-08, plan des litiges, 4.4).

Table nouvelle et vide : aucune donnée existante à reprendre.

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
Create Date: 2026-11-13
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "b3c4d5e6f7a8"
down_revision: Union[str, Sequence[str], None] = "a2b3c4d5e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "dispute_settlement_offers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("mission_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("provider_percentage", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("provider_amount", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("client_amount", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("platform_amount", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("proposed_by_account_id", sa.Integer(), nullable=False),
        sa.Column("proposed_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("responded_by_account_id", sa.Integer(), nullable=True),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("settlement_operation_id", sa.Integer(), nullable=True),
        sa.CheckConstraint("kind IN ('redo', 'release', 'refund', 'split')", name="ck_dispute_offers_kind"),
        sa.CheckConstraint(
            "status IN ('pending', 'accepted', 'declined', 'expired', 'cancelled')", name="ck_dispute_offers_status"
        ),
        sa.CheckConstraint("(kind = 'split') = (provider_percentage IS NOT NULL)", name="ck_dispute_offers_split_percentage"),
        sa.ForeignKeyConstraint(["mission_id"], ["bot_missions.mission_id"]),
        sa.ForeignKeyConstraint(["proposed_by_account_id"], ["accounts.id"]),
        sa.ForeignKeyConstraint(["responded_by_account_id"], ["accounts.id"]),
        sa.ForeignKeyConstraint(["settlement_operation_id"], ["money_operations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("settlement_operation_id"),
    )
    op.create_index(op.f("ix_dispute_settlement_offers_mission_id"), "dispute_settlement_offers", ["mission_id"], unique=False)
    op.create_index(op.f("ix_dispute_settlement_offers_expires_at"), "dispute_settlement_offers", ["expires_at"], unique=False)
    op.create_index(
        "uq_dispute_offers_pending_mission",
        "dispute_settlement_offers",
        ["mission_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
        sqlite_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_index("uq_dispute_offers_pending_mission", table_name="dispute_settlement_offers")
    op.drop_index(op.f("ix_dispute_settlement_offers_expires_at"), table_name="dispute_settlement_offers")
    op.drop_index(op.f("ix_dispute_settlement_offers_mission_id"), table_name="dispute_settlement_offers")
    op.drop_table("dispute_settlement_offers")
