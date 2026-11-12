"""Contrôle d'une base restaurée (backend/app/controle_registre.py)."""

import importlib
import json
from decimal import Decimal

import pytest
from sqlalchemy import text

from backend.app import controle_registre as _controle  # noqa: F401  (pré-import)


@pytest.fixture
def base(monkeypatch, backend_db_url):
    importlib.import_module("backend.app.main")
    monkeypatch.setenv("DATABASE_URL", backend_db_url)
    monkeypatch.delenv("APP_ENV", raising=False)
    database = importlib.reload(importlib.import_module("backend.app.database"))
    importlib.reload(importlib.import_module("backend.app.models"))
    database.init_db()
    yield database
    database.engine.dispose()


def _a_jour(database):
    from backend.app import sante

    with database.engine.begin() as connexion:
        connexion.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        connexion.execute(text("INSERT INTO alembic_version VALUES (:r)"), {"r": sante.revision_attendue()})


def _crediter(database, telegram_id, montant, devise):
    from backend.app import ledger

    with database.SessionLocal() as session:
        compte = ledger.account_id_for(session, ledger.TELEGRAM, telegram_id, create=True)
        ledger.record_opening_balance(session, compte, devise, montant)
        session.commit()


def _controler(database):
    from backend.app import controle_registre

    with database.SessionLocal() as session:
        try:
            return controle_registre.controler(session)
        finally:
            session.rollback()


def test_une_base_jamais_migree_echoue(base):
    resultat = _controler(base)
    assert resultat["ok"] is False
    assert resultat["problemes_schema"]


def test_un_registre_sain_passe_avec_son_resume(base):
    _a_jour(base)
    _crediter(base, 101, Decimal("40.00"), "USD")
    _crediter(base, 102, Decimal("15000.00"), "CDF")

    resultat = _controler(base)

    assert resultat["ok"] is True, resultat["anomalies"]
    assert resultat["sommes_par_devise"] == {"CDF": "0.00", "USD": "0.00"}
    assert resultat["ecritures"] == 4
    assert resultat["derniere_ecriture"]


def test_une_ecriture_orpheline_est_detectee(base):
    from backend.app.models import LedgerEntry, MoneyOperation

    _a_jour(base)
    _crediter(base, 101, Decimal("40.00"), "USD")
    with base.SessionLocal() as session:
        operation = session.query(MoneyOperation).first()
        session.add(LedgerEntry(operation_id=operation.id, account_type="wallet", account_id=1, currency="USD", amount=Decimal("5.00")))
        session.commit()

    resultat = _controler(base)

    assert resultat["ok"] is False
    codes = {anomalie["code"] for anomalie in resultat["anomalies"]}
    assert {"unbalanced_operation", "registre_desequilibre"} <= codes


def test_le_controle_n_ecrit_rien(base):
    _a_jour(base)
    _crediter(base, 101, Decimal("40.00"), "USD")
    avant = _compter(base)
    _controler(base)
    assert _compter(base) == avant


def _compter(database):
    with database.engine.connect() as connexion:
        return {
            table: connexion.execute(text(f"SELECT count(*) FROM {table}")).scalar()
            for table in ("ledger_entries", "money_operations", "accounts")
        }


def test_la_commande_rend_un_resume_json_et_un_code_de_sortie(base, capsys):
    from backend.app import controle_registre

    assert controle_registre.main() == 1  # jamais migrée
    capsys.readouterr()
    _a_jour(base)
    assert controle_registre.main() == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True
