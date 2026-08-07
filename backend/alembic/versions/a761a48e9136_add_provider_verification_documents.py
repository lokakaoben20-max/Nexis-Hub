"""add provider verification documents

Revision ID: a761a48e9136
Revises: a92fb549a950
Create Date: 2026-08-07 19:31:25.516181

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a761a48e9136'
down_revision: Union[str, Sequence[str], None] = 'a92fb549a950'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('bot_providers', sa.Column('id_document_file_id', sa.String(length=255), nullable=True))
    op.add_column('bot_providers', sa.Column('selfie_file_id', sa.String(length=255), nullable=True))
    op.add_column('bot_providers', sa.Column('portfolio_file_ids', sa.JSON(), nullable=False, server_default='[]'))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('bot_providers', 'portfolio_file_ids')
    op.drop_column('bot_providers', 'selfie_file_id')
    op.drop_column('bot_providers', 'id_document_file_id')
