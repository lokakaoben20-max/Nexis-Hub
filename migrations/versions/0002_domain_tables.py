"""Add remaining five Nexis domain tables.

Revision ID: 0002_domain_tables
Revises: 0001_initial_domain
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_domain_tables"
down_revision = "0001_initial_domain"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "quotes",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("mission_id", sa.BigInteger(), sa.ForeignKey("missions.id"), nullable=False),
        sa.Column("provider_id", sa.BigInteger(), sa.ForeignKey("providers.id"), nullable=False),
        sa.Column("amount", sa.Numeric(20, 4), nullable=False),
        sa.Column("currency", sa.Text(), nullable=False),
        sa.Column("delay_hours", sa.Integer(), nullable=False),
        sa.Column("message", sa.Text()),
        sa.Column("status", sa.Text()),
        sa.Column("amount_usd_equiv", sa.Numeric(20, 4)),
    )
    op.create_foreign_key("fk_transactions_quote_id", "transactions", "quotes", ["quote_id"], ["id"])
    op.create_table(
        "services",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("key", sa.Text(), unique=True, nullable=False),
        sa.Column("name_fr", sa.Text(), nullable=False),
        sa.Column("name_ln", sa.Text()),
        sa.Column("name_en", sa.Text()),
        sa.Column("category", sa.Text()),
        sa.Column("icon_emoji", sa.Text()),
        sa.Column("module", sa.Text(), nullable=False),
        sa.Column("requires_inspection", sa.Integer()),
        sa.Column("visit_fee_usd", sa.Numeric(20, 4)),
        sa.Column("is_active", sa.Integer()),
    )
    op.create_table(
        "service_requests",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("provider_id", sa.BigInteger(), sa.ForeignKey("providers.id"), nullable=False),
        sa.Column("service_name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.Text()),
        sa.Column("admin_note", sa.Text()),
    )
    op.create_table(
        "reviews",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("mission_id", sa.BigInteger(), sa.ForeignKey("missions.id"), unique=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("provider_id", sa.BigInteger(), sa.ForeignKey("providers.id"), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("was_punctual", sa.Integer()),
        sa.Column("was_professional", sa.Integer()),
        sa.Column("was_resolved", sa.Integer()),
        sa.Column("comment", sa.Text()),
        sa.Column("is_public", sa.Integer()),
    )
    op.create_table(
        "platform_settings",
        sa.Column("key", sa.Text(), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("description", sa.Text()),
    )


def downgrade():
    raise RuntimeError("Downgrade disabled: restore an approved backup instead")
