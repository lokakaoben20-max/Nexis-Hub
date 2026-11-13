"""Décisions de litige en deux temps

Une décision de Nexis Hub sur un litige n'est plus exécutée tout de suite
(règles du 2026-11-08) : elle est enregistrée dans `dispute_decisions` avec
ses montants figés, et exécutée 3 jours plus tard sauf contestation par le
client ou le prestataire. Une décision contestée est revue par une autre
personne de Nexis Hub (deuxième tour), dont la décision est finale.

Table nouvelle, aucune donnée existante à reprendre : les litiges déjà
tranchés ont leur règlement dans `money_operations`, ceux encore ouverts
n'ont pas de décision.

Revision ID: f1a2b3c4d5e6
Revises: e0f1a2b3c4d5
Create Date: 2026-11-13
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "e0f1a2b3c4d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "dispute_decisions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("mission_id", sa.Integer(), nullable=False),
        sa.Column("round", sa.Integer(), nullable=False),
        sa.Column("decision", sa.String(length=20), nullable=False),
        sa.Column("provider_percentage", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("provider_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("client_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("platform_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("decided_by_account_id", sa.Integer(), nullable=False),
        sa.Column("decided_by_telegram_id", sa.BigInteger(), nullable=True),
        sa.Column("decided_at", sa.DateTime(), nullable=False),
        sa.Column("execute_after", sa.DateTime(), nullable=False),
        sa.Column("contested_by_account_id", sa.Integer(), nullable=True),
        sa.Column("contested_by_role", sa.String(length=20), nullable=True),
        sa.Column("contested_at", sa.DateTime(), nullable=True),
        sa.Column("contest_reason", sa.Text(), nullable=True),
        sa.Column("executed_at", sa.DateTime(), nullable=True),
        sa.Column("executed_operation_id", sa.Integer(), nullable=True),
        sa.CheckConstraint("round IN (1, 2)", name="ck_dispute_decisions_round"),
        sa.CheckConstraint("decision IN ('refund', 'release', 'split')", name="ck_dispute_decisions_decision"),
        sa.ForeignKeyConstraint(["mission_id"], ["bot_missions.mission_id"]),
        sa.ForeignKeyConstraint(["decided_by_account_id"], ["accounts.id"]),
        sa.ForeignKeyConstraint(["contested_by_account_id"], ["accounts.id"]),
        sa.ForeignKeyConstraint(["executed_operation_id"], ["money_operations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("mission_id", "round", name="uq_dispute_decisions_mission_round"),
        sa.UniqueConstraint("executed_operation_id"),
    )
    op.create_index(op.f("ix_dispute_decisions_mission_id"), "dispute_decisions", ["mission_id"], unique=False)
    op.create_index(op.f("ix_dispute_decisions_execute_after"), "dispute_decisions", ["execute_after"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_dispute_decisions_execute_after"), table_name="dispute_decisions")
    op.drop_index(op.f("ix_dispute_decisions_mission_id"), table_name="dispute_decisions")
    op.drop_table("dispute_decisions")
