"""Publie une version d'un document juridique (CONCEPTION_ACCEPTATIONS.md).

Usage, depuis la racine du dépôt :

    python -m backend.publish_legal_version conditions_generales 2026-11-01 \
        https://exemple/conditions-v1 textes/conditions-v1.txt --effective 2026-11-01T00:00

- Le fichier est le texte exact publié à l'url : son empreinte SHA-256 est
  enregistrée, elle prouve ce que chaque personne a accepté.
- `--effective` (UTC) : date d'entrée en vigueur ; maintenant par défaut. Une
  date future permet d'annoncer un changement avant qu'il s'applique.
- Une version déjà publiée est refusée : un texte corrigé est une nouvelle
  version. Dès qu'une version est en vigueur, le bot exige son acceptation.
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

from backend.app import legal, ledger
from backend.app.database import SessionLocal


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Publie une version d'un document juridique.")
    parser.add_argument("document_key", choices=legal.DOCUMENT_KEYS)
    parser.add_argument("version")
    parser.add_argument("url")
    parser.add_argument("text_file", type=Path)
    parser.add_argument("--effective", type=datetime.fromisoformat, default=None, help="UTC, par ex. 2026-11-01T00:00")
    args = parser.parse_args(argv)

    text = args.text_file.read_bytes()
    effective_at = args.effective or ledger._utcnow()
    if effective_at.tzinfo is not None:
        print("Donnez la date en UTC sans fuseau (ex. 2026-11-01T00:00).", file=sys.stderr)
        return 2
    with SessionLocal() as db:
        try:
            version = legal.publish_version(db, args.document_key, args.version, args.url, text, effective_at)
            db.commit()
        except legal.LegalError as error:
            db.rollback()
            print(f"Refusé : {error.code}", file=sys.stderr)
            return 1
        print(
            f"Publié : {version.document_key} {version.version}, en vigueur le {version.effective_at:%Y-%m-%d %H:%M} UTC, "
            f"empreinte {version.text_sha256}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
