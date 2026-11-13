"""Règles des profils (backend/app/profils.py) et contraintes de la base.

Chaque transition de statut d'un prestataire, permise ou refusée ; le
catalogue ; l'éligibilité à une mission ; le compteur de refus. Les
contraintes de la base sont vérifiées en écrivant directement des états
interdits : elles tiennent même si le code se trompait.

Classes prises dans `profils` lui-même, pour la même raison que
test_ledger.py (d'autres fichiers rechargent `backend.app.models`).
"""

from datetime import datetime

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from backend.app import ledger, profils
from backend.tests import profils_de_test

ProviderProfile = profils.ProviderProfile
ProviderService = profils.ProviderService
ProviderCommune = profils.ProviderCommune
NexisAccount = profils.NexisAccount


@pytest.fixture
def db(backend_db_url):
    engine = create_engine(backend_db_url, future=True)
    if engine.dialect.name == "sqlite":
        # SQLite n'applique les clés étrangères qu'à la demande, connexion par
        # connexion : on les active pour que les contraintes soient vérifiées
        # ici comme sur Postgres.
        event.listen(engine, "connect", lambda connection, _: connection.execute("PRAGMA foreign_keys=ON"))
    NexisAccount.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    profils_de_test.ensure_catalogue(session)
    session.commit()
    yield session
    session.close()
    engine.dispose()


def account(db, telegram_id):
    account_id = ledger.account_id_for(db, ledger.TELEGRAM, telegram_id, create=True)
    db.commit()
    return account_id


def register(db, telegram_id, **fields):
    values = {
        "full_name": "Jean Prestataire",
        "phone_number": "+243810000001",
        "services": ["service_plomberie"],
        "communes": ["Gombe"],
    }
    values.update(fields)
    provider, created = profils.register_provider(db, account(db, telegram_id), **values)
    db.commit()
    return provider, created


def refused(code, action, *args, **kwargs):
    with pytest.raises(profils.ProfileRefused) as raised:
        action(*args, **kwargs)
    assert raised.value.code == code
    return raised.value


# --- Inscription --------------------------------------------------------------


def test_a_new_provider_waits_for_verification(db):
    provider, created = register(db, 7)

    assert created
    assert provider.status == "pending_verification"
    assert provider.verified_at is None
    assert provider.badge == "pending"
    assert profils.provider_services(db, provider.account_id) == ["service_plomberie"]
    assert profils.provider_communes(db, provider.account_id) == ["Gombe"]
    assert db.get(NexisAccount, provider.account_id).roles == ["provider"]


def test_registering_again_never_changes_the_status_of_a_verified_provider(db):
    provider, _ = register(db, 7)
    profils.verify_provider(db, provider.account_id)
    profils.set_own_availability(db, provider.account_id, "offline")
    db.commit()

    provider, created = register(db, 7, full_name="Jean P.", services=["service_nettoyage"], communes=["Lemba"])

    assert not created
    assert provider.status == "offline"
    assert provider.verified_at is not None
    assert provider.full_name == "Jean P."
    assert profils.provider_services(db, provider.account_id) == ["service_nettoyage"]
    assert profils.provider_communes(db, provider.account_id) == ["Lemba"]


def test_a_rejected_provider_who_registers_again_waits_for_a_new_verification(db):
    provider, _ = register(db, 7)
    profils.reject_provider(db, provider.account_id)
    db.commit()

    provider, _ = register(db, 7)

    assert provider.status == "pending_verification"


def test_documents_already_given_are_kept_when_none_are_sent(db):
    register(db, 7, id_document_file_id="piece", selfie_file_id="selfie", portfolio_file_ids=["p1"])
    provider, _ = register(db, 7)

    assert (provider.id_document_file_id, provider.selfie_file_id, provider.portfolio_file_ids) == ("piece", "selfie", ["p1"])


