"""Compte Nexis : rôles et langue commune synchronisés depuis les profils
Telegram, numéro vérifié unique (docs/ARCHITECTURE_WHATSAPP.md).

Classes prises dans `crud` / `ledger` pour la même raison que test_ledger.py.
"""

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from backend.app import crud, ledger

NexisAccount = crud.NexisAccount


@pytest.fixture
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'identity.db'}", future=True)
    NexisAccount.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    yield session
    session.close()
    engine.dispose()


def account(db, telegram_id):
    return db.get(NexisAccount, ledger.account_id_for(db, ledger.TELEGRAM, telegram_id))


def test_registering_a_client_gives_the_account_the_client_role_and_language(db):
    crud.upsert_user(db, 42, "Ben", "+243800000042", language="ln")

    assert account(db, 42).roles == ["client"]
    assert account(db, 42).language == "ln"


def test_a_person_with_both_profiles_has_both_roles_on_one_account(db):
    crud.upsert_user(db, 7, "Ben", None, language="fr")
    crud.upsert_provider(db, 7, "Ben", None, ["service_plomberie"], ["Gombe"], language="fr")

    assert account(db, 7).roles == ["client", "provider"]
    assert db.query(NexisAccount).count() == 1


def test_a_language_change_on_either_profile_becomes_the_shared_language(db):
    crud.upsert_user(db, 7, "Ben", None, language="fr")
    crud.upsert_provider(db, 7, "Ben", None, ["service_plomberie"], ["Gombe"], language="fr")

    crud.update_provider_language(db, 7, "en")
    assert account(db, 7).language == "en"
    crud.update_user_language(db, 7, "ln")
    assert account(db, 7).language == "ln"
    assert account(db, 7).roles == ["client", "provider"]


def test_a_typed_phone_number_is_never_recorded_as_verified(db):
    crud.upsert_user(db, 42, "Ben", "+243800000042", language="fr")

    assert account(db, 42).phone_e164 is None
    assert account(db, 42).phone_verified_at is None


def test_a_verified_number_belongs_to_one_account_only(db):
    crud.upsert_user(db, 1, "A", None)
    crud.upsert_user(db, 2, "B", None)
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
