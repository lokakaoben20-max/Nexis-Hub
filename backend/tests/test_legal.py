"""Acceptation des conditions (backend/app/legal.py, CONCEPTION_ACCEPTATIONS.md).

Les classes de modèles viennent de `legal` / `ledger` eux-mêmes, comme dans
test_ledger.py : d'autres tests rechargent `backend.app.models`.
"""

from datetime import timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app import ledger, legal

LegalAcceptance = legal.LegalAcceptance
LegalDocumentVersion = legal.LegalDocumentVersion
ChannelIdentity = ledger.ChannelIdentity

TELEGRAM_ID = 42


@pytest.fixture
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'legal.db'}", future=True)
    LegalAcceptance.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    yield session
    session.close()
    engine.dispose()


def publish(db, key=legal.GENERAL_TERMS, version="v1", effective_in=timedelta(0), text=b"Texte complet"):
    row = legal.publish_version(db, key, version, f"https://exemple.test/{key}/{version}", text, ledger._utcnow() + effective_in)
    db.commit()
    return row


def publish_all(db, version="v1"):
    for key in legal.DOCUMENT_KEYS:
        publish(db, key, version)


def decide(db, key=legal.GENERAL_TERMS, version="v1", decision=legal.ACCEPTED, external_id=TELEGRAM_ID, channel="telegram"):
    row = legal.record_decision(db, channel, external_id, key, version, decision, "fr")
    db.commit()
    return row


def missing_keys(db, role=legal.CLIENT, external_id=TELEGRAM_ID, channel="telegram"):
    return [item["document_key"] for item in legal.status(db, channel, external_id, role)["missing"]]


# --- Versions -----------------------------------------------------------------


def test_nothing_published_means_nothing_required(db):
    status = legal.status(db, "telegram", TELEGRAM_ID, legal.PROVIDER)
    assert status == {"role": legal.PROVIDER, "missing": [], "complete": True}


def test_publish_records_fingerprint_of_exact_text(db):
    row = publish(db, text=b"Article 1. Bonjour")
    assert row.text_sha256 == legal.text_fingerprint(b"Article 1. Bonjour")
    assert len(row.text_sha256) == 64


def test_published_version_is_never_replaced(db):
    publish(db, text=b"Premier texte")
    with pytest.raises(legal.LegalError) as error:
        publish(db, text=b"Autre texte")
    assert error.value.code == "version_already_published"
    db.rollback()
    rows = db.query(LegalDocumentVersion).all()
    assert len(rows) == 1
    assert rows[0].text_sha256 == legal.text_fingerprint(b"Premier texte")


@pytest.mark.parametrize(
    "kwargs, code",
    [
        ({"key": "inconnu"}, "unknown_document"),
        ({"version": "  "}, "invalid_version"),
        ({"version": "v1:a"}, "invalid_version"),
        ({"version": "x" * 31}, "invalid_version"),
        ({"text": b"   "}, "empty_text"),
    ],
)
def test_publish_rejects_invalid_input(db, kwargs, code):
    with pytest.raises(legal.LegalError) as error:
        publish(db, **kwargs)
    assert error.value.code == code


def test_publish_requires_an_https_link(db):
    with pytest.raises(legal.LegalError) as error:
        legal.publish_version(db, legal.GENERAL_TERMS, "v1", "http://exemple.test/cg", b"Texte", ledger._utcnow())
    assert error.value.code == "invalid_version"


def test_version_dated_before_the_previous_one_is_refused(db):
    publish(db, version="v1")
    with pytest.raises(legal.LegalError) as error:
        publish(db, version="v2", effective_in=timedelta(days=-1))
    assert error.value.code == "effective_before_previous_version"


def test_future_version_waits_for_its_effective_date(db):
    publish(db, version="v1")
    publish(db, version="v2", effective_in=timedelta(days=15))
    assert legal.current_version(db, legal.GENERAL_TERMS).version == "v1"
    later = ledger._utcnow() + timedelta(days=16)
    assert legal.current_version(db, legal.GENERAL_TERMS, now=later).version == "v2"


# --- Exigences par rôle ----------------------------------------------------------


def test_client_needs_general_terms_and_data_consent(db):
    publish_all(db)
    assert missing_keys(db, legal.CLIENT) == [legal.GENERAL_TERMS, legal.DATA_CONSENT]


def test_provider_also_needs_provider_terms(db):
    publish_all(db)
    assert missing_keys(db, legal.PROVIDER) == [legal.GENERAL_TERMS, legal.DATA_CONSENT, legal.PROVIDER_TERMS]


def test_only_published_documents_are_required(db):
    publish(db, legal.GENERAL_TERMS)
    assert missing_keys(db, legal.PROVIDER) == [legal.GENERAL_TERMS]


