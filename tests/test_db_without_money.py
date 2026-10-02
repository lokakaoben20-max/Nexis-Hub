"""db.py ne contient plus d'argent (CONCEPTION_ARGENT.md) : nettoyage de
l'ancien stockage au démarrage, sans jamais perdre un mouvement en attente."""

import sqlite3

import pytest

import db


def _legacy_db(path, pending_outbox=0):
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, telegram_id INTEGER UNIQUE NOT NULL, phone_number TEXT NOT NULL, wallet_balance_usd REAL DEFAULT 0, wallet_balance_cdf REAL DEFAULT 0)")
    conn.execute("CREATE TABLE backend_outbox (id INTEGER PRIMARY KEY, path TEXT, payload TEXT)")
    for index in range(pending_outbox):
        conn.execute("INSERT INTO backend_outbox (path, payload) VALUES ('/api/bot/payments', '{}')")
    conn.commit()
    conn.close()


def _columns(table):
    with db.get_connection() as conn:
        return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def test_startup_drops_the_old_balances_and_the_empty_replay_queue(tmp_path):
    db.DB_PATH = tmp_path / "legacy.db"
    _legacy_db(db.DB_PATH)

    db.init_db()

    assert "wallet_balance_usd" not in _columns("users")
    assert "wallet_balance_usd" not in _columns("providers")
    with db.get_connection() as conn:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert "backend_outbox" not in tables


def test_startup_refuses_to_lose_money_moves_still_waiting_for_the_backend(tmp_path):
    db.DB_PATH = tmp_path / "legacy.db"
    _legacy_db(db.DB_PATH, pending_outbox=2)

    with pytest.raises(RuntimeError, match="2 mouvement"):
        db.init_db()


def test_a_provider_cannot_quote_their_own_mission(tmp_path):
    db.DB_PATH = tmp_path / "quotes.db"
    db.init_db()
    db.create_user(7, "+243800000007", "Ben", language="fr")
    db.create_provider(7, "+243800000007", "Ben", ["service_plomberie"], ["Gombe"], language="fr")
    mission_id = db.create_mission(7, {"service": "service_plomberie", "commune": "Gombe", "currency": "USD", "description": "x", "urgent": False})

    with pytest.raises(ValueError, match="propre mission"):
        db.create_quote(mission_id, 7, 10.0, "USD", 1, "")
