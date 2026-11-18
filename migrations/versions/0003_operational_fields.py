"""Add operational and financial fields, nullable for safe existing-row upgrades.

Revision ID: 0003_operational_fields
Revises: 0002_domain_tables
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_operational_fields"
down_revision = "0002_domain_tables"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("channel", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("commune", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("preferred_currency", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("is_active", sa.Integer(), nullable=True))
    op.add_column("users", sa.Column("total_missions", sa.Integer(), nullable=True))
    op.add_column("users", sa.Column("created_at", sa.Text(), nullable=True))
    op.add_column("providers", sa.Column("is_verified", sa.Integer(), nullable=True))
    op.add_column("providers", sa.Column("is_active", sa.Integer(), nullable=True))
    op.add_column("providers", sa.Column("is_suspended", sa.Integer(), nullable=True))
    op.add_column("providers", sa.Column("badge", sa.Text(), nullable=True))
    op.add_column("providers", sa.Column("id_document_url", sa.Text(), nullable=True))
    op.add_column("providers", sa.Column("portfolio_urls", sa.Text(), nullable=True))
    op.add_column("providers", sa.Column("subscription", sa.Text(), nullable=True))
    op.add_column("providers", sa.Column("preferred_currency", sa.Text(), nullable=True))
    op.add_column("providers", sa.Column("created_at", sa.Text(), nullable=True))
    op.add_column("missions", sa.Column("channel", sa.Text(), nullable=True))
    op.add_column("missions", sa.Column("service_id", sa.BigInteger(), nullable=True))
    op.add_column("missions", sa.Column("address_details", sa.Text(), nullable=True))
    op.add_column("missions", sa.Column("amount", sa.Numeric(20, 4), nullable=True))
    op.add_column("missions", sa.Column("amount_usd_equiv", sa.Numeric(20, 4), nullable=True))
    op.add_column("missions", sa.Column("commission_amount", sa.Numeric(20, 4), nullable=True))
    op.add_column("missions", sa.Column("tola_fee", sa.Numeric(20, 4), nullable=True))
    op.add_column("missions", sa.Column("aggregator_fee", sa.Numeric(20, 4), nullable=True))
    op.add_column("missions", sa.Column("payment_ref", sa.Text(), nullable=True))
    op.add_column("missions", sa.Column("dispute_reason", sa.Text(), nullable=True))
    op.add_column("missions", sa.Column("created_at", sa.Text(), nullable=True))
    op.add_column("transactions", sa.Column("amount_usd_equiv", sa.Numeric(20, 4), nullable=True))
    op.add_column("transactions", sa.Column("commission_amount", sa.Numeric(20, 4), nullable=True))
    op.add_column("transactions", sa.Column("tola_fee", sa.Numeric(20, 4), nullable=True))
    op.add_column("transactions", sa.Column("net_provider", sa.Numeric(20, 4), nullable=True))
    op.add_column("transactions", sa.Column("aggregator_fee", sa.Numeric(20, 4), nullable=True))
    op.add_column("transactions", sa.Column("operator", sa.Text(), nullable=True))
    op.add_column("transactions", sa.Column("phone_number", sa.Text(), nullable=True))
    op.add_column("transactions", sa.Column("created_at", sa.Text(), nullable=True))


def downgrade():
    raise RuntimeError("Downgrade disabled: restore an approved backup instead")
