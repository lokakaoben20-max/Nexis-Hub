"""Non-regression des paiements et transitions sensibles."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import db


def setup_wallet_mission(tmp_path):
    db.DB_PATH = tmp_path / "nexis_payments_test.db"
    db.init_db()
    db.create_user(101, "+243800000101", "Client", language="fr")
    db.create_provider(202, "+243800000202", "Prestataire", ["service_plomberie"], ["Gombe"])
    mission_id = db.create_mission(
        101,
        {"service": "service_plomberie", "urgent": False, "commune": "Gombe",
         "currency": "USD", "description": "Test de securite"},
    )
    quote_id = db.create_quote(mission_id, 202, 50.0, "USD", 4)
    with db.get_connection() as conn:
        conn.execute("UPDATE users SET wallet_balance_usd = 200 WHERE telegram_id = 101")
    return mission_id, quote_id


def test_mobile_money_simulation_never_confirms_a_payment():
    with pytest.raises(ValueError, match="confirmation serveur"):
        db.mark_quote_paid(123, operator="mobile_money_simulation")


def test_wallet_payment_requires_accepted_quote(tmp_path):
    mission_id, quote_id = setup_wallet_mission(tmp_path)
    with pytest.raises(ValueError, match="accepté"):
        db.mark_quote_paid_with_wallet(quote_id)
    with db.get_connection() as conn:
        balance = conn.execute(
            "SELECT wallet_balance_usd FROM users WHERE telegram_id = 101"
        ).fetchone()[0]
        escrow_transactions = conn.execute(
            "SELECT COUNT(*) FROM transactions WHERE mission_id = ? AND type = 'escrow_in'",
            (mission_id,),
        ).fetchone()[0]
    assert balance == 200
    assert escrow_transactions == 0


def test_wallet_payment_is_processed_once(tmp_path):
    mission_id, quote_id = setup_wallet_mission(tmp_path)
    db.accept_quote(quote_id)
    first = db.mark_quote_paid_with_wallet(quote_id)
    assert first["transaction_id"] is not None

    with pytest.raises(ValueError, match="nouveau|traité"):
        db.mark_quote_paid_with_wallet(quote_id)

    with db.get_connection() as conn:
        balance = conn.execute(
            "SELECT wallet_balance_usd FROM users WHERE telegram_id = 101"
        ).fetchone()[0]
        count = conn.execute(
            "SELECT COUNT(*) FROM transactions WHERE mission_id = ? AND type = 'escrow_in'",
            (mission_id,),
        ).fetchone()[0]
    assert balance == 148.5
    assert count == 1


def test_release_requires_completed_provider_work_and_occurs_once(tmp_path):
    mission_id, quote_id = setup_wallet_mission(tmp_path)
    db.accept_quote(quote_id)
    db.mark_quote_paid_with_wallet(quote_id)

    with pytest.raises(ValueError, match="libérable"):
        db.release_payment(mission_id)

    db.start_mission(mission_id, 202)
    db.finish_mission(mission_id, 202)
    result = db.release_payment(mission_id)
    assert result["payment_status"] == "released"

    with pytest.raises(ValueError, match="libérable"):
        db.release_payment(mission_id)

    with db.get_connection() as conn:
        balance = conn.execute(
            "SELECT wallet_balance_usd FROM providers WHERE telegram_id = 202"
        ).fetchone()[0]
        count = conn.execute(
            "SELECT COUNT(*) FROM transactions WHERE mission_id = ? AND type = 'release'",
            (mission_id,),
        ).fetchone()[0]
    assert balance == 45.0
    assert count == 1


def test_mission_cannot_finish_before_it_starts(tmp_path):
    mission_id, quote_id = setup_wallet_mission(tmp_path)
    db.accept_quote(quote_id)
    db.mark_quote_paid_with_wallet(quote_id)
    with pytest.raises(ValueError, match="en cours"):
        db.finish_mission(mission_id, 202)