@pytest.mark.parametrize(
    "fields, code",
    [
        ({"services": []}, "services_required"),
        ({"services": ["service_inconnu"]}, "unknown_service"),
        ({"services": "service_plomberie"}, "invalid_services"),
        ({"communes": []}, "communes_required"),
        ({"communes": ["Kintambo"]}, "unknown_commune"),
        ({"full_name": "   "}, "invalid_name"),
        ({"full_name": "x" * 101}, "invalid_name"),
        ({"phone_number": "1" * 51}, "invalid_phone"),
        ({"id_document_file_id": ""}, "invalid_document"),
        ({"portfolio_file_ids": ["p"] * 21}, "invalid_document"),
    ],
)
def test_a_registration_with_invalid_data_is_refused_and_writes_nothing(db, fields, code):
    account_id = account(db, 7)
    values = {"full_name": "Jean", "phone_number": None, "services": ["service_plomberie"], "communes": ["Gombe"]}
    values.update(fields)

    refused(code, profils.register_provider, db, account_id, **values)
    db.rollback()

    assert profils.provider_profile(db, account_id) is None


def test_duplicate_services_and_communes_are_kept_once(db):
    provider, _ = register(db, 7, services=["service_plomberie", "service_plomberie"], communes=["Gombe", "Gombe"])

    assert profils.provider_services(db, provider.account_id) == ["service_plomberie"]
    assert profils.provider_communes(db, provider.account_id) == ["Gombe"]


def test_module_b_comes_from_the_catalogue(db):
    provider, _ = register(db, 7, services=["service_nettoyage"])
    assert profils.provider_module(db, provider.account_id) == "A"

    profils.set_provider_services(db, provider.account_id, ["service_nettoyage", "service_electricite"])
    assert profils.provider_module(db, provider.account_id) == "B"


# --- Statuts ------------------------------------------------------------------


def test_admin_verification_makes_the_provider_available_and_is_idempotent(db):
    provider, _ = register(db, 7)

    provider = profils.verify_provider(db, provider.account_id)
    first_verification = provider.verified_at
    assert (provider.status, provider.badge) == ("available", "verified")

    profils.set_own_availability(db, provider.account_id, "offline")
    provider = profils.verify_provider(db, provider.account_id)
    assert provider.status == "offline", "une seconde validation ne change rien"
    assert provider.verified_at == first_verification


def test_a_rejected_provider_cannot_be_verified_before_registering_again(db):
    provider, _ = register(db, 7)
    profils.reject_provider(db, provider.account_id)

    refused("provider_not_pending", profils.verify_provider, db, provider.account_id)


def test_a_verified_provider_cannot_be_rejected(db):
    provider, _ = register(db, 7)
    profils.verify_provider(db, provider.account_id)

    refused("provider_not_pending", profils.reject_provider, db, provider.account_id)


def test_rejecting_twice_changes_nothing(db):
    provider, _ = register(db, 7)
    profils.reject_provider(db, provider.account_id)

    assert profils.reject_provider(db, provider.account_id).status == "rejected"


@pytest.mark.parametrize("status", ["available", "offline"])
def test_an_unverified_provider_can_never_make_himself_available(db, status):
    provider, _ = register(db, 7)

    refused("provider_not_verified", profils.set_own_availability, db, provider.account_id, status)
    profils.reject_provider(db, provider.account_id)
    refused("provider_not_verified", profils.set_own_availability, db, provider.account_id, status)


@pytest.mark.parametrize("status", ["paused", "pending_verification", "rejected", "suspended", "n'importe quoi"])
def test_a_provider_only_chooses_available_or_offline(db, status):
    provider, _ = register(db, 7)
    profils.verify_provider(db, provider.account_id)

    refused("status_not_allowed", profils.set_own_availability, db, provider.account_id, status)


def test_a_suspended_provider_cannot_change_his_availability(db):
    provider, _ = register(db, 7)
    profils.verify_provider(db, provider.account_id)
    profils.set_suspended(db, provider.account_id, True)

    refused("provider_suspended", profils.set_own_availability, db, provider.account_id, "available")


def test_suspension_keeps_the_status_and_is_idempotent(db):
    provider, _ = register(db, 7)
    profils.verify_provider(db, provider.account_id)
    profils.set_own_availability(db, provider.account_id, "offline")

    provider = profils.set_suspended(db, provider.account_id, True)
    suspended_at = provider.suspended_at
    assert (provider.is_suspended, provider.status) == (True, "offline")
    assert profils.set_suspended(db, provider.account_id, True).suspended_at == suspended_at

    provider = profils.set_suspended(db, provider.account_id, False)
    assert (provider.is_suspended, provider.suspended_at, provider.status) == (False, None, "offline")


