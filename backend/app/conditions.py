"""Conditions d'utilisation : la case à cocher obligatoire, sur tous les canaux.

Seul module qui écrit `legal_document_versions` et `legal_acceptances`, et
seule source des règles (CONCEPTION_CONDITIONS.md). Les canaux (bot Telegram,
Mini App, WhatsApp, application) ne font qu'afficher la case : c'est ici que
se décide si une personne peut s'inscrire ou agir.

Règles (décision de Ben, 2026-11-20) :

- Une acceptation appartient au **compte Nexis**, jamais à un identifiant de
  canal : relier WhatsApp à un compte Telegram ne demande pas de recocher.
- Client : les CGU. Prestataire : les CGU et les conditions des prestataires.
  Un client qui devient prestataire coche les conditions des prestataires
  (et les CGU si une nouvelle version est entrée en vigueur entre-temps).
- L'inscription porte l'acceptation : le profil et la case cochée sont
  enregistrés dans la même transaction, ou rien ne l'est.
- On accepte le texte qu'on a vu : une acceptation nomme une version, qui
  doit être celle en vigueur (`terms_version_outdated` sinon).
- Nouvelle version en vigueur : chacun recoche avant toute nouvelle action
  (`terms_not_accepted`). Ce qui est déjà engagé (mission en cours, litige,
  retrait de son propre argent) reste possible : une personne qui refuse les
  nouvelles conditions n'est jamais privée de son argent.
- **Aucune version publiée = personne ne passe** (`terms_unavailable`) : la
  case est obligatoire, on ne laisse pas entrer sans elle. Publier les
  versions est une étape de la mise en service.
"""

import argparse
import hashlib
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import exists, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.models import (
    LEGAL_DOCUMENTS,
    LEGAL_ROLES,
    LEGAL_SURFACES,
    LegalAcceptance,
    LegalDocumentVersion,
    NexisAccount,
)

logger = logging.getLogger(__name__)

CGU = "cgu"
PROVIDER_TERMS = "conditions_prestataires"
CLIENT = "client"
PROVIDER = "provider"
# Ordre d'affichage : les CGU d'abord.
REQUIRED_DOCUMENTS = {
    CLIENT: (CGU,),
    PROVIDER: (CGU, PROVIDER_TERMS),
}
assert set(REQUIRED_DOCUMENTS) == set(LEGAL_ROLES)
assert {key for keys in REQUIRED_DOCUMENTS.values() for key in keys} == set(LEGAL_DOCUMENTS)

LANGUAGES = ("fr", "ln", "en")
# Court, sans espace ni « : » : la version voyage dans les boutons Telegram
# (64 octets au plus) et dans les adresses des pages de lecture.
VERSION_PATTERN = re.compile(r"[A-Za-z0-9._-]{1,30}")
MAX_TEXT_LENGTH = 500_000

# D'où une personne de chaque canal peut cocher la case. La Mini App appelle
# avec la clé du bot Telegram.
SURFACES_BY_CHANNEL = {
    "telegram": ("telegram_bot", "mini_app"),
    "whatsapp": ("whatsapp",),
    "app": ("app",),
}
assert {surface for surfaces in SURFACES_BY_CHANNEL.values() for surface in surfaces} == set(LEGAL_SURFACES)


class ConditionsError(Exception):
    """Refus, avec un code stable que les canaux traduisent. `missing` : les
    versions à accepter (refus `terms_not_accepted`)."""

    def __init__(self, code: str, http_status: int = 409, missing: list[dict] | None = None):
        super().__init__(code)
        self.code = code
        self.http_status = http_status
        self.missing = missing or []

    def detail(self) -> dict:
        detail = {"code": self.code}
        if self.code == "terms_not_accepted":
            detail["missing"] = self.missing
        return detail


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def version_view(version: LegalDocumentVersion) -> dict:
    return {
        "document_key": version.document_key,
        "version": version.version,
        "effective_at": version.effective_at.isoformat(),
    }


# --- Publication ---------------------------------------------------------------


