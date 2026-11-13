"""Rôles admin en base, à la place de ADMIN_TELEGRAM_ID

Plusieurs personnes de Nexis Hub peuvent être admin. C'est nécessaire pour la
révision d'une décision de litige contestée, qui doit venir d'une autre
personne que la première décision (règle du 2026-11-08).

Table nouvelle et vide : après la migration, personne n'est admin tant
qu'aucun rôle n'a été donné avec `python -m backend.app.admins ajouter`.

Revision ID: a2b3c4d5e6f7
Revises: a3b4c5d6e7f8
Create Date: 2026-11-13
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "a2b3c4d5e6f7"
down_revision: Union[str, Sequence[str], None] = "a3b4c5d6e7f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "admin_roles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("granted_at", sa.DateTime(), nullable=False),
        sa.Column("granted_reason", sa.Text(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_reason", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_admin_roles_account_id"), "admin_roles", ["account_id"], unique=False)
    op.create_index(
        "uq_admin_roles_active_account",
        "admin_roles",
        ["account_id"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
        sqlite_where=sa.text("revoked_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_admin_roles_active_account", table_name="admin_roles")
    op.drop_index(op.f("ix_admin_roles_account_id"), table_name="admin_roles")
    op.drop_table("admin_roles")