def test_unknown_provider(db):
    account_id = account(db, 7)
    for action in (profils.verify_provider, profils.reject_provider, profils.record_declined_alert):
        refused("provider_not_found", action, db, account_id)
    refused("provider_not_found", profils.set_own_availability, db, account_id, "available")
    refused("provider_not_found", profils.set_suspended, db, account_id, True)
    refused("provider_not_found", profils.set_provider_services, db, account_id, ["service_plomberie"])


# --- Refus de missions -------------------------------------------------------


def test_the_third_declined_mission_in_a_row_pauses_an_available_provider(db):
    provider, _ = register(db, 7)
    profils.verify_provider(db, provider.account_id)

    for expected in (1, 2):
        provider = profils.record_declined_alert(db, provider.account_id)
        assert (provider.consecutive_ignored, provider.status) == (expected, "available")
    provider = profils.record_declined_alert(db, provider.account_id)
    assert (provider.consecutive_ignored, provider.status) == (3, "paused")


def test_coming_back_from_pause_resets_the_counter(db):
    provider, _ = register(db, 7)
    profils.verify_provider(db, provider.account_id)
    for _ in range(3):
        profils.record_declined_alert(db, provider.account_id)

    provider = profils.set_own_availability(db, provider.account_id, "available")
    assert (provider.status, provider.consecutive_ignored) == ("available", 0)
    provider = profils.record_declined_alert(db, provider.account_id)
    assert provider.status == "available", "un seul refus après la reprise ne remet pas en pause"


def test_declines_never_make_an_offline_or_unverified_provider_available(db):
    pending, _ = register(db, 7)
    for _ in range(4):
        pending = profils.record_declined_alert(db, pending.account_id)
    assert pending.status == "pending_verification"

    offline, _ = register(db, 8)
    profils.verify_provider(db, offline.account_id)
    profils.set_own_availability(db, offline.account_id, "offline")
    for _ in range(4):
        offline = profils.record_declined_alert(db, offline.account_id)
    assert offline.status == "offline"


def test_answering_a_mission_resets_the_counter(db):
    provider, _ = register(db, 7)
    profils.verify_provider(db, provider.account_id)
    profils.record_declined_alert(db, provider.account_id)
    profils.record_declined_alert(db, provider.account_id)

    assert profils.reset_declined_alerts(db, provider.account_id).consecutive_ignored == 0


# --- Matching -----------------------------------------------------------------


def eligible(db, service="service_plomberie", commune="Gombe", **kwargs):
    return [ledger.telegram_id_of(db, provider.account_id) for provider in profils.eligible_providers(db, service, commune, **kwargs)]


def test_only_verified_available_unsuspended_providers_of_that_service_and_commune_are_eligible(db):
    profils_de_test.provider(db, 1)  # éligible
    profils_de_test.provider(db, 2, verified=False)  # en attente
    profils_de_test.provider(db, 3, services=("service_nettoyage",))  # autre service
    profils_de_test.provider(db, 4, communes=("Lemba",))  # autre commune
    offline = profils_de_test.provider(db, 5)
    profils.set_own_availability(db, offline.account_id, "offline")
    suspended = profils_de_test.provider(db, 6)
    profils.set_suspended(db, suspended.account_id, True)
    paused = profils_de_test.provider(db, 7)
    for _ in range(3):
        profils.record_declined_alert(db, paused.account_id)
    rejected = profils_de_test.provider(db, 8, verified=False)
    profils.reject_provider(db, rejected.account_id)
    profils_de_test.provider(db, 9, services=("service_nettoyage", "service_plomberie"), communes=("Lemba", "Gombe"))
    db.commit()

    assert eligible(db) == [1, 9]


def test_the_client_is_never_offered_his_own_mission(db):
    provider = profils_de_test.provider(db, 1)
    profils_de_test.provider(db, 2)

    assert eligible(db, exclude_account_id=provider.account_id) == [2]


