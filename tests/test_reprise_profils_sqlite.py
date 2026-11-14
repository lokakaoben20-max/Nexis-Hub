"""Reprise unique des profils de l'ancien fichier SQLite dans le backend
(`python -m outils.reprise_profils_sqlite`) : rapport d'abord, tout ou rien,
conflit = arrêt sans rien écrire, relance sans effet."""

import hashlib
import json
import sqlite3

import pytest

from outils import reprise_profils_sqlite as reprise

SCHEMA = """
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT, telegram_id INTEGER UNIQUE NOT NULL, phone_number TEXT NOT NULL,
    first_name TEXT, language TEXT DEFAULT 'fr', created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE providers (
    id INTEGER PRIMARY KEY AUTOINCREMENT, telegram_id INTEGER UNIQUE NOT NULL, phone_number TEXT NOT NULL,
    full_name TEXT NOT NULL, services TEXT NOT NULL, communes TEXT NOT NULL, badge TEXT DEFAULT 'pending',
    rating REAL DEFAULT 0, total_missions INTEGER DEFAULT 0, status TEXT DEFAULT 'available',
    is_verified INTEGER DEFAULT 0, is_suspended INTEGER DEFAULT 0, consecutive_ignored INTEGER DEFAULT 0,
    language TEXT DEFAULT 'fr', id_document_file_id TEXT, selfie_file_id TEXT, portfolio_file_ids TEXT DEFAULT '[]',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE service_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT, provider_id INTEGER NOT NULL, service_name TEXT NOT NULL,
    description TEXT NOT NULL, status TEXT DEFAULT 'pending', admin_note TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP, backend_request_id INTEGER
);
"""


class AncienneBase:
    """Un fichier SQLite comme celui de db.py."""

    def __init__(self, path):
        self.path = path
        with sqlite3.connect(path) as conn:
            conn.executescript(SCHEMA)

    def client(self, telegram_id, first_name="Cliente", phone="+243810000001", language="fr", created_at="2026-10-01 09:00:00"):
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                "INSERT INTO users (telegram_id, phone_number, first_name, language, created_at) VALUES (?, ?, ?, ?, ?)",
                (telegram_id, phone, first_name, language, created_at),
            )

    def provider(self, telegram_id, full_name="Prestataire", *, services=("service_plomberie",), communes=("Gombe",), status="available",
                 verified=True, suspended=False, ignored=0, badge=None, language="fr", created_at="2026-10-02 10:00:00"):
        with sqlite3.connect(self.path) as conn:
            cursor = conn.execute(
                "INSERT INTO providers (telegram_id, phone_number, full_name, services, communes, status, is_verified, is_suspended,"
                " consecutive_ignored, badge, language, id_document_file_id, selfie_file_id, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (telegram_id, f"+24382{telegram_id:07d}", full_name, json.dumps(list(services)), json.dumps(list(communes)), status,
                 int(verified), int(suspended), ignored, badge or ("verified" if verified else "pending"), language,
                 f"id-{telegram_id}", f"selfie-{telegram_id}", created_at),
            )
            return cursor.lastrowid

    def service_request(self, provider_row_id, name="Soudure", status="pending", backend_request_id=None, note=None):
        with sqlite3.connect(self.path) as conn:
            cursor = conn.execute(
                "INSERT INTO service_requests (provider_id, service_name, description, status, admin_note, created_at, backend_request_id)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (provider_row_id, name, "Soudure à l'arc et portails.", status, note, "2026-10-03 11:00:00", backend_request_id),
            )
            return cursor.lastrowid

    def empreinte(self):
        return hashlib.sha256(self.path.read_bytes()).hexdigest()


@pytest.fixture
def ancienne(tmp_path):
    return AncienneBase(tmp_path / "nexis_hub.db")


def _reprendre(live, ancienne, appliquer=False):
    with live.database.SessionLocal() as session:
        return reprise.reprendre(session, ancienne.path, appliquer=appliquer)


def _provider(live, telegram_id):
    return live.profile(telegram_id)["provider"]


def _requests(live):
    from backend.app.models import ProviderServiceRequest

    with live.database.SessionLocal() as session:
        return [(r.service_name, r.status, r.admin_note) for r in session.query(ProviderServiceRequest).order_by(ProviderServiceRequest.id)]


