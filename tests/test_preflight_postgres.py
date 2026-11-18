"""Read-only preflight verification without exporting personal data."""

import json
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import db
from scripts.preflight_postgres import preflight_sqlite


def test_preflight_reports_schema_and_counts_without_personal_data(tmp_path):
    db.DB_PATH = tmp_path / "nexis.db"
    db.init_db()
    db.create_user(998877, "+243800000998", "Secret Prenom")

    report = preflight_sqlite(db.DB_PATH)
    assert report["table_count"] == 9
    assert report["tables"]["users"]["rows"] == 1
    assert report["integrity"] == "ok"
    assert report["blockers"] == []
    assert report["ready_for_mapping_review"] is True
    assert report["actual_data_transferred"] is False
    assert "users.wallet_balance_usd" in report["money_columns_requiring_decimal_review"]
    serialized = json.dumps(report, ensure_ascii=False)
    assert "Secret Prenom" not in serialized
    assert "+243800000998" not in serialized
    assert "998877" not in serialized


def test_preflight_detects_foreign_key_inconsistencies(tmp_path):
    db.DB_PATH = tmp_path / "nexis.db"
    db.init_db()
    with sqlite3.connect(db.DB_PATH) as conn:
        conn.execute(
            "INSERT INTO missions (user_id, service, commune, description) "
            "VALUES (999999, 'service_plomberie', 'Gombe', 'Orphan')"
        )
    report = preflight_sqlite(db.DB_PATH)
    assert report["ready_for_mapping_review"] is False
    assert "foreign_key_violations" in report["blockers"]
    assert report["foreign_key_violations_by_table"]["missions"] == 1


def test_preflight_never_creates_missing_source(tmp_path):
    missing = tmp_path / "missing.db"
    with pytest.raises(FileNotFoundError):
        preflight_sqlite(missing)
    assert not missing.exists()