def publish_version(
    db: Session,
    document_key: str,
    version: str,
    text: str,
    *,
    language: str = "fr",
    effective_at: datetime | None = None,
    now: datetime | None = None,
) -> LegalDocumentVersion:
    """Publie une version (sans valider la transaction). Une version déjà
    publiée n'est jamais remplacée ; une version datée avant la précédente
    est refusée (elle ne deviendrait jamais celle en vigueur)."""
    now = now or _utcnow()
    effective_at = effective_at or now
    if document_key not in LEGAL_DOCUMENTS:
        raise ConditionsError("unknown_document", 422)
    version = (version or "").strip()
    if not VERSION_PATTERN.fullmatch(version):
        raise ConditionsError("invalid_version", 422)
    if language not in LANGUAGES:
        raise ConditionsError("invalid_language", 422)
    if not isinstance(text, str) or not text.strip() or len(text) > MAX_TEXT_LENGTH:
        raise ConditionsError("invalid_text", 422)
    if effective_at < now:
        # Une acceptation passée ne peut pas porter sur un texte publié après.
        raise ConditionsError("effective_in_past", 422)
    latest = db.scalars(
        select(LegalDocumentVersion)
        .where(LegalDocumentVersion.document_key == document_key)
        .order_by(LegalDocumentVersion.effective_at.desc(), LegalDocumentVersion.id.desc())
        .limit(1)
    ).first()
    if latest is not None and effective_at <= latest.effective_at:
        raise ConditionsError("effective_before_previous_version", 422)
    row = LegalDocumentVersion(
        document_key=document_key,
        version=version,
        language=language,
        text=text,
        text_sha256=fingerprint(text),
        effective_at=effective_at,
        published_at=now,
    )
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
    except IntegrityError as error:
        raise ConditionsError("version_already_published", 409) from error
    return row


# --- Lecture -------------------------------------------------------------------


def current_version(db: Session, document_key: str, now: datetime | None = None) -> LegalDocumentVersion | None:
    """Dernière version entrée en vigueur ; une version à date future attend."""
    now = now or _utcnow()
    return db.scalars(
        select(LegalDocumentVersion)
        .where(LegalDocumentVersion.document_key == document_key, LegalDocumentVersion.effective_at <= now)
        .order_by(LegalDocumentVersion.effective_at.desc(), LegalDocumentVersion.id.desc())
        .limit(1)
    ).first()


def find_version(db: Session, document_key: str, version: str) -> LegalDocumentVersion | None:
    return db.scalars(
        select(LegalDocumentVersion).where(
            LegalDocumentVersion.document_key == document_key, LegalDocumentVersion.version == version
        )
    ).first()


def required_versions(db: Session, role: str, now: datetime | None = None) -> list[LegalDocumentVersion]:
    """Versions en vigueur qu'un compte de ce rôle doit avoir acceptées. Un
    document exigé sans version en vigueur : `terms_unavailable`, personne ne
    passe (la case est obligatoire, jamais sautée faute de texte)."""
    if role not in REQUIRED_DOCUMENTS:
        raise ConditionsError("unknown_role", 422)
    versions = []
    for key in REQUIRED_DOCUMENTS[role]:
        version = current_version(db, key, now)
        if version is None:
            raise ConditionsError("terms_unavailable", 503)
        versions.append(version)
    return versions


def _accepted(db: Session, account_id: int, version_id: int) -> bool:
    return (
        db.scalar(
            select(LegalAcceptance.id).where(
                LegalAcceptance.account_id == account_id, LegalAcceptance.version_id == version_id
            )
        )
        is not None
    )


def missing(db: Session, account_id: int | None, role: str, now: datetime | None = None) -> list[dict]:
    """Versions en vigueur exigées pour ce rôle que ce compte n'a pas
    acceptées (toutes, pour une personne encore sans compte)."""
    return [
        version_view(version)
        for version in required_versions(db, role, now)
        if account_id is None or not _accepted(db, account_id, version.id)
    ]


