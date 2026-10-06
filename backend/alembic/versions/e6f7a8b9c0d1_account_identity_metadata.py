"""Add canonical account roles, language, and verified phone identity.

Revision ID: e6f7a8b9c0d1
Revises: d4e5f6a7b8c9
Create Date: 2026-10-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e6f7a8b9c0d1"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "accounts",
        sa.Column("roles", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )
    op.add_column(
        "accounts",
        sa.Column("phone_e164", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "accounts",
        sa.Column("phone_verified_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "accounts",
        sa.Column("language", sa.String(length=5), nullable=False, server_default="fr"),
    )

    bind = op.get_bind()
    accounts = sa.table(
        "accounts",
        sa.column("id", sa.Integer()),
        sa.column("roles", sa.JSON()),
        sa.column("language", sa.String(length=5)),
    )

    # Build canonical account attributes from the existing Telegram profiles.
    # A person may have both profiles; retain both roles and prefer the client
    # language for their shared account language. Existing phone fields are
    # intentionally not copied: the old schema cannot distinguish a number
    # shared as a Telegram contact from one typed by hand.
    account_ids = bind.execute(sa.select(accounts.c.id).order_by(accounts.c.id)).scalars().all()
    for account_id in account_ids:
        identity_id = bind.execute(
            sa.text(
                "SELECT external_id FROM channel_identities "
                "WHERE account_id = :account_id AND channel = 'telegram'"
            ),
            {"account_id": account_id},
        ).scalar_one_or_none()

        roles: list[str] = []
        language = "fr"
        if identity_id is not None:
            telegram_id = int(identity_id)
            user_language = bind.execute(
                sa.text("SELECT language FROM bot_users WHERE telegram_id = :telegram_id"),
                {"telegram_id": telegram_id},
            ).scalar_one_or_none()
            provider_language = bind.execute(
                sa.text("SELECT language FROM bot_providers WHERE telegram_id = :telegram_id"),
                {"telegram_id": telegram_id},
            ).scalar_one_or_none()
            if user_language is not None:
                roles.append("client")
                language = user_language
            if provider_language is not None:
                roles.append("provider")
                if user_language is None:
                    language = provider_language

        bind.execute(
            accounts.update()
            .where(accounts.c.id == account_id)
            .values(roles=roles, language=language),
        )

    op.create_index(
        "uq_accounts_verified_phone_e164",
        "accounts",
        ["phone_e164"],
        unique=True,
        postgresql_where=sa.text("phone_verified_at IS NOT NULL"),
        sqlite_where=sa.text("phone_verified_at IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_accounts_verified_phone_e164", table_name="accounts")
    op.drop_column("accounts", "language")
    op.drop_column("accounts", "phone_verified_at")
    op.drop_column("accounts", "phone_e164")
    op.drop_column("accounts", "roles")
