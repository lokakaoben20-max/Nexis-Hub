"""Safely back up the NEXIS SQLite database using SQLite's online backup API.

Usage:
    python scripts/backup_sqlite.py --destination backups/nexis-2026-11-18.db

The source DB is read-only; an existing backup is never overwritten.
"""

import argparse
import sqlite3
from contextlib import closing
from pathlib import Path


DEFAULT_SOURCE = Path(__file__).resolve().parents[1] / "nexis_hub.db"


def backup_sqlite(source: Path, destination: Path) -> dict:
    source = Path(source).expanduser().resolve()
    destination = Path(destination).expanduser().resolve()

    if not source.is_file():
        raise FileNotFoundError(f"Base SQLite introuvable : {source}")
    if source == destination:
        raise ValueError("La sauvegarde ne peut pas écraser sa base source")
    if destination.exists():
        raise FileExistsError(f"Une sauvegarde existe déjà : {destination}")

    # Read-only mode guarantees that running a backup cannot create a missing source DB.
    with closing(sqlite3.connect(f"file:{source}?mode=ro", uri=True)) as source_conn:
        source_check = source_conn.execute("PRAGMA quick_check").fetchone()[0]
        if source_check != "ok":
            raise RuntimeError(f"Base source corrompue : {source_check}")

        destination.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive creation protects any previously saved backup.
        with destination.open("xb"):
            pass

        try:
            with closing(sqlite3.connect(destination)) as backup_conn:
                source_conn.backup(backup_conn)
                integrity = backup_conn.execute("PRAGMA integrity_check").fetchone()[0]
                if integrity != "ok":
                    raise RuntimeError(f"Sauvegarde invalide : {integrity}")
                foreign_key_issues = sum(
                    1 for _ in backup_conn.execute("PRAGMA foreign_key_check")
                )
        except Exception:
            # Only the newly created, incomplete backup is removed.
            destination.unlink(missing_ok=True)
            raise

    return {
        "path": str(destination),
        "integrity": "ok",
        "foreign_key_issues": foreign_key_issues,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Sauvegarde vérifiée de Nexis SQLite")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()

    result = backup_sqlite(args.source, args.destination)
    print(f"Sauvegarde créée : {result['path']} (intégrité : {result['integrity']})")
    if result["foreign_key_issues"]:
        print(
            f"ATTENTION : {result['foreign_key_issues']} incohérence(s) de clés étrangères. "
            "Ne pas lancer de migration avant correction."
        )


if __name__ == "__main__":
    main()