def test_eligible_providers_are_ranked_by_score_then_by_registration(db):
    profils_de_test.provider(db, 1)
    profils_de_test.provider(db, 2, average_rating=4.0)
    profils_de_test.provider(db, 3, badge="partner", average_rating=5.0, total_missions=10, success_rate=100.0)
    profils_de_test.provider(db, 4)

    assert eligible(db) == [3, 2, 1, 4]


def test_rank_orders_known_providers_and_omits_the_others(db):
    first = profils_de_test.provider(db, 1)
    best = profils_de_test.provider(db, 2, average_rating=5.0)
    unknown = account(db, 3)

    assert profils.rank(db, [first.account_id, unknown, best.account_id]) == [best.account_id, first.account_id]
    assert profils.rank(db, []) == []


# --- Client et langue ---------------------------------------------------------


def test_client_profile_and_language(db):
    account_id = account(db, 42)
    client, created = profils.save_client_profile(db, account_id, first_name="  Ben   L ", phone_number="+243 81")
    assert created and client.first_name == "Ben L"
    client, created = profils.save_client_profile(db, account_id, first_name="Ben")
    assert not created and client.phone_number == "+243 81", "un numéro absent ne l'efface pas"

    profils.set_language(db, account_id, "ln")
    assert profils.language_of(db, account_id) == "ln"
    refused("invalid_language", profils.set_language, db, account_id, "de")
    refused("client_not_found", profils.rename_client, db, account(db, 43), "X")
    assert profils.language_of(db, None) == "fr"


# --- Contraintes de la base ---------------------------------------------------


def _raw_provider(db, telegram_id, **overrides):
    values = {
        "account_id": account(db, telegram_id),
        "full_name": "Brut",
        "status": "pending_verification",
        "verified_at": None,
        "is_suspended": False,
        "suspended_at": None,
        "badge": "pending",
        "average_rating": 0.0,
        "total_reviews": 0,
        "total_missions": 0,
        "success_rate": 0.0,
        "consecutive_ignored": 0,
        "portfolio_file_ids": [],
        "created_at": datetime(2026, 11, 12),
        "updated_at": datetime(2026, 11, 12),
    }
    values.update(overrides)
    db.add(ProviderProfile(**values))


@pytest.mark.parametrize(
    "overrides",
    [
        {"status": "available"},  # disponible sans être vérifié
        {"status": "paused"},
        {"status": "offline"},
        {"status": "pending_verification", "verified_at": datetime(2026, 11, 12)},  # vérifié mais en attente
        {"status": "rejected", "verified_at": datetime(2026, 11, 12)},
        {"status": "suspended", "verified_at": datetime(2026, 11, 12)},  # statut inconnu
        {"is_suspended": True},  # suspendu sans date
        {"suspended_at": datetime(2026, 11, 12)},  # date sans suspension
        {"badge": "or"},
        {"consecutive_ignored": -1},
    ],
)
def test_the_database_refuses_impossible_provider_states(db, overrides):
    _raw_provider(db, 7, **overrides)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_the_database_accepts_a_consistent_provider(db):
    _raw_provider(db, 7, status="available", verified_at=datetime(2026, 11, 12))
    db.commit()


@pytest.mark.parametrize("row", [ProviderService(service_key="service_inconnu"), ProviderCommune(commune="Kintambo")])
def test_the_database_refuses_a_service_or_commune_outside_the_catalogue(db, row):
    _raw_provider(db, 7)
    db.commit()
    row.account_id = ledger.account_id_for(db, ledger.TELEGRAM, 7)
    db.add(row)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_the_catalogue_refuses_inconsistent_visit_fees(db):
    from sqlalchemy import text

    for module, inspection, fee in (("B", True, 0), ("A", False, 5), ("A", True, 0), ("C", False, 0)):
        with pytest.raises(IntegrityError):
            db.execute(
                text(
                    "INSERT INTO services (key, name_fr, name_ln, name_en, category, icon_emoji, module,"
                    " requires_inspection, visit_fee_usd, position, is_active)"
                    " VALUES ('x', 'X', 'X', 'X', 'X', 'x', :module, :inspection, :fee, 99, TRUE)"
                ),
                {"module": module, "inspection": inspection, "fee": fee},
            )
            db.commit()
        db.rollback()
