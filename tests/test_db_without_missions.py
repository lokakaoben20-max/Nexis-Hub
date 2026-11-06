"""db.py ne garde plus de missions, devis ni avis (CONCEPTION_MISSIONS.md) :
au démarrage, les anciennes tables sont archivées dans un fichier puis
supprimées, sans jamais perdre une ligne."""

import json
import sqlite3

import pytest

import db


def _legacy_db(path, missions=1):
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, telegram_id INTEGER UNIQUE NOT NULL, phone_number TEXT NOT NULL, first_name TEXT, language TEXT, total_missions INTEGER DEFAULT 0)")
    conn.execute("CREATE TABLE missions (id INTEGER PRIMARY KEY, user_id INTEGER, service TEXT, status TEXT, payment_status TEXT)")
    conn.execute("CREATE TABLE quotes (id INTEGER PRIMARY KEY, mission_id INTEGER, amount REAL, status TEXT)")
    conn.execute("CREATE TABLE reviews (id INTEGER PRIMARY KEY, mission_id INTEGER, rating INTEGER)")
    conn.execute("INSERT INTO users (telegram_id, phone_number, first_name, total_missions) VALUES (42, '+243', 'Cliente', ?)", (missions,))
    for number in range(1, missions + 1):
        conn.execute("INSERT INTO missions (user_id, service, status, payment_status) VALUES (1, 'service_plomberie', 'completed', 'released')")
        conn.execute("INSERT INTO quotes (mission_id, amount, status) VALUES (?, 50.0, 'accepted')", (number,))
        conn.execute("INSERT INTO reviews (mission_id, rating) VALUES (?, 5)", (number,))
    conn.commit()
    conn.close()


def _tables():
    with db.get_connection() as conn:
        return {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}


def test_a_new_database_has_no_mission_tables(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "nexis_hub.db")
    db.init_db()

    assert not _tables() & {"missions", "quotes", "reviews"}
    assert not db.mission_archive_path().exists()


def test_old_missions_are_archived_then_dropped(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "nexis_hub.db")
    _legacy_db(db.DB_PATH, missions=2)

    db.init_db()

    assert not _tables() & {"missions", "quotes", "reviews"}
    archive = json.loads(db.mission_archive_path().read_text(encoding="utf-8"))
    assert [row["id"] for row in archive["missions"]] == [1, 2]
    assert archive["quotes"][0] == {"id": 1, "mission_id": 1, "amount": 50.0, "status": "accepted"}
    assert len(archive["reviews"]) == 2
    with db.get_connection() as conn:
        assert "total_missions" not in {row[1] for row in conn.execute("PRAGMA table_info(users)")}
        assert conn.execute("SELECT first_name FROM users WHERE telegram_id = 42").fetchone() == ("Cliente",)

    db.init_db()  # relancer ne change plus rien
    assert db.mission_archive_path().exists()


def test_empty_old_tables_are_dropped_without_an_archive(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "nexis_hub.db")
    _legacy_db(db.DB_PATH, missions=0)

    db.init_db()

    assert not _tables() & {"missions", "quotes", "reviews"}
    assert not db.mission_archive_path().exists()


def test_an_existing_archive_is_never_overwritten(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "nexis_hub.db")
    _legacy_db(db.DB_PATH)
    db.mission_archive_path().write_text("archive précédente", encoding="utf-8")

    with pytest.raises(RuntimeError, match="existe déjà"):
        db.init_db()

    assert db.mission_archive_path().read_text(encoding="utf-8") == "archive précédente"
    assert {"missions", "quotes", "reviews"} <= _tables(), "rien n'est supprimé sans archive"


def test_nothing_is_dropped_when_the_archive_cannot_be_written(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "nexis_hub.db")
    _legacy_db(db.DB_PATH)

    def failing_dump(*args, **kwargs):
        raise OSError("disque plein")

    monkeypatch.setattr(db.json, "dump", failing_dump)
    with pytest.raises(OSError):
        db.init_db()

    assert {"missions", "quotes", "reviews"} <= _tables()
    assert list(tmp_path.glob("*anciennes_missions*")) == [], "pas d'archive à moitié écrite"
