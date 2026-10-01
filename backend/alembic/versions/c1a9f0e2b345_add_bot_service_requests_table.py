"""add bot_service_requests table

Revision ID: c1a9f0e2b345
Revises: a761a48e9136
Create Date: 2026-09-01 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1a9f0e2b345'
down_revision: Union[str, Sequence[str], None] = 'a761a48e9136'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('bot_service_requests',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('provider_telegram_id', sa.BigInteger(), nullable=False),
        sa.Column('service_name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False, server_default=''),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('admin_note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['provider_telegram_id'], ['bot_providers.telegram_id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_bot_service_requests_provider_telegram_id'), 'bot_service_requests', ['provider_telegram_id'], unique=False)
    op.create_index(op.f('ix_bot_service_requests_status'), 'bot_service_requests', ['status'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_bot_service_requests_status'), table_name='bot_service_requests')
    op.drop_index(op.f('ix_bot_service_requests_provider_telegram_id'), table_name='bot_service_requests')
    op.drop_table('bot_service_requests')