def test_the_report_writes_nothing(live_backend, ancienne):
    ancienne.client(101)
    ancienne.provider(102)

    rapport = _reprendre(live_backend, ancienne)

    assert len(rapport.a_faire) == 2 and rapport.conflits == []
    assert "Relancez avec --appliquer" in rapport.texte()
    assert live_backend.profile(101)["profile_type"] == "guest"
    assert live_backend.profile(102)["profile_type"] == "guest"


def test_every_profile_is_taken_over_with_its_status(live_backend, ancienne):
    ancienne.client(101, first_name="Laura", phone="+243810000101", language="ln")
    ancienne.provider(102, "Disponible")
    ancienne.provider(103, "Hors ligne", status="offline")
    ancienne.provider(104, "En pause", status="paused", ignored=3)
    ancienne.provider(105, "Suspendu", suspended=True)
    ancienne.provider(106, "Se dit disponible", verified=False, status="available")
    ancienne.provider(107, "Refusé", verified=False, status="rejected")
    ancienne.client(108, first_name="Double")
    ancienne.provider(108, "Double rôle", language="fr")

    rapport = _reprendre(live_backend, ancienne, appliquer=True)

    assert rapport.conflits == [] and rapport.applique
    laura = live_backend.profile(101)
    assert (laura["client"]["first_name"], laura["client"]["phone_number"], laura["language"]) == ("Laura", "+243810000101", "ln")
    statuses = {tg: (_provider(live_backend, tg)["status"], _provider(live_backend, tg)["is_suspended"]) for tg in range(102, 108)}
    assert statuses == {
        102: ("available", False),
        103: ("offline", False),
        104: ("paused", False),
        105: ("available", True),
        106: ("pending_verification", False),
        107: ("rejected", False),
    }
    assert _provider(live_backend, 104)["consecutive_ignored"] == 3
    assert _provider(live_backend, 102)["id_document_file_id"] == "id-102"
    double = live_backend.profile(108)
    assert double["client"] is not None and double["provider"] is not None, "un seul compte, les deux rôles"


def test_only_verified_available_providers_are_alerted_after_the_takeover(live_backend, ancienne):
    ancienne.provider(102, "Disponible")
    ancienne.provider(105, "Suspendu", suspended=True)
    ancienne.provider(106, "Se dit disponible", verified=False)
    _reprendre(live_backend, ancienne, appliquer=True)

    mission_id = live_backend.new_mission(42, service="service_plomberie", commune="Gombe")

    assert live_backend.alerted(mission_id) == [102]


def test_the_registration_date_is_kept_for_the_ranking(live_backend, ancienne):
    ancienne.provider(102, "Ancien", created_at="2026-09-01 08:00:00")
    _reprendre(live_backend, ancienne, appliquer=True)
    live_backend.provider(103, "Nouveau")

    mission_id = live_backend.new_mission(42, service="service_plomberie", commune="Gombe")

    assert live_backend.alerted(mission_id) == [102, 103], "à score égal, le plus ancien d'abord"


def test_a_second_run_finds_nothing_to_do(live_backend, ancienne):
    ancienne.client(101)
    row = ancienne.provider(102, status="paused", ignored=3)
    ancienne.service_request(row, "Soudure")
    ancienne.service_request(row, "Vitrerie", status="rejected", note="Pas pour le moment")
    _reprendre(live_backend, ancienne, appliquer=True)

    rapport = _reprendre(live_backend, ancienne, appliquer=True)

    assert (rapport.a_faire, rapport.conflits, rapport.applique) == ([], [], False)
    assert "Rien à faire" in rapport.texte()
    assert _requests(live_backend) == [("Soudure", "pending", None), ("Vitrerie", "rejected", "Pas pour le moment")]


def test_sqlite_wins_for_what_it_held_and_the_report_says_it(live_backend, ancienne):
    """Disponibilité réglée dans la Mini App, services changés quand le
    backend ne répondait pas : SQLite faisait foi."""
    live_backend.provider(102, "Ancien nom", services=["service_electricite"])
    ancienne.provider(102, "Nouveau nom", status="offline", services=("service_plomberie", "service_electricite"))

    rapport = _reprendre(live_backend, ancienne, appliquer=True)

    assert rapport.a_faire == ["Telegram 102 (Nouveau nom) : profil prestataire mis à jour, statut available → offline"]
    provider = _provider(live_backend, 102)
    assert (provider["full_name"], provider["status"]) == ("Nouveau nom", "offline")
    assert provider["services"] == ["service_plomberie", "service_electricite"]


