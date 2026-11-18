"""Read-only preflight before migrating NEXIS SQLite data to PostgreSQL.

Generates a schema-and-count manifest only: no customer names, phone numbers,
document URLs, balances or transaction details are exported.
"""

import argparse
import hashlib
import json
import sqlite3
from collections import Counter
from contextlib import closing
from pathlib import Path
from urllib.parse import quote


DEFAULT_SOURCE = Path(__file__).resolve().parents[1] / "nexis_hub.db"
MONEY_FIELD_MARKERS = ("amount", "balance", "commission", "fee", "total", "net_")


def quoted_identifier(name: str) -> str:
    """Escape identifiers returned by SQLite before using them in SQL."""
    return '"' + name.replace('"', '""') + '"'


def preflight_sqlite(source: Path) -> dict:
    source = Path(source).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Base SQLite introuvable : {source}")

    # Read only: do not create/alter the source DB, and keep one read snapshot.
    uri = "file:" + quote(str(source), safe="/") + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as conn:
        conn.execute("BEGIN")
        integrity = conn.execute("PRAGMA quick_check").fetchone()[0]
        rows = conn.execute(
            "SELECT name, sql FROM sqlite_master "
            "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        schema_hash = hashlib.sha256(
            json.dumps(rows, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()

        tables = {}
        real_money_columns = []
        for name, _ in rows:
            escaped = quoted_identifier(name)
            count = conn.execute(f"SELECT COUNT(*) FROM {escaped}").fetchone()[0]
            columns = conn.execute(f"PRAGMA table_info({escaped})").fetchall()
            foreign_keys = conn.execute(f"PRAGMA foreign_key_list({escaped})").fetchall()
            tables[name] = {
                "rows": count,
                "columns": [
                    {"name": c[1], "type": c[2], "not_null": bool(c[3]), "primary_key": bool(c[5])}
                    for c in columns
                ],
                "foreign_keys": [
                    {"from": fk[3], "references_table": fk[2], "references_column": fk[4]}
                    for fk in foreign_keys
                ],
            }
            for column in columns:
                if column[2].upper().startswith("REAL") and any(
                    token in column[1].lower() for token in MONEY_FIELD_MARKERS
                ):
                    real_money_columns.append(f"{name}.{column[1]}")

        fk_issues = Counter()
        for table_name, _row_id, _parent, _fk_id in conn.execute("PRAGMA foreign_key_check"):
            fk_issues[table_name] += 1
        conn.rollback()

    blockers = []
    if integrity != "ok":
        blockers.append("integrity_check_failed")
    if fk_issues:
        blockers.append("foreign_key_violations")

    return {
        "source_name": source.name,
        "source_type": "SQLite",
        "schema_sha256": schema_hash,
        "table_count": len(tables),
        "tables": tables,
        "integrity": integrity,
        "foreign_key_violations_by_table": dict(sorted(fk_issues.items())),
        "money_columns_requiring_decimal_review": sorted(real_money_columns),
        "blockers": blockers,
        "ready_for_mapping_review": not blockers,
        "actual_data_transferred": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyse SQLite en lecture seule avant migration PostgreSQL"
    )
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, help="Rapport JSON sans données personnelles")
    args = parser.parse_args()

    report = preflight_sqlite(args.source)
    payload = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        output = args.output.expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("x", encoding="utf-8") as handle:
            handle.write(payload)
        print(f"Rapport de pré-migration : {output}")
    else:
        print(payload, end="")

    if report["blockers"]:
        raise SystemExit("Pré-migration bloquée : corriger les incohérences signalées")


if __name__ == "__main__":
    main()
