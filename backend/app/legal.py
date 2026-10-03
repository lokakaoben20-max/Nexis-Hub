"""Acceptation des conditions : qui a accepté quelle version, quand, par quel
canal. Seul module qui écrit `legal_document_versions` et
`legal_acceptances`. Voir CONCEPTION_ACCEPTATIONS.md.

Une acceptation appartient au compte Nexis, jamais à un identifiant de canal :
relier WhatsApp à un compte Telegram ne demande pas de réaccepter.
"""

import hashlib
import re
from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app import ledger
from backend.app.models import LegalAcceptance, LegalDocumentVersion, NexisAccount

GENERAL_TERMS = "conditions_generales"
DATA_CONSENT = "donnees_transferts"
PROVIDER_TERMS = "conditions_prestataires"
DOCUMENT_KEYS = (GENERAL_TERMS, DATA_CONSENT, PROVIDER_TERMS)

CLIENT = "client"
PROVIDER = "provider"
# Ordre d'affichage : conditions, puis consentement, puis conditions
# prestataires (dossier juridique, onglet « Textes dans le bot »).
REQUIRED_DOCUMENTS = {
    CLIENT: (GENERAL_TERMS, DATA_CONSENT),
    PROVIDER: (GENERAL_TERMS, DATA_CONSENT, PROVIDER_TERMS),
}

ACCEPTED = "accepted"
REFUSED = "refused"
DECISIONS = {ACCEPTED, REFUSED}
CHANNELS = {"telegram", "whatsapp", "mini_app"}
# Court et sans « : » : la version voyage dans les boutons Telegram
# (callback_data limité à 64 octets).
VERSION_PATTERN = re.compile(r"[A-Za-z0-9._-]{1,30}")


class LegalError(Exception):
    """Refus métier, code stable traduit par le bot."""

    def __init__(self, code: str, http_status: int = 409):
        super().__init__(code)
        self.code = code
        self.http_status = http_status


def text_fingerprint(text: bytes) -> str:
    return hashlib.sha256(text).hexdigest()


def publish_version(
    db: Session,
    document_key: str,
    version: str,
    url: str,
    text: bytes,
    effective_at: datetime,
) -> LegalDocumentVersion:
    """Publie une version. Une version déjà publiée n'est jamais remplacée."""
    if document_key not in DOCUMENT_KEYS:
        raise LegalError("unknown_document", 422)
    version = version.strip()
    url = url.strip()
    if not VERSION_PATTERN.fullmatch(version) or not url.startswith("https://"):
        raise LegalError("invalid_version", 422)
    if not text.strip():
        raise LegalError("empty_text", 422)
    latest = (
        db.query(LegalDocumentVersion)
        .filter(LegalDocumentVersion.document_key == document_key)
        .order_by(LegalDocumentVersion.effective_at.desc())
        .first()
    )
    if latest is not None and effective_at <= latest.effective_at:
        # Les versions se succèdent dans l'ordre de publication : une version
        # datée avant la précédente ne deviendrait jamais celle en vigueur.
        raise LegalError("effective_before_previous_version", 422)
    row = LegalDocumentVersion(
        document_key=document_key,
        version=version,
        url=url,
        text_sha256=text_fingerprint(text),
        effective_at=effective_at,
    )
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
    except IntegrityError as error:
        raise LegalError("version_already_published") from error
    return row


def current_version(db: Session, document_key: str, now: datetime | None = None) -> LegalDocumentVersion | None:
    """Dernière version entrée en vigueur ; une version à date future attend."""
    now = now or ledger._utcnow()
    return (
        db.query(LegalDocumentVersion)
        .filter(LegalDocumentVersion.document_key == document_key, LegalDocumentVersion.effective_at <= now)
        .order_by(LegalDocumentVersion.effective_at.desc(), LegalDocumentVersion.id.desc())
        .first()
    )


def latest_decision(db: Session, account_id: int, version_id: int) -> LegalAcceptance | None:
    return (
        db.query(LegalAcceptance)
        .filter(LegalAcceptance.account_id == account_id, LegalAcceptance.version_id == version_id)
        .order_by(LegalAcceptance.decided_at.desc(), LegalAcceptance.id.desc())
        .first()
    )


def _version_dict(version: LegalDocumentVersion) -> dict:
    return {"document_key": version.document_key, "version": version.version, "url": version.url}


def missing_for_account(db: Session, account_id: int | None, role: str, now: datetime | None = None) -> list[dict]:
    """Versions en vigueur exigées pour ce rôle et pas acceptées (décision la
    plus récente différente de `accepted`). Un document jamais publié n'est
    pas exigé : il n'y a rien à accepter."""
    if role not in REQUIRED_DOCUMENTS:
        raise LegalError("unknown_role", 422)
    missing = []
    for key in REQUIRED_DOCUMENTS[role]:
        version = current_version(db, key, now)
        if version is None:
            continue
        decision = latest_decision(db, account_id, version.id) if account_id is not None else None
        if decision is None or decision.decision != ACCEPTED:
            missing.append(_version_dict(version))
    return missing


def status(db: Session, channel: str, external_id, role: str) -> dict:
    if channel not in CHANNELS:
        raise LegalError("unknown_channel", 422)
    account_id = ledger.account_id_for(db, channel, external_id)
    missing = missing_for_account(db, account_id, role)
    return {"role": role, "missing": missing, "complete": not missing}


def record_decision(
    db: Session,
    channel: str,
    external_id,
    document_key: str,
    version: str,
    decision: str,
    language: str | None = None,
) -> LegalAcceptance:
    """Enregistre un choix sur la version en vigueur, et seulement elle : on
    accepte le texte qu'on a vu. Renvoyer la même décision que la plus récente
    ne crée pas de ligne. Le compte est verrouillé pendant l'écriture."""
    if channel not in CHANNELS:
        raise LegalError("unknown_channel", 422)
    if document_key not in DOCUMENT_KEYS:
        raise LegalError("unknown_document", 422)
    if decision not in DECISIONS:
        raise LegalError("unknown_decision", 422)
    target = (
        db.query(LegalDocumentVersion)
        .filter(LegalDocumentVersion.document_key == document_key, LegalDocumentVersion.version == version)
        .one_or_none()
    )
    if target is None:
        raise LegalError("legal_version_not_found", 404)
    current = current_version(db, document_key)
    if current is None or current.id != target.id:
        raise LegalError("terms_version_outdated")

    account_id = ledger.account_id_for(db, channel, external_id, create=True)
    db.get(NexisAccount, account_id, with_for_update=True)
    previous = latest_decision(db, account_id, target.id)
    if previous is not None and previous.decision == decision:
        return previous
    row = LegalAcceptance(
        account_id=account_id,
        version_id=target.id,
        decision=decision,
        channel=channel,
        language=language,
        decided_at=ledger._utcnow(),
    )
    db.add(row)
    db.flush()
    return row
