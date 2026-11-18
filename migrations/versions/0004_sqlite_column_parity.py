"""Complete column parity with SQLite, without data deletion.

Revision ID: 0004_sqlite_column_parity
Revises: 0003_operational_fields
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_sqlite_column_parity"
down_revision = "0003_operational_fields"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("missions", sa.Column("is_urgent", sa.Integer(), nullable=True))
    op.add_column("missions", sa.Column("photo_file_id", sa.Text(), nullable=True))
    op.add_column("missions", sa.Column("voice_file_id", sa.Text(), nullable=True))
    op.add_column("missions", sa.Column("visit_fee_paid", sa.Integer(), nullable=True))
    op.add_column("missions", sa.Column("visit_fee_status", sa.Text(), nullable=True))
    op.add_column("missions", sa.Column("dispute_deadline", sa.Text(), nullable=True))
    op.add_column("missions", sa.Column("admin_note", sa.Text(), nullable=True))
    op.add_column("missions", sa.Column("client_latitude", sa.Float(), nullable=True))
    op.add_column("missions", sa.Column("client_longitude", sa.Float(), nullable=True))
    op.add_column("missions", sa.Column("distance_km", sa.Float(), nullable=True))
    op.add_column("missions", sa.Column("commission_rate", sa.Numeric(20, 4), nullable=True))
    op.add_column("missions", sa.Column("scheduled_at", sa.Text(), nullable=True))
    op.add_column("missions", sa.Column("arrived_at", sa.Text(), nullable=True))
    op.add_column("missions", sa.Column("started_at", sa.Text(), nullable=True))
    op.add_column("missions", sa.Column("finished_at", sa.Text(), nullable=True))
    op.add_column("missions", sa.Column("confirmed_at", sa.Text(), nullable=True))
    op.add_column("missions", sa.Column("preferred_provider_id", sa.BigInteger(), nullable=True))
    op.add_column("quotes", sa.Column("created_at", sa.Text(), nullable=True))
    op.add_column("providers", sa.Column("languages_spoken", sa.Text(), nullable=True))
    op.add_column("providers", sa.Column("module", sa.Text(), nullable=True))
    op.add_column("providers", sa.Column("rating", sa.Float(), nullable=True))
    op.add_column("providers", sa.Column("total_missions", sa.Integer(), nullable=True))
    op.add_column("providers", sa.Column("success_rate", sa.Float(), nullable=True))
    op.add_column("providers", sa.Column("consecutive_ignored", sa.Integer(), nullable=True))
    op.add_column("providers", sa.Column("warnings_count", sa.Integer(), nullable=True))
    op.add_column("providers", sa.Column("visit_fee_enabled", sa.Integer(), nullable=True))
    op.add_column("providers", sa.Column("latitude", sa.Float(), nullable=True))
    op.add_column("providers", sa.Column("longitude", sa.Float(), nullable=True))
    op.add_column("providers", sa.Column("subscription_end", sa.Text(), nullable=True))
    op.add_column("providers", sa.Column("commission_rate", sa.Numeric(20, 4), nullable=True))
    op.add_column("providers", sa.Column("language", sa.Text(), nullable=True))
    op.add_column("providers", sa.Column("member_since_months", sa.Integer(), nullable=True))
    op.add_column("service_requests", sa.Column("created_at", sa.Text(), nullable=True))
    op.add_column("services", sa.Column("created_at", sa.Text(), nullable=True))
    op.add_column("reviews", sa.Column("created_at", sa.Text(), nullable=True))
    op.add_column("platform_settings", sa.Column("updated_at", sa.Text(), nullable=True))


def downgrade():
    raise RuntimeError("Downgrade disabled: restore an approved backup instead")