def test_a_conflict_stops_everything(live_backend, ancienne):
    live_backend.provider(102, verified=False)
    live_backend.reject_provider(102)
    ancienne.provider(102, verified=True)
    ancienne.client(101)

    rapport = _reprendre(live_backend, ancienne, appliquer=True)

    assert rapport.conflits == ["Telegram 102 (Prestataire) : vérifié dans SQLite seulement (de l'autre côté : « rejected »)"]
    assert not rapport.applique
    assert "Rien n'a été écrit" in rapport.texte()
    assert live_backend.profile(101)["profile_type"] == "guest", "même les profils sans conflit attendent"
    assert _provider(live_backend, 102)["status"] == "rejected"


@pytest.mark.parametrize(
    "setup, expected",
    [
        (lambda a: a.provider(102, services=("service_qui_nexiste_pas",)), "service(s) absent(s) du catalogue : service_qui_nexiste_pas"),
        (lambda a: a.provider(102, communes=("Bruxelles",)), "commune(s) absente(s) du catalogue : Bruxelles"),
        (lambda a: (a.client(102, language="ln"), a.provider(102, language="en")), "deux langues différentes (en, ln)"),
        (lambda a: a.provider(102, badge="partner"), "badge « partner » à attribuer à la main"),
        (lambda a: a.provider(102, status="busy"), "statut inconnu « busy »"),
    ],
)
def test_data_the_backend_cannot_take_is_a_conflict(live_backend, ancienne, setup, expected):
    setup(ancienne)

    rapport = _reprendre(live_backend, ancienne, appliquer=True)

    assert len(rapport.conflits) == 1 and expected in rapport.conflits[0]
    assert live_backend.profile(102)["profile_type"] == "guest"


def test_a_local_decision_on_a_copied_proposal_is_taken_over(live_backend, ancienne):
    from telegram_bot import backend_client

    import asyncio

    live_backend.provider(102)
    backend_id = asyncio.run(backend_client.propose_service(102, "Soudure", "Soudure à l'arc et portails."))["id"]
    row = ancienne.provider(102)
    ancienne.service_request(row, "Soudure", status="accepted", backend_request_id=backend_id, note="Validé")

    rapport = _reprendre(live_backend, ancienne, appliquer=True)

    assert rapport.conflits == []
    assert _requests(live_backend) == [("Soudure", "accepted", "Validé")]


def test_a_proposal_decided_differently_is_a_conflict(live_backend, ancienne):
    from telegram_bot import backend_client

    import asyncio

    live_backend.grant_admin(999)
    live_backend.provider(102)
    backend_id = asyncio.run(backend_client.propose_service(102, "Soudure", "Soudure à l'arc et portails."))["id"]
    asyncio.run(backend_client.admin_decide_service_request(999, backend_id, "rejected", "Non"))
    ancienne.service_request(ancienne.provider(102), "Soudure", status="accepted", backend_request_id=backend_id)

    rapport = _reprendre(live_backend, ancienne, appliquer=True)

    assert rapport.conflits == ["Proposition SQLite n° 1 (Soudure) : « accepted » dans SQLite, « rejected » dans le backend"]
    assert _requests(live_backend) == [("Soudure", "rejected", "Non")]


def test_the_sqlite_file_is_never_written(live_backend, ancienne):
    ancienne.client(101)
    ancienne.provider(102)
    before = ancienne.empreinte()

    _reprendre(live_backend, ancienne, appliquer=True)

    assert ancienne.empreinte() == before


def test_the_command_line(live_backend, ancienne, tmp_path, capsys):
    ancienne.provider(102, services=("service_qui_nexiste_pas",))

    assert reprise.main([str(tmp_path / "absent.db")]) == 2
    assert reprise.main([str(ancienne.path), "--appliquer"]) == 1
    assert "Conflits : 1" in capsys.readouterr().out

    ancienne_ok = AncienneBase(tmp_path / "ok.db")
    ancienne_ok.client(101)
    assert reprise.main([str(ancienne_ok.path)]) == 0
    assert reprise.main([str(ancienne_ok.path), "--appliquer"]) == 0
    assert "Reprise faite" in capsys.readouterr().out
    assert live_backend.profile(101)["client"] is not None
