"""Compte Nexis : rôles donnés par les profils, une seule langue par
personne, numéro vérifié unique (docs/ARCHITECTURE_WHATSAPP.md).

Classes prises dans `crud` / `ledger` pour la même raison que test_ledger.py.
"""

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from backend.app import crud, ledger, profils
from backend.tests import profils_de_test

NexisAccount = crud.NexisAccount


@pytest.fixture
def db(backend_db_url):
    engine = create_engine(backend_db_url, future=True)
    NexisAccount.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    yield session
    session.close()
    engine.dispose()


def client(db, telegram_id, name, language="fr"):
    profils_de_test.client(db, telegram_id, name, language)


def provider(db, telegram_id, name):
    profils_de_test.provider(db, telegram_id, name, verified=False)


def account(db, telegram_id):
    return db.get(NexisAccount, ledger.account_id_for(db, ledger.TELEGRAM, telegram_id))


def test_registering_a_client_gives_the_account_the_client_role_and_language(db):
    client(db, 42, "Ben", language="ln")

    assert account(db, 42).roles == ["client"]
    assert account(db, 42).language == "ln"


def test_a_person_with_both_profiles_has_both_roles_on_one_account(db):
    client(db, 7, "Ben")
    provider(db, 7, "Ben")

    assert account(db, 7).roles == ["client", "provider"]
    assert db.query(NexisAccount).count() == 1


def test_one_language_per_person_whatever_the_role(db):
    client(db, 7, "Ben")
    provider(db, 7, "Ben")
    account_id = account(db, 7).id

    profils.set_language(db, account_id, "en")
    db.commit()
    assert account(db, 7).language == "en"
    assert profils.language_of(db, account_id) == "en"
    with pytest.raises(profils.ProfileRefused):
        profils.set_language(db, account_id, "de")
    assert account(db, 7).roles == ["client", "provider"]


def test_a_typed_phone_number_is_never_recorded_as_verified(db):
    account_id = ledger.account_id_for(db, ledger.TELEGRAM, 42, create=True)
    profils.save_client_profile(db, account_id, first_name="Ben", phone_number="+243800000042")
    db.commit()

    assert account(db, 42).phone_e164 is None
    assert account(db, 42).phone_verified_at is None


def test_a_verified_number_belongs_to_one_account_only(db):
    client(db, 1, "A")
    client(db, 2, "B")
    first, second = account(db, 1), account(db, 2)
    first.phone_e164 = second.phone_e164 = "+243810000000"
    first.phone_verified_at = datetime(2026, 10, 6)
    db.commit()

    # Un même numéro non vérifié sur un autre compte reste permis...
    assert second.phone_verified_at is None
    # ...mais pas deux comptes vérifiés avec le même numéro.
    second.phone_verified_at = datetime(2026, 10, 6)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
