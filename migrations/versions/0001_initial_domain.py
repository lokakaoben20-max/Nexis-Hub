"""Initial isolated PostgreSQL tables for Nexis domain (partial model).

Revision ID: 0001_initial_domain
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial_domain"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False, unique=True),
        sa.Column("phone_number", sa.Text(), nullable=False),
        sa.Column("first_name", sa.Text()),
        sa.Column("language", sa.String(10), nullable=False),
        sa.Column("wallet_balance_usd", sa.Numeric(20, 4), nullable=False),
        sa.Column("wallet_balance_cdf", sa.Numeric(20, 4), nullable=False),
    )
    op.create_table(
        "providers",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False, unique=True),
        sa.Column("phone_number", sa.Text(), nullable=False),
        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column("services", sa.Text(), nullable=False),
        sa.Column("communes", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("wallet_balance_usd", sa.Numeric(20, 4), nullable=False),
        sa.Column("wallet_balance_cdf", sa.Numeric(20, 4), nullable=False),
    )
    op.create_table(
        "missions",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("provider_id", sa.BigInteger(), sa.ForeignKey("providers.id")),
        sa.Column("service", sa.Text(), nullable=False),
        sa.Column("commune", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("payment_status", sa.String(40), nullable=False),
        sa.Column("total_client", sa.Numeric(20, 4), nullable=False),
        sa.Column("net_provider", sa.Numeric(20, 4), nullable=False),
    )
    op.create_table(
        "transactions",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("mission_id", sa.BigInteger(), sa.ForeignKey("missions.id"), nullable=False),
        sa.Column("quote_id", sa.BigInteger()),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("amount", sa.Numeric(20, 4), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("mobile_money_ref", sa.Text()),
    )


def downgrade():
    # Destructive downgrades are intentionally forbidden for financial data.
    raise RuntimeError("Downgrade disabled: restore an approved backup instead")
