"""Fichiers gardés par le backend (backend/app/fichiers.py) : type réel lu
dans le contenu, taille bornée, chiffrement lié à l'identifiant, lecture
vérifiée, configuration obligatoire hors développement."""

import base64
import os

import pytest
from cryptography.exceptions import InvalidTag
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from backend.app import fichiers, ledger
from backend.tests import profils_de_test

StoredFile = fichiers.StoredFile
JPEG = b"\xff\xd8\xff\xe0" + b"realisation" * 20
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 40
WEBP = b"RIFF\x00\x00\x00\x00WEBPVP8 " + b"\x00" * 20


@pytest.fixture
def db(backend_db_url, tmp_path, monkeypatch):
    monkeypatch.setenv("FILES_DIR", str(tmp_path / "fichiers"))
    monkeypatch.delenv("FILES_ENCRYPTION_KEY", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    engine = create_engine(backend_db_url, future=True)
    if engine.dialect.name == "sqlite":
        event.listen(engine, "connect", lambda connection, _: connection.execute("PRAGMA foreign_keys=ON"))
    StoredFile.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    profils_de_test.ensure_catalogue(session)
    session.commit()
    yield session
    session.close()
    engine.dispose()


def owner(db, telegram_id=7):
    account_id = ledger.account_id_for(db, ledger.TELEGRAM, telegram_id, create=True)
    db.commit()
    return account_id


def refused(code, action, *args):
    with pytest.raises(fichiers.FileRefused) as raised:
        action(*args)
    assert raised.value.code == code


def test_the_real_type_comes_from_the_content_never_the_name():
    assert [fichiers.sniff_image(data) for data in (JPEG, PNG, WEBP)] == ["image/jpeg", "image/png", "image/webp"]
    assert fichiers.sniff_image(b"<svg onload=alert(1)>") is None
    assert fichiers.sniff_image(b"GIF89a....") is None


def test_a_photo_is_stored_encrypted_and_read_back_intact(db):
    stored = fichiers.store_photo(db, owner(db), JPEG)
    db.commit()
    assert (stored.content_type, stored.size_bytes, len(stored.id)) == ("image/jpeg", len(JPEG), 32)
    on_disk = fichiers._path(stored.id).read_bytes()
    assert b"realisation" not in on_disk, "jamais en clair sur le disque"
    assert fichiers.read(stored) == JPEG


def test_refusals_write_nothing(db):
    account_id = owner(db)
    refused("empty_file", fichiers.store_photo, db, account_id, b"")
    refused("unsupported_file_type", fichiers.store_photo, db, account_id, b"%PDF-1.7 ...")
    refused("file_too_large", fichiers.store_photo, db, account_id, b"\xff\xd8\xff" + b"0" * fichiers.MAX_PHOTO_BYTES)
    db.rollback()
    assert db.query(StoredFile).count() == 0
    assert not any(path.is_file() and not path.name.startswith(".") for path in fichiers.storage_dir().rglob("*"))


def test_a_file_copied_under_another_id_does_not_decrypt(db):
    first = fichiers.store_photo(db, owner(db), JPEG)
    second = fichiers.store_photo(db, owner(db), PNG)
    db.commit()
    fichiers._path(second.id).write_bytes(fichiers._path(first.id).read_bytes())
    with pytest.raises(InvalidTag):
        fichiers.read(second)


def test_a_missing_or_deleted_file_is_never_served(db):
    stored = fichiers.store_photo(db, owner(db), JPEG)
    db.commit()
    os.remove(fichiers._path(stored.id))
    refused("file_missing", fichiers.read, stored)
    stored.deleted_at = stored.created_at
    refused("file_deleted", fichiers.read, stored)


def test_unattached_uploads_are_capped_per_day(db, monkeypatch):
    monkeypatch.setattr(fichiers, "MAX_UNATTACHED_PER_DAY", 2)
    account_id = owner(db)
    for _ in range(2):
        fichiers.store_photo(db, account_id, JPEG)
    db.commit()
    refused("too_many_files", fichiers.store_photo, db, account_id, JPEG)
    fichiers.store_photo(db, owner(db, 8), JPEG)


def test_outside_development_the_storage_must_be_configured(db, monkeypatch, tmp_path):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("FILES_DIR")
    with pytest.raises(fichiers.StorageNotConfigured):
        fichiers.store_photo(db, owner(db), JPEG)
    monkeypatch.setenv("FILES_DIR", str(tmp_path / "prod"))
    with pytest.raises(fichiers.StorageNotConfigured):
        fichiers.store_photo(db, owner(db), JPEG)
    monkeypatch.setenv("FILES_ENCRYPTION_KEY", base64.urlsafe_b64encode(b"court").decode())
    with pytest.raises(fichiers.StorageNotConfigured):
        fichiers.store_photo(db, owner(db), JPEG)
    db.rollback()
    monkeypatch.setenv("FILES_ENCRYPTION_KEY", fichiers.new_key())
    stored = fichiers.store_photo(db, owner(db), JPEG)
    db.commit()
    assert fichiers.read(stored) == JPEG
    assert not (tmp_path / "prod" / ".cle").exists(), "hors développement, jamais de clé sur le disque"
