"""add mission timestamps and quote created_at for celery tasks

Revision ID: a92fb549a950
Revises: 83f8778ff610
Create Date: 2026-08-06 18:34:32.120354

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a92fb549a950'
down_revision: Union[str, Sequence[str], None] = '83f8778ff610'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('bot_missions', sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')))
    op.add_column('bot_missions', sa.Column('status_changed_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')))
    op.add_column('bot_missions', sa.Column('reminder_sent_10min', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    op.add_column('bot_missions', sa.Column('reminder_sent_20min', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    op.add_column('bot_quotes', sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('bot_quotes', 'created_at')
    op.drop_column('bot_missions', 'reminder_sent_20min')
    op.drop_column('bot_missions', 'reminder_sent_10min')
    op.drop_column('bot_missions', 'status_changed_at')
    op.drop_column('bot_missions', 'created_at')
