import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import db
from db import calculate_payment_amounts


def test_payment_amounts_are_consistent_for_urgent_and_standard_missions():
    standard = calculate_payment_amounts(100.0, "USD", urgent=False)
    urgent = calculate_payment_amounts(100.0, "USD", urgent=True)

    assert standard["commission_amount"] == 10.0
    assert urgent["commission_amount"] == 15.0
    assert standard["total_client"] == 100.0
    assert urgent["total_client"] == 100.0
    assert standard["net_provider"] == 90.0
    assert urgent["net_provider"] == 85.0


def test_client_pays_exactly_the_quote_amount_in_both_currencies():
    """Les frais Tola ayant été supprimés, le total client == le montant du devis."""
    usd = calculate_payment_amounts(100.0, "USD", urgent=False)
    cdf = calculate_payment_amounts(250000.0, "CDF", urgent=False)

    assert usd["total_client"] == 100.0
    assert cdf["total_client"] == 250000.0
    assert usd["tola_fee"] == 0.0
    assert cdf["tola_fee"] == 0.0
    assert usd["aggregator_fee"] == 0.0
    assert cdf["aggregator_fee"] == 0.0


def test_wallet_payment_debits_client_and_marks_mission_paid(tmp_path):
    db.DB_PATH = tmp_path / "test_nexis_hub.db"
    db.init_db()

    client = db.create_user(1001, "+243800000001", "Alice", language="fr")
    provider = db.create_provider(
        2002,
        "+243800000002",
        "Bob",
        ["service_plomberie"],
        ["Gombe"],
        language="fr",
    )
    mission_id = db.create_mission(
        1001,
        {
            "service": "service_plomberie",
            "urgent": False,
            "commune": "Gombe",
            "currency": "USD",
            "description": "Test wallet",
        },
    )
    quote_id = db.create_quote(mission_id, 2002, 50.0, "USD", 4, "")

    db.update_provider_status(2002, "available")
    db.create_user(1001, "+243800000001", "Alice", language="fr")

    with db.get_connection() as conn:
        conn.execute("UPDATE users SET wallet_balance_usd = ? WHERE telegram_id = ?", (200.0, 1001))

    result = db.mark_quote_paid_with_wallet(quote_id, 1001, operator="wallet")

    assert result["status"] == "success"
    assert result["quote"]["id"] == quote_id

    with db.get_connection() as conn:
        user_row = conn.execute("SELECT wallet_balance_usd FROM users WHERE telegram_id = ?", (1001,)).fetchone()
        mission_row = conn.execute("SELECT payment_status, status FROM missions WHERE id = ?", (mission_id,)).fetchone()

    assert user_row[0] == 150.0  # 200 - 50 (devis seul, plus de frais Tola)
    assert mission_row[0] == "paid_escrow"
    assert mission_row[1] == "confirmed"
