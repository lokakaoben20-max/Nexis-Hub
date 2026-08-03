"""add bot_reviews table and provider rating aggregates

Revision ID: 83f8778ff610
Revises: be8b67fa1f0e
Create Date: 2026-08-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '83f8778ff610'
down_revision: Union[str, Sequence[str], None] = 'be8b67fa1f0e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('bot_reviews',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('mission_id', sa.Integer(), nullable=False),
    sa.Column('client_telegram_id', sa.BigInteger(), nullable=False),
    sa.Column('provider_telegram_id', sa.BigInteger(), nullable=False),
    sa.Column('rating', sa.Integer(), nullable=False),
    sa.Column('comment', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['mission_id'], ['bot_missions.mission_id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_bot_reviews_mission_id'), 'bot_reviews', ['mission_id'], unique=True)
    op.create_index(op.f('ix_bot_reviews_client_telegram_id'), 'bot_reviews', ['client_telegram_id'], unique=False)
    op.create_index(op.f('ix_bot_reviews_provider_telegram_id'), 'bot_reviews', ['provider_telegram_id'], unique=False)
    op.add_column('bot_providers', sa.Column('average_rating', sa.Float(), nullable=False, server_default='0'))
    op.add_column('bot_providers', sa.Column('total_reviews', sa.Integer(), nullable=False, server_default='0'))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('bot_providers', 'total_reviews')
    op.drop_column('bot_providers', 'average_rating')
    op.drop_index(op.f('ix_bot_reviews_provider_telegram_id'), table_name='bot_reviews')
    op.drop_index(op.f('ix_bot_reviews_client_telegram_id'), table_name='bot_reviews')
    op.drop_index(op.f('ix_bot_reviews_mission_id'), table_name='bot_reviews')
    op.drop_table('bot_reviews')
