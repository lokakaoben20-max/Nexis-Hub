"""Demandes d'ajout de service et fichiers gardés par le backend

Un prestataire vérifié qui veut proposer un service de plus envoie une
demande (photos de réalisations facultatives) ; l'équipe l'approuve ou la
refuse, comme à l'inscription (décision de Ben, 2026-11-15). Les photos sont
gardées chiffrées par le backend (`stored_files`), quel que soit le canal.

Tables nouvelles et vides : aucune donnée existante à reprendre.

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-11-15
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "d5e6f7a8b9c0"
down_revision: Union[str, Sequence[str], None] = "c4d5e6f7a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "provider_service_additions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("service_key", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("admin_note", sa.Text(), nullable=True),
        sa.Column("decided_by_account_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'cancelled')", name="ck_provider_service_additions_status"
        ),
        sa.CheckConstraint(
            "(status = 'pending' AND decided_at IS NULL) OR (status <> 'pending' AND decided_at IS NOT NULL)",
            name="ck_provider_service_additions_decided",
        ),
        sa.ForeignKeyConstraint(["account_id"], ["provider_profiles.account_id"]),
        sa.ForeignKeyConstraint(["service_key"], ["services.key"]),
        sa.ForeignKeyConstraint(["decided_by_account_id"], ["accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_provider_service_additions_account_id", "provider_service_additions", ["account_id"])
    op.create_index("ix_provider_service_additions_status", "provider_service_additions", ["status"])
    op.create_index(
        "uq_provider_service_additions_pending",
        "provider_service_additions",
        ["account_id", "service_key"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
        sqlite_where=sa.text("status = 'pending'"),
    )
    op.create_table(
        "stored_files",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("owner_account_id", sa.Integer(), nullable=False),
        sa.Column("purpose", sa.String(length=30), nullable=False),
        sa.Column("content_type", sa.String(length=30), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("service_addition_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("purpose IN ('service_photo')", name="ck_stored_files_purpose"),
        sa.CheckConstraint(
            "content_type IN ('image/jpeg', 'image/png', 'image/webp')", name="ck_stored_files_content_type"
        ),
        sa.CheckConstraint("size_bytes > 0", name="ck_stored_files_size"),
        sa.ForeignKeyConstraint(["owner_account_id"], ["accounts.id"]),
        sa.ForeignKeyConstraint(["service_addition_id"], ["provider_service_additions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_stored_files_owner_created", "stored_files", ["owner_account_id", "created_at"])
    op.create_index("ix_stored_files_service_addition_id", "stored_files", ["service_addition_id"])


def downgrade() -> None:
    op.drop_index("ix_stored_files_service_addition_id", table_name="stored_files")
    op.drop_index("ix_stored_files_owner_created", table_name="stored_files")
    op.drop_table("stored_files")
    op.drop_index("uq_provider_service_additions_pending", table_name="provider_service_additions")
    op.drop_index("ix_provider_service_additions_status", table_name="provider_service_additions")
    op.drop_index("ix_provider_service_additions_account_id", table_name="provider_service_additions")
    op.drop_table("provider_service_additions")
