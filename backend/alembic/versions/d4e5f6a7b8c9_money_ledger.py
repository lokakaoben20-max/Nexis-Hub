"""registre d'argent : comptes Nexis, money_operations, ledger_entries

Le backend devient la seule source de vérité de l'argent (CONCEPTION_ARGENT.md) :
- crée les comptes Nexis (`accounts`, indépendants du canal) et rattache chaque
  telegram_id connu à son compte (`channel_identities`) ;
- crée les tables du registre et les colonnes de litige et de comptes des
  missions ;
- reprend les soldes existants dans un wallet unique par personne : le solde
  client et le solde prestataire d'une même personne s'additionnent ;
- enregistre le paiement de chaque mission encore en escrow, pour que sa
  libération, son remboursement ou son partage partent d'un escrow réel ;
- supprime les colonnes de solde, devenues des sommes du registre.

Revision ID: d4e5f6a7b8c9
Revises: c1a9f0e2b345
Create Date: 2026-10-02 20:00:00.000000

"""
import json
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'c1a9f0e2b345'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CENT = Decimal("0.01")
WALLET_TABLES = ("bot_users", "bot_providers")
CURRENCY_COLUMNS = (("USD", "wallet_balance_usd"), ("CDF", "wallet_balance_cdf"))


def _money(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(CENT, rounding=ROUND_HALF_UP)


def _account_for_telegram(bind, accounts: dict, telegram_id):
    if telegram_id is None:
        return None
    if telegram_id not in accounts:
        now = datetime.utcnow()
        account_id = bind.execute(
            sa.text("INSERT INTO accounts (created_at) VALUES (:created_at) RETURNING id"), {"created_at": now}
        ).scalar_one()
        bind.execute(
            sa.text(
                "INSERT INTO channel_identities (account_id, channel, external_id, verified_at, created_at) "
                "VALUES (:account_id, 'telegram', :external_id, :now, :now)"
            ),
            {"account_id": account_id, "external_id": str(telegram_id), "now": now},
        )
        accounts[telegram_id] = account_id
    return accounts[telegram_id]


def _insert_operation(bind, *, kind, currency, movements, mission_id=None, phase=None, details=None):
    now = datetime.utcnow()
    operation_id = bind.execute(
        sa.text(
            "INSERT INTO money_operations (kind, mission_id, phase, actor_telegram_id, reference, details, created_at) "
            "VALUES (:kind, :mission_id, :phase, NULL, NULL, :details, :created_at) RETURNING id"
        ),
        {"kind": kind, "mission_id": mission_id, "phase": phase, "details": json.dumps(details or {}), "created_at": now},
    ).scalar_one()
    for account_type, account_id, amount in movements:
        bind.execute(
            sa.text(
                "INSERT INTO ledger_entries (operation_id, account_type, account_id, currency, amount, created_at) "
                "VALUES (:operation_id, :account_type, :account_id, :currency, :amount, :created_at)"
            ),
            {
                "operation_id": operation_id,
                "account_type": account_type,
                "account_id": account_id,
                "currency": currency,
                "amount": amount,
                "created_at": now,
            },
        )


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('accounts',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table('channel_identities',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('channel', sa.String(length=20), nullable=False),
        sa.Column('external_id', sa.String(length=64), nullable=False),
        sa.Column('verified_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('channel', 'external_id', name='uq_channel_identities_channel_external_id'),
        sa.UniqueConstraint('account_id', 'channel', name='uq_channel_identities_account_channel'),
    )
    op.create_index(op.f('ix_channel_identities_account_id'), 'channel_identities', ['account_id'], unique=False)
    op.create_table('money_operations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('kind', sa.String(length=30), nullable=False),
        sa.Column('mission_id', sa.Integer(), nullable=True),
        sa.Column('phase', sa.String(length=20), nullable=True),
        sa.Column('actor_telegram_id', sa.BigInteger(), nullable=True),
        sa.Column('reference', sa.String(length=64), nullable=True),
        sa.Column('details', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['mission_id'], ['bot_missions.mission_id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('mission_id', 'phase', name='uq_money_operations_mission_phase'),
    )
    op.create_index(op.f('ix_money_operations_mission_id'), 'money_operations', ['mission_id'], unique=False)
    op.create_table('ledger_entries',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('operation_id', sa.Integer(), nullable=False),
        sa.Column('account_type', sa.String(length=20), nullable=False),
        sa.Column('account_id', sa.BigInteger(), nullable=True),
        sa.Column('currency', sa.String(length=3), nullable=False),
        sa.Column('amount', sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['operation_id'], ['money_operations.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_ledger_entries_operation_id'), 'ledger_entries', ['operation_id'], unique=False)
    op.create_index(op.f('ix_ledger_entries_account_type'), 'ledger_entries', ['account_type'], unique=False)
    op.create_index(op.f('ix_ledger_entries_account_id'), 'ledger_entries', ['account_id'], unique=False)
    op.add_column('bot_missions', sa.Column('dispute_opened_at', sa.DateTime(), nullable=True))
    op.add_column('bot_missions', sa.Column('dispute_deadline', sa.DateTime(), nullable=True))
    op.add_column('bot_missions', sa.Column('accepted_quote_ref', sa.Integer(), nullable=True))
    op.add_column('bot_missions', sa.Column('client_account_id', sa.Integer(), sa.ForeignKey('accounts.id'), nullable=True))
    op.add_column('bot_missions', sa.Column('provider_account_id', sa.Integer(), sa.ForeignKey('accounts.id'), nullable=True))

    bind = op.get_bind()
    accounts = {}
    wallets: dict[tuple[int, str], Decimal] = {}
    for table in WALLET_TABLES:
        rows = bind.execute(
            sa.text(f"SELECT telegram_id, wallet_balance_usd, wallet_balance_cdf FROM {table} ORDER BY telegram_id")
        ).fetchall()
        for telegram_id, usd, cdf in rows:
            account_id = _account_for_telegram(bind, accounts, telegram_id)
            for currency, value in (("USD", usd), ("CDF", cdf)):
                wallets[(account_id, currency)] = wallets.get((account_id, currency), Decimal("0.00")) + _money(value)
    for (account_id, currency), amount in sorted(wallets.items()):
        if amount == 0:
            continue
        _insert_operation(
            bind,
            kind="opening_balance",
            currency=currency,
            details={"account_id": account_id},
            movements=[("external", None, -amount), ("wallet", account_id, amount)],
        )

    open_escrows = bind.execute(
        sa.text(
            "SELECT mission_id, currency, total_client, commission_amount, net_provider, provider_telegram_id, urgent, telegram_id "
            "FROM bot_missions WHERE payment_status = 'paid_escrow' "
            "AND (status IS NULL OR status NOT IN ('completed', 'cancelled')) ORDER BY mission_id"
        )
    ).fetchall()
    for mission_id, currency, total, commission, net, provider_telegram_id, urgent, client_telegram_id in open_escrows:
        total, commission, net = _money(total), _money(commission), _money(net)
        bind.execute(
            sa.text("UPDATE bot_missions SET client_account_id = :client, provider_account_id = :provider WHERE mission_id = :mission_id"),
            {
                "client": _account_for_telegram(bind, accounts, client_telegram_id),
                "provider": _account_for_telegram(bind, accounts, provider_telegram_id),
                "mission_id": mission_id,
            },
        )
        _insert_operation(
            bind,
            kind="fund_legacy",
            currency=currency,
            mission_id=mission_id,
            phase="funding",
            details={
                "method": "legacy",
                "provider_telegram_id": provider_telegram_id,
                "currency": currency,
                "urgent": bool(urgent),
                "total": str(total),
                "commission": str(commission),
                "net": str(net),
            },
            movements=[("external", None, -total), ("escrow", mission_id, total)],
        )

    for table in WALLET_TABLES:
        for _, column in CURRENCY_COLUMNS:
            op.drop_column(table, column)


def downgrade() -> None:
    """Downgrade schema.

    Le wallet unique d'une personne revient dans sa ligne `bot_users` si elle
    en a une, sinon dans sa ligne `bot_providers` : jamais compté deux fois.
    """
    for table in WALLET_TABLES:
        for _, column in CURRENCY_COLUMNS:
            op.add_column(table, sa.Column(column, sa.Float(), nullable=False, server_default='0'))
    bind = op.get_bind()
    wallet_of = (
        "COALESCE((SELECT SUM(ledger_entries.amount) FROM ledger_entries "
        "JOIN channel_identities ON channel_identities.account_id = ledger_entries.account_id "
        "WHERE ledger_entries.account_type = 'wallet' AND ledger_entries.currency = :currency "
        "AND channel_identities.channel = 'telegram' "
        "AND channel_identities.external_id = CAST({table}.telegram_id AS VARCHAR)), 0)"
    )
    for currency, column in CURRENCY_COLUMNS:
        bind.execute(
            sa.text(f"UPDATE bot_users SET {column} = " + wallet_of.format(table="bot_users")),
            {"currency": currency},
        )
        bind.execute(
            sa.text(
                f"UPDATE bot_providers SET {column} = " + wallet_of.format(table="bot_providers")
                + " WHERE telegram_id NOT IN (SELECT telegram_id FROM bot_users)"
            ),
            {"currency": currency},
        )
    op.drop_column('bot_missions', 'provider_account_id')
    op.drop_column('bot_missions', 'client_account_id')
    op.drop_column('bot_missions', 'accepted_quote_ref')
    op.drop_column('bot_missions', 'dispute_deadline')
    op.drop_column('bot_missions', 'dispute_opened_at')
    op.drop_index(op.f('ix_ledger_entries_account_id'), table_name='ledger_entries')
    op.drop_index(op.f('ix_ledger_entries_account_type'), table_name='ledger_entries')
    op.drop_index(op.f('ix_ledger_entries_operation_id'), table_name='ledger_entries')
    op.drop_table('ledger_entries')
    op.drop_index(op.f('ix_money_operations_mission_id'), table_name='money_operations')
    op.drop_table('money_operations')
    op.drop_index(op.f('ix_channel_identities_account_id'), table_name='channel_identities')
    op.drop_table('channel_identities')
    op.drop_table('accounts')
