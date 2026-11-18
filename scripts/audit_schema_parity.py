"""Compare the actual SQLite schema with PostgreSQL ORM metadata without touching production.

Runs db.init_db() against a temporary SQLite file, never the live database.
Reports column names only; no records or credentials.
"""
import json
import tempfile
from pathlib import Path

import db
from backend.app import models  # noqa: F401 - register ORM tables
from backend.app.postgres import Base


def audit_schema():
    original = db.DB_PATH
    try:
        with tempfile.TemporaryDirectory(prefix="nexis-schema-audit-") as folder:
            db.DB_PATH = Path(folder) / "schema-only.db"
            db.init_db()
            with db.get_connection() as conn:
                source = {}
                for (name,) in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' "
                    "AND name NOT LIKE 'sqlite_%'"
                ):
                    source[name] = {
                        row[1] for row in conn.execute(f'PRAGMA table_info("{name}")')
                    }
    finally:
        db.DB_PATH = original

    target = {name: set(table.columns.keys()) for name, table in Base.metadata.tables.items()}
    return {
        "source_tables": len(source),
        "target_tables": len(target),
        "missing_tables": sorted(set(source) - set(target)),
        "extra_tables": sorted(set(target) - set(source)),
        "missing_columns": {
            name: sorted(source[name] - target[name])
            for name in sorted(set(source) & set(target))
            if source[name] - target[name]
        },
        "extra_columns": {
            name: sorted(target[name] - source[name])
            for name in sorted(set(source) & set(target))
            if target[name] - source[name]
        },
    }


if __name__ == "__main__":
    report = audit_schema()
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if report["missing_tables"] or report["extra_tables"]:
        raise SystemExit("Table mismatch: reconcile before backend cutover")
