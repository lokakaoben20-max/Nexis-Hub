"""acceptation des conditions : versions publiées et décisions

Voir CONCEPTION_ACCEPTATIONS.md. Deux tables neuves, aucune donnée existante.

À rebaser sur e6f7a8b9c0d1 (migration d'identité préparée sur le PC de Ben)
avant toute fusion : sans cela, deux têtes Alembic.

Revision ID: f1a2b3c4d5e6
Revises: d4e5f6a7b8c9
Create Date: 2026-10-03 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'legal_document_versions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('document_key', sa.String(length=50), nullable=False),
        sa.Column('version', sa.String(length=50), nullable=False),
        sa.Column('url', sa.String(length=500), nullable=False),
        sa.Column('text_sha256', sa.String(length=64), nullable=False),
        sa.Column('effective_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('document_key', 'version', name='uq_legal_document_versions_key_version'),
    )
    op.create_index(op.f('ix_legal_document_versions_document_key'), 'legal_document_versions', ['document_key'], unique=False)
    op.create_index(op.f('ix_legal_document_versions_effective_at'), 'legal_document_versions', ['effective_at'], unique=False)
    op.create_table(
        'legal_acceptances',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('version_id', sa.Integer(), nullable=False),
        sa.Column('decision', sa.String(length=10), nullable=False),
        sa.Column('channel', sa.String(length=20), nullable=False),
        sa.Column('language', sa.String(length=5), nullable=True),
        sa.Column('decided_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ),
        sa.ForeignKeyConstraint(['version_id'], ['legal_document_versions.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint("decision IN ('accepted', 'refused')", name='ck_legal_acceptances_decision'),
    )
    op.create_index(op.f('ix_legal_acceptances_account_id'), 'legal_acceptances', ['account_id'], unique=False)
    op.create_index(op.f('ix_legal_acceptances_version_id'), 'legal_acceptances', ['version_id'], unique=False)
    op.create_index(op.f('ix_legal_acceptances_decided_at'), 'legal_acceptances', ['decided_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_legal_acceptances_decided_at'), table_name='legal_acceptances')
    op.drop_index(op.f('ix_legal_acceptances_version_id'), table_name='legal_acceptances')
    op.drop_index(op.f('ix_legal_acceptances_account_id'), table_name='legal_acceptances')
    op.drop_table('legal_acceptances')
    op.drop_index(op.f('ix_legal_document_versions_effective_at'), table_name='legal_document_versions')
    op.drop_index(op.f('ix_legal_document_versions_document_key'), table_name='legal_document_versions')
    op.drop_table('legal_document_versions')
