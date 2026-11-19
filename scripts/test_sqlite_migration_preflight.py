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

    def _report_after_checkpoint(self):
        # The preflight uses immutable=1, which intentionally ignores WAL files.
        # Flush this disposable test database so the reader sees committed edits.
        with sqlite3.connect(self.path) as conn:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        return preflight(self.path)

    def test_empty_schema_passes(self):
        report = self._report_after_checkpoint()
        self.assertEqual(report["errors"], [], report)
        self.assertEqual(len(report["tables"]), 9)
        # init_db() seeds catalog and platform defaults even on a fresh DB.
        self.assertGreater(report["tables"]["services"]["rows"], 0)
        self.assertGreater(report["tables"]["platform_settings"]["rows"], 0)
        for name, table in report["tables"].items():
            if name not in ("services", "platform_settings"):
                self.assertEqual(table["rows"], 0, name)

    def test_invalid_precision_is_rejected(self):
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                "INSERT INTO users (telegram_id, phone_number, wallet_balance_usd) VALUES (?, ?, ?)",
                (101, "test-only", 1.123456),
            )
        report = self._report_after_checkpoint()
        self.assertTrue(
            any("users.wallet_balance_usd" in error for error in report["errors"]),
            report,
        )

    def test_orphaned_mission_reference_is_rejected(self):
        # Simulate a legacy SQLite backup with foreign keys not enforced.
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                "INSERT INTO missions (user_id, service, commune, description) "
                "VALUES (?, ?, ?, ?)",
                (999999, "test-only", "test-only", "orphan reference"),
            )
        report = self._report_after_checkpoint()
        self.assertTrue(
            any("missions: 1 orphaned foreign-key references" in error
                for error in report["errors"]),
            report,
        )

    def test_missing_referenced_table_reports_error_without_crashing(self):
        with sqlite3.connect(self.path) as conn:
            conn.execute("DROP TABLE users")
        report = self._report_after_checkpoint()
        self.assertIn("Missing table: users", report["errors"])

    def test_missing_table_is_rejected(self):
        with sqlite3.connect(self.path) as conn:
            conn.execute("DROP TABLE platform_settings")
        report = self._report_after_checkpoint()
        self.assertIn("Missing table: platform_settings", report["errors"])


if __name__ == "__main__":
    unittest.main()
