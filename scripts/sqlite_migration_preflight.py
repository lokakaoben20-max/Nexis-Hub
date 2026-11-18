"""Read-only SQLite to PostgreSQL migration preflight.

Never opens a PostgreSQL connection or writes to either database.
Usage: python -m scripts.sqlite_migration_preflight /path/to/backup.sqlite3
"""
import argparse
import json
import sqlite3
from decimal import Decimal, InvalidOperation
from pathlib import Path

from backend.app import models  # noqa: F401
from backend.app.postgres import Base

FINANCIAL_TOKENS = ("amount", "balance", "fee", "commission", "rate", "net_provider", "total_client")
MAX_DECIMAL = Decimal("9999999999999999.9999")


def preflight(path):
    source = Path(path).expanduser().resolve(strict=True)
    if not source.is_file():
        raise ValueError("Source must be a regular SQLite backup file")
    # SQLite read-only URI: no source creation, schema edits or journal writes.
    uri = source.as_uri() + "?mode=ro&immutable=1"
    result = {"source": str(source), "tables": {}, "errors": [], "warnings": []}
    with sqlite3.connect(uri, uri=True) as conn:
        conn.execute("PRAGMA query_only=ON")
        check = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if check != "ok":
            result["errors"].append("SQLite integrity_check failed")
            return result
        # A broken backup may lack referenced tables. Check presence before
        # PRAGMA foreign_key_check, which otherwise raises OperationalError.
        existing = {
            name for (name,) in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        for name in Base.metadata.tables:
            if name not in existing:
                result["errors"].append(f"Missing table: {name}")
        if result["errors"]:
            return result

        # Report only aggregate counts; never expose customer data or IDs.
        orphan_counts = {}
        try:
            for table_name, _rowid, _parent, _fk_index in conn.execute("PRAGMA foreign_key_check"):
                orphan_counts[table_name] = orphan_counts.get(table_name, 0) + 1
        except sqlite3.DatabaseError:
            result["errors"].append("SQLite foreign-key integrity check failed")
            return result
        for table_name, count in sorted(orphan_counts.items()):
            result["errors"].append(f"{table_name}: {count} orphaned foreign-key references")
        for name, table in Base.metadata.tables.items():
            safe_name = '"' + name.replace('"', '""') + '"'
            exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone()
            if not exists:
                result["errors"].append(f"Missing table: {name}")
                continue
            source_cols = {row[1] for row in conn.execute(f"PRAGMA table_info({safe_name})")}
            target_cols = set(table.columns.keys())
            for col in sorted(source_cols - target_cols):
                result["errors"].append(f"{name}: source-only column {col}")
            for col in sorted(target_cols - source_cols):
                result["errors"].append(f"{name}: target-only column {col}")
            count = conn.execute(f"SELECT COUNT(*) FROM {safe_name}").fetchone()[0]
            result["tables"][name] = {"rows": count}
            for col in table.columns:
                if col.name not in source_cols:
                    continue
                if not any(token in col.name for token in FINANCIAL_TOKENS):
                    continue
                if not hasattr(col.type, "precision") or col.type.precision is None:
                    continue
                qcol = '"' + col.name.replace('"', '""') + '"'
                for (value,) in conn.execute(f"SELECT {qcol} FROM {safe_name} WHERE {qcol} IS NOT NULL"):
                    try:
                        number = Decimal(str(value))
                        if not number.is_finite() or abs(number) > MAX_DECIMAL or number.as_tuple().exponent < -4:
                            raise ValueError("outside NUMERIC(20,4) exact range")
                    except (InvalidOperation, ValueError, TypeError):
                        result["errors"].append(f"{name}.{col.name}: non-representable monetary value")
                        break
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backup", help="Path to an offline SQLite backup; never use the live database")
    args = parser.parse_args()
    report = preflight(args.backup)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if report["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
