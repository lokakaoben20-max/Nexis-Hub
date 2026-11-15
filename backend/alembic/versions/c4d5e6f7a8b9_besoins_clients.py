"""Besoins des clients hors catalogue (remplace « Autre service »)

Un client dont le besoin n'entre dans aucun service l'écrit et l'envoie à
l'équipe Nexis Hub, qui lui répond (décision de Ben, 2026-11-15). Ni mission
ni argent.

Table nouvelle et vide : aucune donnée existante à reprendre.

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-11-15
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "c4d5e6f7a8b9"
down_revision: Union[str, Sequence[str], None] = "b3c4d5e6f7a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "client_service_requests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("admin_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("status IN ('pending', 'accepted', 'rejected')", name="ck_client_service_requests_status"),
        sa.CheckConstraint(
            "(status = 'pending' AND reviewed_at IS NULL) OR (status <> 'pending' AND reviewed_at IS NOT NULL)",
            name="ck_client_service_requests_reviewed",
        ),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_client_service_requests_account_id", "client_service_requests", ["account_id"])
    op.create_index("ix_client_service_requests_status", "client_service_requests", ["status"])


def downgrade() -> None:
    op.drop_index("ix_client_service_requests_status", table_name="client_service_requests")
    op.drop_index("ix_client_service_requests_account_id", table_name="client_service_requests")
    op.drop_table("client_service_requests")
