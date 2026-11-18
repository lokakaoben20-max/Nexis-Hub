"""Isolated PostgreSQL relational and transaction smoke test.

Only run against disposable CI database. Never uses real payments or user data.
"""
import os
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import Mission, Provider, Quote, Transaction, User
from backend.app.postgres import get_engine


def main():
    url = os.environ.get("NEXIS_DATABASE_URL", "")
    if "127.0.0.1" not in url or "/nexis_ci" not in url:
        raise RuntimeError("Refusing to run smoke test outside isolated CI database")

    engine = get_engine()
    with Session(engine) as session:
        with session.begin():
            user = User(telegram_id=900000001, phone_number="000", language="fr",
                        wallet_balance_usd=Decimal("100.0000"),
                        wallet_balance_cdf=Decimal("0"))
            provider = Provider(telegram_id=900000002, phone_number="000",
                                full_name="CI provider", services="[]", communes="[]",
                                status="available", wallet_balance_usd=Decimal("0"),
                                wallet_balance_cdf=Decimal("0"))
            session.add_all([user, provider])
            session.flush()
            mission = Mission(user_id=user.id, provider_id=provider.id,
                              service="CI test", commune="Gombe", description="Synthetic",
                              currency="USD", status="pending", payment_status="unpaid",
                              total_client=Decimal("12.5000"),
                              net_provider=Decimal("10.0000"))
            session.add(mission)
            session.flush()
            quote = Quote(mission_id=mission.id, provider_id=provider.id,
                          amount=Decimal("12.5000"), currency="USD", delay_hours=2)
            session.add(quote)
            session.flush()
            tx = Transaction(mission_id=mission.id, quote_id=quote.id,
                             type="ci_simulated", amount=Decimal("12.5000"),
                             currency="USD", status="pending")
            session.add(tx)
            session.flush()
            assert session.scalar(select(Transaction).where(Transaction.quote_id == quote.id)).id == tx.id
            assert session.get(User, user.id).wallet_balance_usd == Decimal("100.0000")
            assert session.get(Transaction, tx.id).status == "pending"
            # Deliberately roll back: this is not a payment capture or escrow release.
            session.rollback()

    with Session(engine) as session:
        assert session.scalar(select(User).where(User.telegram_id == 900000001)) is None
        assert session.scalar(select(Transaction).where(Transaction.type == "ci_simulated")) is None
    print("Synthetic relational inserts and rollback verified")


if __name__ == "__main__":
    main()
