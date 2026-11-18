"""Isolated tests for read-only SQLite migration preflight; no production database."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import db
from scripts.sqlite_migration_preflight import preflight


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(prefix="nexis-preflight-test-")
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / "offline-backup.sqlite3"
        with patch.object(db, "DB_PATH", self.path):
            db.init_db()

    def test_empty_schema_passes(self):
        report = preflight(self.path)
        self.assertEqual(report["errors"], [], report)
        self.assertEqual(len(report["tables"]), 9)
        self.assertTrue(all(t["rows"] == 0 for t in report["tables"].values()))

    def test_invalid_precision_is_rejected(self):
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                "INSERT INTO users (telegram_id, phone_number, wallet_balance_usd) VALUES (?, ?, ?)",
                (101, "test-only", 1.123456),
            )
        report = preflight(self.path)
        self.assertTrue(
            any("users.wallet_balance_usd" in error for error in report["errors"]),
            report,
        )

    def test_missing_table_is_rejected(self):
        with sqlite3.connect(self.path) as conn:
            conn.execute("DROP TABLE platform_settings")
        report = preflight(self.path)
        self.assertIn("Missing table: platform_settings", report["errors"])


if __name__ == "__main__":
    unittest.main()
