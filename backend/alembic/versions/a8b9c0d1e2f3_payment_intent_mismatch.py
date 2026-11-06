"""Paiements à montant différent : montant reçu et décision de l'admin

Quatre colonnes facultatives sur payment_intents, aucune donnée existante
modifiée. Une intention déjà en `mismatch` garde ses colonnes vides : la
décision de l'admin relit toujours le montant chez l'agrégateur.

Revision ID: a8b9c0d1e2f3
Revises: f7a8b9c0d1e2
Create Date: 2026-10-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a8b9c0d1e2f3"
down_revision: Union[str, Sequence[str], None] = "f7a8b9c0d1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("payment_intents") as batch:
        batch.add_column(sa.Column("received_amount", sa.Numeric(precision=14, scale=2), nullable=True))
        batch.add_column(sa.Column("received_currency", sa.String(length=3), nullable=True))
        batch.add_column(sa.Column("resolved_by_telegram_id", sa.BigInteger(), nullable=True))
        batch.add_column(sa.Column("resolved_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("payment_intents") as batch:
        batch.drop_column("resolved_at")
        batch.drop_column("resolved_by_telegram_id")
        batch.drop_column("received_currency")
        batch.drop_column("received_amount")
