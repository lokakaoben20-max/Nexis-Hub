"""Relie les entités métier aux comptes Nexis

Revision ID: a1b2c3d4e5f6
Revises: a8b9c0d1e2f3
Create Date: 2026-10-07
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "a8b9c0d1e2f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for table, column in (
        ("bot_quotes", "provider_account_id"),
        ("bot_reviews", "client_account_id"),
        ("bot_reviews", "provider_account_id"),
        ("bot_service_requests", "provider_account_id"),
    ):
        op.add_column(table, sa.Column(column, sa.Integer(), nullable=True))
        op.create_foreign_key(
            f"fk_{table}_{column}_accounts", table, "accounts", [column], ["id"]
        )
        op.create_index(f"ix_{table}_{column}", table, [column])

    bind = op.get_bind()
    # Les identités sont déjà créées par la migration du registre. Ne jamais
    # fabriquer ici de compte : un historique non rattaché doit rester visible
    # comme anomalie d'audit, pas devenir un compte vide.
    for table, account_col, telegram_col in (
        ("bot_missions", "client_account_id", "telegram_id"),
        ("bot_missions", "provider_account_id", "provider_telegram_id"),
        ("bot_quotes", "provider_account_id", "provider_telegram_id"),
        ("bot_reviews", "client_account_id", "client_telegram_id"),
        ("bot_reviews", "provider_account_id", "provider_telegram_id"),
        ("bot_service_requests", "provider_account_id", "provider_telegram_id"),
    ):
        bind.execute(sa.text(f"""
            UPDATE {table} AS entity
               SET {account_col} = identity.account_id
              FROM channel_identities AS identity
             WHERE identity.channel = 'telegram'
               AND identity.external_id = CAST(entity.{telegram_col} AS VARCHAR)
               AND entity.{account_col} IS NULL
               AND entity.{telegram_col} IS NOT NULL
        """))


def downgrade() -> None:
    for table, column in (
        ("bot_service_requests", "provider_account_id"),
        ("bot_reviews", "provider_account_id"),
        ("bot_reviews", "client_account_id"),
        ("bot_quotes", "provider_account_id"),
    ):
        op.drop_index(f"ix_{table}_{column}", table_name=table)
        op.drop_constraint(f"fk_{table}_{column}_accounts", table, type_="foreignkey")
        op.drop_column(table, column)
