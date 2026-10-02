from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backfill_wallets_to_backend as backfill
import db
from backend.app.database import Base
from backend.app.models import BotProvider, BotUser


def _setup(tmp_path, monkeypatch):
    db.DB_PATH = tmp_path / "test_nexis_hub.db"
    db.init_db()
    engine = create_engine(f"sqlite:///{tmp_path / 'backend.db'}", future=True)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(backfill, "SessionLocal", session_factory)

    db.create_provider(3001, "+243800003001", "Prestataire", ["service_plomberie"], ["Gombe"], language="fr")
    with db.get_connection() as conn:
        conn.execute("UPDATE providers SET wallet_balance_usd = 180.0 WHERE telegram_id = 3001")
    with session_factory() as session:
        session.add(BotProvider(telegram_id=3001, full_name="Prestataire", phone_number="+243800003001"))
        session.commit()
    return session_factory


def _backend_usd(session_factory):
    with session_factory() as session:
        return session.get(BotProvider, 3001).wallet_balance_usd


def test_dry_run_reports_without_writing(tmp_path, monkeypatch, capsys):
    session_factory = _setup(tmp_path, monkeypatch)

    assert backfill.main(apply=False) == 0

    assert "prestataire 3001 : wallet_balance_usd 0.0 -> 180.0" in capsys.readouterr().out
    assert _backend_usd(session_factory) == 0.0


def test_apply_copies_db_wallet_to_backend(tmp_path, monkeypatch):
    session_factory = _setup(tmp_path, monkeypatch)

    assert backfill.main(apply=True) == 0

    assert _backend_usd(session_factory) == 180.0


def test_refuses_while_money_moves_are_still_queued(tmp_path, monkeypatch):
    # Sinon le mouvement en file serait compté deux fois : copie puis rejeu.
    session_factory = _setup(tmp_path, monkeypatch)
    db.enqueue_backend_call("/api/bot/missions/status", {"mission_id": 1, "status": "completed"})

    assert backfill.main(apply=True) == 1

    assert _backend_usd(session_factory) == 0.0


def test_account_unknown_to_backend_is_skipped(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    db.create_user(3002, "+243800003002", "Client", language="fr")

    assert backfill.main(apply=True) == 0  # pas d'erreur, juste ignoré
