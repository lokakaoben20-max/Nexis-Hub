"""Règles d'argent par compte Nexis

- `money_operations.actor_account_id` : compte qui a déclenché l'opération,
  rétro-rempli pour les opérations déclenchées par le client (paiement,
  confirmation). Les décisions admin et automatiques restent sans compte.
- `payment_intents.funding_request` : le client et le prestataire y sont
  désormais désignés par leur compte, plus par leur identifiant Telegram.
- `payouts.requested_by_telegram_id` devient facultatif : un retrait peut
  venir d'un autre canal que Telegram.

Une identité Telegram introuvable arrête la migration : une intention ne
doit jamais perdre son client ou son prestataire.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-11-06
"""
import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CLIENT_OPERATION_KINDS = ("fund_mobile_money", "fund_wallet", "release")


def _load(value):
    return json.loads(value) if isinstance(value, str) else dict(value or {})


def _rewrite_funding_requests(bind, convert) -> None:
    rows = bind.execute(sa.text("SELECT id, funding_request FROM payment_intents ORDER BY id")).fetchall()
    for intent_id, raw in rows:
        request = _load(raw)
        new_request = convert(intent_id, request)
        if new_request != request:
            bind.execute(
                sa.text("UPDATE payment_intents SET funding_request = :request WHERE id = :id"),
                {"request": json.dumps(new_request), "id": intent_id},
            )


def upgrade() -> None:
    op.add_column("money_operations", sa.Column("actor_account_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_money_operations_actor_account_id_accounts", "money_operations", "accounts", ["actor_account_id"], ["id"]
    )
    op.create_index("ix_money_operations_actor_account_id", "money_operations", ["actor_account_id"])

    bind = op.get_bind()
    bind.execute(
        sa.text("""
            UPDATE money_operations AS operation
               SET actor_account_id = identity.account_id
              FROM channel_identities AS identity
             WHERE identity.channel = 'telegram'
               AND identity.external_id = CAST(operation.actor_telegram_id AS VARCHAR)
               AND operation.actor_telegram_id IS NOT NULL
               AND operation.kind IN :kinds
        """).bindparams(sa.bindparam("kinds", expanding=True)),
        {"kinds": list(CLIENT_OPERATION_KINDS)},
    )

    accounts = {
        external_id: account_id
        for account_id, external_id in bind.execute(
            sa.text("SELECT account_id, external_id FROM channel_identities WHERE channel = 'telegram'")
        ).fetchall()
    }

    def to_accounts(intent_id, request):
        if "client_account_id" in request:
            return request
        request = dict(request)
        for role in ("client", "provider"):
            telegram_id = request.pop(f"{role}_telegram_id")
            account_id = accounts.get(str(telegram_id))
            if account_id is None:
                raise RuntimeError(f"Intention {intent_id} : aucun compte pour le {role} Telegram {telegram_id}")
            request[f"{role}_account_id"] = account_id
        return request

    _rewrite_funding_requests(bind, to_accounts)

    with op.batch_alter_table("payouts") as batch:
        batch.alter_column("requested_by_telegram_id", existing_type=sa.BigInteger(), nullable=True)


def downgrade() -> None:
    bind = op.get_bind()
    with op.batch_alter_table("payouts") as batch:
        batch.alter_column("requested_by_telegram_id", existing_type=sa.BigInteger(), nullable=False)

    telegram_ids = {
        account_id: external_id
        for account_id, external_id in bind.execute(
            sa.text("SELECT account_id, external_id FROM channel_identities WHERE channel = 'telegram'")
        ).fetchall()
    }

    def to_telegram(intent_id, request):
        if "client_telegram_id" in request:
            return request
        request = dict(request)
        for role in ("client", "provider"):
            account_id = request.pop(f"{role}_account_id")
            telegram_id = telegram_ids.get(account_id)
            if telegram_id is None:
                raise RuntimeError(f"Intention {intent_id} : le {role} (compte {account_id}) n'a pas d'identité Telegram")
            request[f"{role}_telegram_id"] = int(telegram_id)
        return request

    _rewrite_funding_requests(bind, to_telegram)

    op.drop_index("ix_money_operations_actor_account_id", table_name="money_operations")
    op.drop_constraint("fk_money_operations_actor_account_id_accounts", "money_operations", type_="foreignkey")
    op.drop_column("money_operations", "actor_account_id")
