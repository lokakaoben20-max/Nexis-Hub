"""Interrupteurs d'arrêt Mobile Money (encaissements, versements) et leur journal

Tables nouvelles et vides : sans ligne, un flux est ouvert. Rien ne change
tant qu'un admin n'a rien coupé (`backend/app/interrupteurs.py`).

Revision ID: f8a9b0c1d2e3
Revises: e7f8a9b0c1d2
Create Date: 2026-11-19
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "f8a9b0c1d2e3"
down_revision: Union[str, Sequence[str], None] = "e7f8a9b0c1d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NAMES = "name IN ('collections', 'payouts')"


def upgrade() -> None:
    op.create_table(
        "money_switches",
        sa.Column("name", sa.String(length=20), nullable=False),
        sa.Column("is_open", sa.Boolean(), nullable=False),
        sa.Column("changed_at", sa.DateTime(), nullable=False),
        sa.Column("changed_by_telegram_id", sa.BigInteger(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.CheckConstraint(NAMES, name="ck_money_switches_name"),
        sa.PrimaryKeyConstraint("name"),
    )
    op.create_table(
        "money_switch_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=20), nullable=False),
        sa.Column("is_open", sa.Boolean(), nullable=False),
        sa.Column("at", sa.DateTime(), nullable=False),
        sa.Column("by_telegram_id", sa.BigInteger(), nullable=True),
        sa.Column("source", sa.String(length=10), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.CheckConstraint(NAMES, name="ck_money_switch_events_name"),
        sa.CheckConstraint("source IN ('bot', 'cli')", name="ck_money_switch_events_source"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_money_switch_events_name"), "money_switch_events", ["name"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_money_switch_events_name"), table_name="money_switch_events")
    op.drop_table("money_switch_events")
    op.drop_table("money_switches")
