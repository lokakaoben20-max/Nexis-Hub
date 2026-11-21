"""Conditions d'utilisation : versions publiées et acceptations

Tables nouvelles et vides. Tant qu'aucune version n'est publiée
(`python -m backend.app.conditions publier`), aucune inscription n'aboutit
et aucune action n'est permise : la case à cocher est obligatoire
(backend/app/conditions.py, CONCEPTION_CONDITIONS.md).

Revision ID: a9b0c1d2e3f4
Revises: f8a9b0c1d2e3
Create Date: 2026-11-20
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "a9b0c1d2e3f4"
down_revision: Union[str, Sequence[str], None] = "f8a9b0c1d2e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "legal_document_versions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("document_key", sa.String(length=40), nullable=False),
        sa.Column("version", sa.String(length=30), nullable=False),
        sa.Column("language", sa.String(length=5), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("text_sha256", sa.String(length=64), nullable=False),
        sa.Column("effective_at", sa.DateTime(), nullable=False),
        sa.Column("published_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "document_key IN ('cgu', 'conditions_prestataires')", name="ck_legal_document_versions_key"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_key", "version", name="uq_legal_document_versions_key_version"),
    )
    op.create_index(
        op.f("ix_legal_document_versions_document_key"), "legal_document_versions", ["document_key"], unique=False
    )
    op.create_table(
        "legal_acceptances",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("version_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=10), nullable=False),
        sa.Column("surface", sa.String(length=20), nullable=False),
        sa.Column("language", sa.String(length=5), nullable=False),
        sa.Column("accepted_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("role IN ('client', 'provider')", name="ck_legal_acceptances_role"),
        sa.CheckConstraint(
            "surface IN ('telegram_bot', 'mini_app', 'whatsapp', 'app')", name="ck_legal_acceptances_surface"
        ),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.ForeignKeyConstraint(["version_id"], ["legal_document_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", "version_id", name="uq_legal_acceptances_account_version"),
    )
    op.create_index(op.f("ix_legal_acceptances_account_id"), "legal_acceptances", ["account_id"], unique=False)
    op.create_index(op.f("ix_legal_acceptances_version_id"), "legal_acceptances", ["version_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_legal_acceptances_version_id"), table_name="legal_acceptances")
    op.drop_index(op.f("ix_legal_acceptances_account_id"), table_name="legal_acceptances")
    op.drop_table("legal_acceptances")
    op.drop_index(op.f("ix_legal_document_versions_document_key"), table_name="legal_document_versions")
    op.drop_table("legal_document_versions")