def test_unknown_role_and_channel_are_refused(db):
    with pytest.raises(legal.LegalError) as error:
        legal.status(db, "telegram", TELEGRAM_ID, "admin")
    assert error.value.code == "unknown_role"
    with pytest.raises(legal.LegalError) as error:
        legal.status(db, "sms", TELEGRAM_ID, legal.CLIENT)
    assert error.value.code == "unknown_channel"


def test_status_does_not_create_an_account(db):
    publish_all(db)
    legal.status(db, "telegram", TELEGRAM_ID, legal.CLIENT)
    assert db.query(ChannelIdentity).count() == 0


# --- Décisions -------------------------------------------------------------------


def test_accepting_everything_completes_the_status(db):
    publish_all(db)
    for key in legal.DOCUMENT_KEYS:
        decide(db, key)
    assert legal.status(db, "telegram", TELEGRAM_ID, legal.PROVIDER)["complete"] is True


def test_first_decision_creates_the_nexis_account(db):
    publish(db)
    row = decide(db)
    assert row.account_id == ledger.account_id_for(db, ledger.TELEGRAM, TELEGRAM_ID)
    assert row.channel == "telegram"
    assert row.language == "fr"


def test_acceptance_follows_the_account_across_channels(db):
    """Une personne qui relie WhatsApp à son compte n'a pas à réaccepter."""
    publish_all(db)
    decide(db, legal.GENERAL_TERMS)
    decide(db, legal.DATA_CONSENT)
    account_id = ledger.account_id_for(db, ledger.TELEGRAM, TELEGRAM_ID)
    db.add(ChannelIdentity(account_id=account_id, channel="whatsapp", external_id="243810000000"))
    db.commit()
    assert missing_keys(db, legal.CLIENT, external_id="243810000000", channel="whatsapp") == []


def test_refusal_is_recorded_and_keeps_the_document_missing(db):
    publish(db)
    row = decide(db, decision=legal.REFUSED)
    assert row.decision == legal.REFUSED
    assert missing_keys(db) == [legal.GENERAL_TERMS]


def test_latest_decision_wins_and_history_is_kept(db):
    publish(db)
    decide(db, decision=legal.REFUSED)
    decide(db, decision=legal.ACCEPTED)
    assert missing_keys(db) == []
    # Retrait du consentement : un refus après l'acceptation.
    decide(db, decision=legal.REFUSED)
    assert missing_keys(db) == [legal.GENERAL_TERMS]
    decisions = [row.decision for row in db.query(LegalAcceptance).order_by(LegalAcceptance.id)]
    assert decisions == [legal.REFUSED, legal.ACCEPTED, legal.REFUSED]


def test_repeating_the_same_decision_writes_nothing(db):
    publish(db)
    first = decide(db)
    second = decide(db)
    assert second.id == first.id
    assert db.query(LegalAcceptance).count() == 1


def test_only_the_version_in_force_can_be_accepted(db):
    publish(db, version="v1", effective_in=timedelta(days=-30))
    publish(db, version="v2", effective_in=timedelta(seconds=-1))
    with pytest.raises(legal.LegalError) as error:
        decide(db, version="v1")
    assert error.value.code == "terms_version_outdated"
    db.rollback()
    assert db.query(LegalAcceptance).count() == 0


def test_a_future_version_cannot_be_accepted_yet(db):
    publish(db, version="v1")
    publish(db, version="v2", effective_in=timedelta(days=15))
    with pytest.raises(legal.LegalError) as error:
        decide(db, version="v2")
    assert error.value.code == "terms_version_outdated"


def test_new_version_in_force_must_be_accepted_again(db):
    publish(db, version="v1", effective_in=timedelta(days=-30))
    decide(db, version="v1")
    publish(db, version="v2", effective_in=timedelta(seconds=-1))
    assert legal.status(db, "telegram", TELEGRAM_ID, legal.CLIENT)["missing"] == [
        {"document_key": legal.GENERAL_TERMS, "version": "v2", "url": "https://exemple.test/conditions_generales/v2"}
    ]


@pytest.mark.parametrize(
    "kwargs, code, http_status",
    [
        ({"version": "v9"}, "legal_version_not_found", 404),
        ({"key": "inconnu"}, "unknown_document", 422),
        ({"decision": "peut-etre"}, "unknown_decision", 422),
        ({"channel": "sms"}, "unknown_channel", 422),
    ],
)
def test_invalid_decisions_are_refused_without_writing(db, kwargs, code, http_status):
    publish(db)
    with pytest.raises(legal.LegalError) as error:
        decide(db, **kwargs)
    assert (error.value.code, error.value.http_status) == (code, http_status)
    db.rollback()
    assert db.query(LegalAcceptance).count() == 0
    assert db.query(ChannelIdentity).count() == 0
