"""Checks for SQLite reliability and recoverable backups."""

import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import db
from scripts.backup_sqlite import backup_sqlite


def test_connection_enforces_foreign_keys_and_closes(tmp_path):
    db.DB_PATH = tmp_path / "source.db"
    db.init_db()
    with db.get_connection() as conn:
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"

    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT 1")

    with pytest.raises(sqlite3.IntegrityError):
        with db.get_connection() as conn:
            conn.execute(
                "INSERT INTO missions (user_id, service, commune, description) "
                "VALUES (999999, 'service_plomberie', 'Gombe', 'Orphan')"
            )


def test_online_backup_preserves_data_without_overwriting(tmp_path):
    db.DB_PATH = tmp_path / "source.db"
    db.init_db()
    db.create_user(12345, "+243812345678", "Alice")

    destination = tmp_path / "backups" / "nexis-snapshot.db"
    result = backup_sqlite(db.DB_PATH, destination)
    assert result["integrity"] == "ok"
    assert result["foreign_key_issues"] == 0
    assert destination.exists()

    with sqlite3.connect(destination) as conn:
        users = conn.execute(
            "SELECT first_name FROM users WHERE telegram_id = 12345"
        ).fetchall()
        assert users == [("Alice",)]
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"

    with pytest.raises(FileExistsError):
        backup_sqlite(db.DB_PATH, destination)

    with pytest.raises(ValueError):
        backup_sqlite(db.DB_PATH, db.DB_PATH)


def test_backup_does_not_create_missing_database(tmp_path):
    missing = tmp_path / "missing.db"
    destination = tmp_path / "backup.db"
    with pytest.raises(FileNotFoundError):
        backup_sqlite(missing, destination)
    assert not missing.exists()
    assert not destination.exists()
