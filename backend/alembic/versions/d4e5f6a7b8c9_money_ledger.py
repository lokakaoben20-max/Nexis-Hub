"""registre d'argent : money_operations + ledger_entries, soldes repris

Le backend devient la seule source de vérité de l'argent (CONCEPTION_ARGENT.md) :
- crée les tables du registre et les colonnes de litige des missions ;
- reprend chaque solde wallet existant en « solde d'ouverture » ;
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
WALLET_TABLES = (("bot_users", "client"), ("bot_providers", "provider"))
CURRENCY_COLUMNS = (("USD", "wallet_balance_usd"), ("CDF", "wallet_balance_cdf"))


def _money(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(CENT, rounding=ROUND_HALF_UP)


def _insert_operation(bind, *, kind, currency, movements, mission_id=None, phase=None, details=None):
    now = datetime.utcnow()
    result = bind.execute(
        sa.text(
            "INSERT INTO money_operations (kind, mission_id, phase, actor_telegram_id, reference, details, created_at) "
            "VALUES (:kind, :mission_id, :phase, NULL, NULL, :details, :created_at) RETURNING id"
        ),
        {"kind": kind, "mission_id": mission_id, "phase": phase, "details": json.dumps(details or {}), "created_at": now},
    )
    operation_id = result.scalar_one()
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

    bind = op.get_bind()
    for table, account_type in WALLET_TABLES:
        rows = bind.execute(sa.text(f"SELECT telegram_id, wallet_balance_usd, wallet_balance_cdf FROM {table}")).fetchall()
        for telegram_id, usd, cdf in rows:
            for currency, value in (("USD", usd), ("CDF", cdf)):
                amount = _money(value)
                if amount == 0:
                    continue
                _insert_operation(
                    bind,
                    kind="opening_balance",
                    currency=currency,
                    details={"account_type": account_type, "telegram_id": telegram_id},
                    movements=[("external", None, -amount), (account_type, telegram_id, amount)],
                )

    open_escrows = bind.execute(
        sa.text(
            "SELECT mission_id, currency, total_client, commission_amount, net_provider, provider_telegram_id, urgent "
            "FROM bot_missions WHERE payment_status = 'paid_escrow' "
            "AND (status IS NULL OR status NOT IN ('completed', 'cancelled'))"
        )
    ).fetchall()
    for mission_id, currency, total, commission, net, provider_telegram_id, urgent in open_escrows:
        total, commission, net = _money(total), _money(commission), _money(net)
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

    for table, _ in WALLET_TABLES:
        for _, column in CURRENCY_COLUMNS:
            op.drop_column(table, column)


def downgrade() -> None:
    """Downgrade schema."""
    for table, _ in WALLET_TABLES:
        for _, column in CURRENCY_COLUMNS:
            op.add_column(table, sa.Column(column, sa.Float(), nullable=False, server_default='0'))
    bind = op.get_bind()
    for table, account_type in WALLET_TABLES:
        for currency, column in CURRENCY_COLUMNS:
            bind.execute(
                sa.text(
                    f"UPDATE {table} SET {column} = COALESCE(("
                    "SELECT SUM(amount) FROM ledger_entries "
                    f"WHERE account_type = :account_type AND account_id = {table}.telegram_id AND currency = :currency"
                    "), 0)"
                ),
                {"account_type": account_type, "currency": currency},
            )
    op.drop_column('bot_missions', 'accepted_quote_ref')
    op.drop_column('bot_missions', 'dispute_deadline')
    op.drop_column('bot_missions', 'dispute_opened_at')
    op.drop_index(op.f('ix_ledger_entries_account_id'), table_name='ledger_entries')
    op.drop_index(op.f('ix_ledger_entries_account_type'), table_name='ledger_entries')
    op.drop_index(op.f('ix_ledger_entries_operation_id'), table_name='ledger_entries')
    op.drop_table('ledger_entries')
    op.drop_index(op.f('ix_money_operations_mission_id'), table_name='money_operations')
    op.drop_table('money_operations')