def held_roles(db: Session, account_id: int | None) -> list[str]:
    account = db.get(NexisAccount, account_id) if account_id is not None else None
    roles = set(account.roles or []) if account is not None else set()
    return [role for role in LEGAL_ROLES if role in roles]


def status(db: Session, account_id: int | None, now: datetime | None = None) -> dict:
    """Ce qu'un compte doit accepter : pour les rôles qu'il a (`missing`), et
    pour chaque rôle s'il le prenait (`by_role`, pour l'écran d'inscription ou
    de bascule). `terms_unavailable` si rien n'est publié."""
    now = now or _utcnow()
    by_role = {role: missing(db, account_id, role, now) for role in LEGAL_ROLES}
    roles = held_roles(db, account_id)
    pending: dict[str, dict] = {}
    for role in roles:
        for item in by_role[role]:
            pending.setdefault(item["document_key"], item)
    # Ordre des documents : celui de REQUIRED_DOCUMENTS[PROVIDER] (CGU d'abord).
    ordered = [pending[key] for key in REQUIRED_DOCUMENTS[PROVIDER] if key in pending]
    return {
        "roles": roles,
        "missing": ordered,
        "complete": not ordered,
        # Rôle à envoyer avec l'acceptation de `missing`.
        "role": PROVIDER if any(item["document_key"] == PROVIDER_TERMS for item in ordered) else CLIENT,
        "by_role": by_role,
    }


def require(db: Session, account_id: int | None, role: str, now: datetime | None = None) -> None:
    """Refuse (`terms_not_accepted`, avec les versions à accepter) un compte
    qui n'a pas accepté les versions en vigueur exigées pour ce rôle."""
    pending = missing(db, account_id, role, now)
    if pending:
        raise ConditionsError("terms_not_accepted", 409, missing=pending)


def accepted_clauses(db: Session, account_column, role: str, now: datetime | None = None) -> list:
    """Conditions SQL « ce compte a accepté chaque version exigée pour ce
    rôle », pour filtrer une requête (prestataires à qui proposer une
    mission). Rien de publié : `terms_unavailable`, comme partout."""
    return [
        exists().where(LegalAcceptance.account_id == account_column, LegalAcceptance.version_id == version.id)
        for version in required_versions(db, role, now)
    ]


# --- Acceptation ---------------------------------------------------------------


def checked_surface(channel: str, surface) -> str:
    if surface not in SURFACES_BY_CHANNEL.get(channel, ()):
        raise ConditionsError("invalid_surface", 422)
    return surface


def accept(
    db: Session,
    account_id: int,
    role: str,
    documents,
    *,
    surface: str,
    language: str,
    now: datetime | None = None,
) -> list[LegalAcceptance]:
    """Enregistre la case cochée pour ces versions (sans valider la
    transaction). Chaque version doit être celle en vigueur d'un document
    exigé pour ce rôle ; sinon rien n'est enregistré. Recocher une version
    déjà acceptée ne crée rien. Le compte est verrouillé pendant l'écriture.

    `documents` : liste de {"document_key", "version"}."""
    now = now or _utcnow()
    if role not in REQUIRED_DOCUMENTS:
        raise ConditionsError("unknown_role", 422)
    if surface not in LEGAL_SURFACES:
        raise ConditionsError("invalid_surface", 422)
    if language not in LANGUAGES:
        raise ConditionsError("invalid_language", 422)
    if not isinstance(documents, (list, tuple)) or not documents or len(documents) > len(LEGAL_DOCUMENTS):
        raise ConditionsError("invalid_terms", 422)
    targets = []
    seen = set()
    for document in documents:
        key = document.get("document_key") if isinstance(document, dict) else None
        version = document.get("version") if isinstance(document, dict) else None
        if key not in REQUIRED_DOCUMENTS[role] or key in seen or not isinstance(version, str):
            raise ConditionsError("invalid_terms", 422)
        seen.add(key)
        target = find_version(db, key, version)
        if target is None:
            raise ConditionsError("terms_version_not_found", 404)
        current = current_version(db, key, now)
        if current is None or current.id != target.id:
            raise ConditionsError("terms_version_outdated", 409)
        targets.append(target)

    if db.get(NexisAccount, account_id, with_for_update=True) is None:
        raise ConditionsError("account_not_found", 404)
    rows = []
    for target in targets:
        existing = db.scalars(
            select(LegalAcceptance).where(
                LegalAcceptance.account_id == account_id, LegalAcceptance.version_id == target.id
            )
        ).first()
        if existing is not None:
            rows.append(existing)
            continue
        row = LegalAcceptance(
            account_id=account_id,
            version_id=target.id,
            role=role,
            surface=surface,
            language=language,
            accepted_at=now,
        )
        db.add(row)
        db.flush()
        rows.append(row)
    return rows


