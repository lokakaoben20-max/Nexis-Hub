"""Règles de la case des conditions d'utilisation (backend/app/conditions.py).

Publication (jamais de réécriture, ordre des versions), version en vigueur,
ce qui manque à un compte selon ses rôles, acceptation (version en vigueur
seulement, idempotente, rien d'enregistré sur un refus), inscription qui
porte la case, prestataires proposés aux missions, commande d'exploitation.
Les contraintes de la base sont vérifiées en écrivant directement.
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from backend.app import conditions, ledger, profils
from backend.tests import profils_de_test

pytestmark = pytest.mark.conditions_reelles

LegalAcceptance = conditions.LegalAcceptance
LegalDocumentVersion = conditions.LegalDocumentVersion
NOW = datetime(2026, 11, 20, 8, 0)


@pytest.fixture
def db(backend_db_url):
    engine = create_engine(backend_db_url, future=True)
    if engine.dialect.name == "sqlite":
        event.listen(engine, "connect", lambda connection, _: connection.execute("PRAGMA foreign_keys=ON"))
    LegalAcceptance.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    profils_de_test.ensure_catalogue(session)
    session.commit()
    yield session
    session.close()
    engine.dispose()


def publish(db, key, version, *, at=NOW, text=None):
    row = conditions.publish_version(db, key, version, text or f"Texte {key} {version}", effective_at=at, now=min(at, NOW))
    db.commit()
    return row


def publish_both(db, version="v1", at=NOW):
    publish(db, conditions.CGU, version, at=at)
    publish(db, conditions.PROVIDER_TERMS, version, at=at)


def account(db, telegram_id):
    account_id = ledger.account_id_for(db, ledger.TELEGRAM, telegram_id, create=True)
    db.commit()
    return account_id


def docs(*pairs):
    return [{"document_key": key, "version": version} for key, version in pairs]


def accept(db, account_id, role, *pairs, now=NOW):
    rows = conditions.accept(db, account_id, role, docs(*pairs), surface="telegram_bot", language="fr", now=now)
    db.commit()
    return rows


# --- Publication -------------------------------------------------------------


def test_a_published_version_keeps_its_exact_text_and_fingerprint(db):
    row = publish(db, conditions.CGU, "2026-11-20", text="Article 1. Nexis Hub…")
    assert row.text == "Article 1. Nexis Hub…"
    assert row.text_sha256 == conditions.fingerprint("Article 1. Nexis Hub…")
    assert row.language == "fr"


def test_a_published_version_is_never_replaced(db):
    publish(db, conditions.CGU, "v1")
    with pytest.raises(conditions.ConditionsError) as refused:
        publish(db, conditions.CGU, "v1", at=NOW + timedelta(days=1), text="autre texte")
    assert refused.value.code == "version_already_published"
    assert db.scalar(select(LegalDocumentVersion.text).where(LegalDocumentVersion.version == "v1")) == "Texte cgu v1"


@pytest.mark.parametrize(
    ("key", "version", "text", "code"),
    [
        ("inconnu", "v1", "texte", "unknown_document"),
        ("cgu", "v 1", "texte", "invalid_version"),
        ("cgu", "v:1", "texte", "invalid_version"),
        ("cgu", "", "texte", "invalid_version"),
        ("cgu", "v1", "   ", "invalid_text"),
    ],
)
def test_publication_refusals(db, key, version, text, code):
    with pytest.raises(conditions.ConditionsError) as refused:
        conditions.publish_version(db, key, version, text, now=NOW)
    assert refused.value.code == code


def test_a_version_cannot_take_effect_in_the_past_or_before_the_previous_one(db):
    with pytest.raises(conditions.ConditionsError) as refused:
        conditions.publish_version(db, "cgu", "v0", "texte", effective_at=NOW - timedelta(minutes=1), now=NOW)
    assert refused.value.code == "effective_in_past"
    publish(db, conditions.CGU, "v2", at=NOW + timedelta(days=10))
    with pytest.raises(conditions.ConditionsError) as refused:
        conditions.publish_version(db, "cgu", "v1", "texte", effective_at=NOW + timedelta(days=5), now=NOW)
    assert refused.value.code == "effective_before_previous_version"


def test_the_version_in_force_is_the_latest_whose_date_has_come(db):
    publish(db, conditions.CGU, "v1")
    publish(db, conditions.CGU, "v2", at=NOW + timedelta(days=7))
    assert conditions.current_version(db, conditions.CGU, NOW + timedelta(days=1)).version == "v1"
    assert conditions.current_version(db, conditions.CGU, NOW + timedelta(days=7)).version == "v2"


# --- Ce qui manque -------------------------------------------------------------


def test_nothing_published_lets_nobody_through(db):
    with pytest.raises(conditions.ConditionsError) as refused:
        conditions.missing(db, None, conditions.CLIENT, NOW)
    assert (refused.value.code, refused.value.http_status) == ("terms_unavailable", 503)
    publish(db, conditions.CGU, "v1")
    assert conditions.missing(db, None, conditions.CLIENT, NOW) == [
        {"document_key": "cgu", "version": "v1", "effective_at": NOW.isoformat()}
    ]
    # Conditions des prestataires pas encore publiées : aucun prestataire.
    with pytest.raises(conditions.ConditionsError) as refused:
        conditions.missing(db, None, conditions.PROVIDER, NOW)
    assert refused.value.code == "terms_unavailable"


def test_a_client_needs_the_cgu_and_a_provider_also_needs_the_provider_terms(db):
    publish_both(db)
    person = account(db, 1)
    assert [item["document_key"] for item in conditions.missing(db, person, conditions.CLIENT, NOW)] == ["cgu"]
    assert [item["document_key"] for item in conditions.missing(db, person, conditions.PROVIDER, NOW)] == [
        "cgu",
        "conditions_prestataires",
    ]
    accept(db, person, conditions.CLIENT, ("cgu", "v1"))
    assert conditions.missing(db, person, conditions.CLIENT, NOW) == []
    # Bascule vers prestataire : seules les conditions des prestataires manquent.
    assert [item["document_key"] for item in conditions.missing(db, person, conditions.PROVIDER, NOW)] == [
        "conditions_prestataires"
    ]


def test_a_new_version_in_force_must_be_accepted_again(db):
    publish_both(db)
    person = account(db, 1)
    accept(db, person, conditions.CLIENT, ("cgu", "v1"))
    publish(db, conditions.CGU, "v2", at=NOW + timedelta(days=30))
    conditions.require(db, person, conditions.CLIENT, NOW + timedelta(days=29))
    with pytest.raises(conditions.ConditionsError) as refused:
        conditions.require(db, person, conditions.CLIENT, NOW + timedelta(days=30))
    assert refused.value.code == "terms_not_accepted"
    assert refused.value.missing == [
        {"document_key": "cgu", "version": "v2", "effective_at": (NOW + timedelta(days=30)).isoformat()}
    ]
    assert refused.value.detail()["missing"] == refused.value.missing


def test_status_covers_the_roles_the_account_holds(db):
    publish_both(db)
    assert conditions.status(db, None, NOW)["missing"] == []  # personne inconnue : rien à recocher
    profils_de_test.client(db, 1)
    person = ledger.account_id_for(db, ledger.TELEGRAM, 1)
    state = conditions.status(db, person, NOW)
    assert state["roles"] == ["client"]
    assert [item["document_key"] for item in state["missing"]] == ["cgu"]
    assert state["role"] == "client" and state["complete"] is False
    assert [item["document_key"] for item in state["by_role"]["provider"]] == ["cgu", "conditions_prestataires"]

    profils_de_test.provider(db, 2)
    provider = ledger.account_id_for(db, ledger.TELEGRAM, 2)
    state = conditions.status(db, provider, NOW)
    assert state["role"] == "provider"
    assert [item["document_key"] for item in state["missing"]] == ["cgu", "conditions_prestataires"]
    accept(db, provider, conditions.PROVIDER, ("cgu", "v1"), ("conditions_prestataires", "v1"))
    assert conditions.status(db, provider, NOW)["complete"] is True


# --- Acceptation -----------------------------------------------------------------


def test_accepting_twice_records_one_row(db):
    publish_both(db)
    person = account(db, 1)
    first = accept(db, person, conditions.CLIENT, ("cgu", "v1"))
    again = accept(db, person, conditions.PROVIDER, ("cgu", "v1"), ("conditions_prestataires", "v1"))
    assert again[0].id == first[0].id
    rows = db.scalars(select(LegalAcceptance).where(LegalAcceptance.account_id == person)).all()
    assert len(rows) == 2
    cgu = next(row for row in rows if row.version_id == first[0].version_id)
    # La première acceptation fait foi (rôle, canal, date).
    assert (cgu.role, cgu.surface, cgu.language, cgu.accepted_at) == ("client", "telegram_bot", "fr", NOW)


def test_only_the_version_in_force_can_be_accepted_and_nothing_is_recorded_otherwise(db):
    publish_both(db)
    publish(db, conditions.CGU, "v2", at=NOW + timedelta(days=3))
    person = account(db, 1)
    later = NOW + timedelta(days=3)
    with pytest.raises(conditions.ConditionsError) as refused:
        accept(db, person, conditions.PROVIDER, ("conditions_prestataires", "v1"), ("cgu", "v1"), now=later)
    assert refused.value.code == "terms_version_outdated"
    db.rollback()
    assert db.scalars(select(LegalAcceptance)).all() == []
    # Une version annoncée pour plus tard ne s'accepte pas non plus d'avance.
    with pytest.raises(conditions.ConditionsError) as refused:
        accept(db, person, conditions.CLIENT, ("cgu", "v2"))
    assert refused.value.code == "terms_version_outdated"


@pytest.mark.parametrize(
    ("role", "documents", "code"),
    [
        ("client", docs(("conditions_prestataires", "v1")), "invalid_terms"),
        ("client", docs(("cgu", "v1"), ("cgu", "v1")), "invalid_terms"),
        ("client", [], "invalid_terms"),
        ("client", ["cgu"], "invalid_terms"),
        ("client", docs(("cgu", "v9")), "terms_version_not_found"),
        ("admin", docs(("cgu", "v1")), "unknown_role"),
    ],
)
def test_acceptance_refusals(db, role, documents, code):
    publish_both(db)
    person = account(db, 1)
    with pytest.raises(conditions.ConditionsError) as refused:
        conditions.accept(db, person, role, documents, surface="telegram_bot", language="fr", now=NOW)
    assert refused.value.code == code


def test_acceptance_needs_a_known_surface_and_language(db):
    publish_both(db)
    person = account(db, 1)
    for surface, language, code in (("sms", "fr", "invalid_surface"), ("app", "de", "invalid_language")):
        with pytest.raises(conditions.ConditionsError) as refused:
            conditions.accept(db, person, "client", docs(("cgu", "v1")), surface=surface, language=language, now=NOW)
        assert refused.value.code == code


@pytest.mark.parametrize(
    ("channel", "surface", "allowed"),
    [
        ("telegram", "telegram_bot", True),
        ("telegram", "mini_app", True),
        ("telegram", "whatsapp", False),
        ("whatsapp", "whatsapp", True),
        ("whatsapp", "telegram_bot", False),
        ("app", "app", True),
        ("app", "mini_app", False),
    ],
)
def test_each_channel_declares_only_its_own_surfaces(channel, surface, allowed):
    if allowed:
        assert conditions.checked_surface(channel, surface) == surface
    else:
        with pytest.raises(conditions.ConditionsError):
            conditions.checked_surface(channel, surface)


def test_signup_without_the_box_ticked_is_refused(db):
    publish_both(db)
    person = account(db, 1)
    with pytest.raises(conditions.ConditionsError) as refused:
        conditions.accept_for_signup(db, person, "client", None, channel="telegram", language="fr", now=NOW)
    assert refused.value.code == "terms_not_accepted"
    conditions.accept_for_signup(
        db,
        person,
        "client",
        {"surface": "telegram_bot", "documents": docs(("cgu", "v1"))},
        channel="telegram",
        language="ln",
        now=NOW,
    )
    db.commit()
    # Bascule vers prestataire : les CGU déjà cochées ne suffisent pas.
    with pytest.raises(conditions.ConditionsError) as refused:
        conditions.accept_for_signup(db, person, "provider", None, channel="telegram", language="fr", now=NOW)
    assert [item["document_key"] for item in refused.value.missing] == ["conditions_prestataires"]
    conditions.accept_for_signup(
        db,
        person,
        "provider",
        {"surface": "mini_app", "documents": docs(("conditions_prestataires", "v1"))},
        channel="telegram",
        language="fr",
        now=NOW,
    )
    db.commit()
    rows = db.scalars(select(LegalAcceptance).order_by(LegalAcceptance.id)).all()
    assert [(row.role, row.surface, row.language) for row in rows] == [
        ("client", "telegram_bot", "ln"),
        ("provider", "mini_app", "fr"),
    ]


def test_an_account_that_does_not_exist_cannot_accept(db):
    publish_both(db)
    with pytest.raises(conditions.ConditionsError) as refused:
        accept(db, 999_999, conditions.CLIENT, ("cgu", "v1"))
    assert refused.value.code == "account_not_found"


# --- Contraintes de la base ------------------------------------------------------


def test_the_database_refuses_a_second_row_for_the_same_version(db):
    publish_both(db)
    person = account(db, 1)
    version = conditions.current_version(db, "cgu", NOW)
    for _ in range(2):
        db.add(LegalAcceptance(account_id=person, version_id=version.id, role="client", surface="app", language="fr", accepted_at=NOW))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


@pytest.mark.parametrize(("role", "surface"), [("admin", "app"), ("client", "sms")])
def test_the_database_refuses_an_unknown_role_or_surface(db, role, surface):
    publish_both(db)
    person = account(db, 1)
    version = conditions.current_version(db, "cgu", NOW)
    db.add(LegalAcceptance(account_id=person, version_id=version.id, role=role, surface=surface, language="fr", accepted_at=NOW))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_the_database_refuses_an_unknown_document(db):
    db.add(
        LegalDocumentVersion(
            document_key="charte", version="v1", language="fr", text="x", text_sha256="0" * 64, effective_at=NOW, published_at=NOW
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


# --- Prestataires proposés aux missions -------------------------------------------


def test_only_providers_who_accepted_the_provider_terms_in_force_receive_missions(db):
    profils_de_test.provider(db, 1)
    profils_de_test.provider(db, 2)
    # Rien de publié : personne n'est proposé.
    assert profils.eligible_providers(db, "service_plomberie", "Gombe") == []

    publish(db, conditions.CGU, "v1", at=datetime.utcnow().replace(microsecond=0) - timedelta(seconds=1))
    publish(db, conditions.PROVIDER_TERMS, "v1", at=datetime.utcnow().replace(microsecond=0) - timedelta(seconds=1))
    first = ledger.account_id_for(db, ledger.TELEGRAM, 1)
    accept(db, first, conditions.PROVIDER, ("cgu", "v1"), ("conditions_prestataires", "v1"), now=datetime.utcnow())
    assert [provider.account_id for provider in profils.eligible_providers(db, "service_plomberie", "Gombe")] == [first]


# --- Commande d'exploitation ------------------------------------------------------


def test_the_command_publishes_a_file_and_refuses_it_twice(db, backend_db_url, monkeypatch, tmp_path, capsys):
    from backend.app import database

    monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=create_engine(backend_db_url, future=True)))
    texte = tmp_path / "cgu.md"
    texte.write_text("Conditions générales — mosala na bosembo", encoding="utf-8")
    assert conditions.main(["publier", "cgu", "2026-11-20", str(texte)]) == 0
    assert "Publié : cgu 2026-11-20" in capsys.readouterr().out
    assert conditions.main(["publier", "cgu", "2026-11-20", str(texte)]) == 1
    assert "version_already_published" in capsys.readouterr().err
    assert conditions.main(["liste"]) == 0
    out = capsys.readouterr().out
    assert "cgu 2026-11-20" in out
    assert "Aucune version en vigueur pour conditions_prestataires" in out
    db.expire_all()
    row = db.scalar(select(LegalDocumentVersion).where(LegalDocumentVersion.version == "2026-11-20"))
    assert row.text == "Conditions générales — mosala na bosembo"