def accept_for_signup(
    db: Session,
    account_id: int,
    role: str,
    terms,
    *,
    channel: str,
    language: str,
    now: datetime | None = None,
) -> None:
    """Inscription (ou bascule vers prestataire) : enregistre la case cochée
    envoyée avec l'inscription, puis refuse si une version exigée pour ce
    rôle manque encore. L'appelant annule toute la transaction sur un refus :
    pas de profil sans case cochée.

    `terms` : None (rien coché) ou {"surface", "documents": [...]}."""
    now = now or _utcnow()
    if terms is not None:
        surface = checked_surface(channel, terms.get("surface"))
        accept(db, account_id, role, terms.get("documents"), surface=surface, language=language, now=now)
    require(db, account_id, role, now)


# --- Commande d'exploitation -----------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """Publier une version, ou voir les versions publiées :

        python -m backend.app.conditions publier cgu 2026-11-20 chemin/cgu.md [--en-vigueur 2026-12-01T00:00]
        python -m backend.app.conditions liste
    """
    from backend.app.database import SessionLocal

    parser = argparse.ArgumentParser(prog="python -m backend.app.conditions")
    commandes = parser.add_subparsers(dest="commande", required=True)
    publier = commandes.add_parser("publier", help="publie une version d'un document")
    publier.add_argument("document", choices=LEGAL_DOCUMENTS)
    publier.add_argument("version")
    publier.add_argument("fichier", help="texte complet, en UTF-8")
    publier.add_argument("--langue", default="fr", choices=LANGUAGES)
    publier.add_argument("--en-vigueur", help="date UTC d'entrée en vigueur (AAAA-MM-JJTHH:MM), maintenant par défaut")
    commandes.add_parser("liste", help="affiche les versions publiées")
    args = parser.parse_args(argv)

    with SessionLocal() as db:
        if args.commande == "liste":
            rows = db.scalars(
                select(LegalDocumentVersion).order_by(LegalDocumentVersion.document_key, LegalDocumentVersion.effective_at)
            ).all()
            for row in rows:
                print(f"{row.document_key} {row.version} en vigueur le {row.effective_at:%d/%m/%Y %H:%M} UTC  sha256={row.text_sha256[:12]}…")
            for key in LEGAL_DOCUMENTS:
                if current_version(db, key) is None:
                    print(f"Aucune version en vigueur pour {key} : aucune inscription ne peut aboutir.")
            return 0
        try:
            text = Path(args.fichier).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            print(f"Fichier illisible : {error}", file=sys.stderr)
            return 1
        try:
            effective_at = datetime.fromisoformat(args.en_vigueur) if args.en_vigueur else None
        except ValueError:
            print("Date d'entrée en vigueur invalide (AAAA-MM-JJTHH:MM, en UTC).", file=sys.stderr)
            return 1
        try:
            row = publish_version(db, args.document, args.version, text, language=args.langue, effective_at=effective_at)
            db.commit()
        except ConditionsError as error:
            db.rollback()
            print(f"Refusé : {error.code}", file=sys.stderr)
            return 1
        print(f"Publié : {row.document_key} {row.version}, en vigueur le {row.effective_at:%d/%m/%Y %H:%M} UTC, sha256={row.text_sha256}")
        logger.warning("Conditions publiées : %s %s", row.document_key, row.version)
    return 0


if __name__ == "__main__":
    sys.exit(main())
