"""Idempotence des actions d'écriture venant d'un canal (étape 2 du plan
WhatsApp, /mnt/project-files/whatsapp/plan-implementation-whatsapp-2026-11-07.md).

Meta renvoie un webhook tant qu'il n'a pas eu de réponse, et peut l'envoyer
plusieurs fois : un même message WhatsApp peut donc arriver deux fois, ou dix
fois en parallèle. Chaque écriture que le service WhatsApp demande au backend
porte l'en-tête `Idempotency-Key` (l'identifiant du message, `wamid`).

La garantie est dans Postgres, **dans la transaction de l'action** :

1. verrou de transaction sur (canal, clé) : une deuxième demande avec la même
   clé attend que la première ait fini (validée ou annulée) ;
2. clé déjà enregistrée : même demande → même réponse, rien n'est refait ;
   autre demande sous la même clé → refus `idempotency_key_reused` ;
3. sinon l'action s'exécute sans valider, la clé et la réponse sont ajoutées,
   puis **une seule** validation écrit les deux ensemble.

Une action refusée (erreur métier) ou interrompue n'enregistre rien : le
message rejoué est réévalué, ce qui est sûr puisque rien n'a été écrit.

Redis n'est pas utilisé ici : une clé perdue ou expirée, ou écrite hors de la
transaction, laisserait passer une deuxième action.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.models import IdempotencyKey

HEADER = "Idempotency-Key"
# Identifiant de message WhatsApp (`wamid.` + base64) et clés d'autres canaux.
_KEY = re.compile(r"[A-Za-z0-9._:=+/-]{8,200}")
# Meta renvoie un webhook non acquitté pendant plusieurs jours : on garde les
# clés bien au-delà.
RETENTION = timedelta(days=30)


class IdempotencyError(Exception):
    def __init__(self, code: str, http_status: int):
        super().__init__(code)
        self.code = code
        self.http_status = http_status


@dataclass(frozen=True)
class Outcome:
    status: int
    body: dict
    replayed: bool


def check_key(key: str | None, *, required: bool) -> str | None:
    if key is None or key == "":
        if required:
            raise IdempotencyError("idempotency_key_required", 400)
        return None
    if not _KEY.fullmatch(key):
        raise IdempotencyError("invalid_idempotency_key", 400)
    return key


def fingerprint(*, route: str, channel: str, actor_id: str, path_params: dict, body: dict) -> str:
    """Empreinte stable de la demande : la même clé ne vaut que pour la même
    route, le même acteur, les mêmes paramètres et le même corps."""
    canonical = json.dumps(
        {"route": route, "channel": channel, "actor": actor_id, "path": path_params, "body": body},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def _lock(db: Session, channel: str, key: str) -> None:
    """Verrou de transaction (Postgres) sur (canal, clé), relâché à la
    validation ou à l'annulation. SQLite n'a qu'un écrivain à la fois."""
    if db.get_bind().dialect.name == "postgresql":
        digest = hashlib.sha256(f"idempotency:{channel}:{key}".encode()).digest()
        db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": int.from_bytes(digest[:8], "big", signed=True)})


def _stored(db: Session, channel: str, key: str) -> IdempotencyKey | None:
    return db.query(IdempotencyKey).filter_by(channel=channel, key=key).one_or_none()


def _replay(row: IdempotencyKey, request_fingerprint: str) -> Outcome:
    if row.fingerprint != request_fingerprint:
        raise IdempotencyError("idempotency_key_reused", 409)
    return Outcome(row.response_status, row.response_body, replayed=True)


def run(
    db: Session,
    *,
    channel: str,
    key: str,
    request_fingerprint: str,
    action: Callable[[], dict],
    now: datetime | None = None,
) -> Outcome:
    """Exécute `action` une seule fois pour (canal, clé). `action` écrit dans
    `db` sans valider et rend le corps de la réponse (succès, 200). En cas
    d'exception, l'appelant annule la transaction : rien n'est enregistré."""
    _lock(db, channel, key)
    row = _stored(db, channel, key)
    if row is not None:
        return _replay(row, request_fingerprint)

    body = action()
    db.add(
        IdempotencyKey(
            channel=channel,
            key=key,
            fingerprint=request_fingerprint,
            response_status=200,
            response_body=body,
            created_at=now or datetime.utcnow(),
        )
    )
    try:
        db.commit()
    except IntegrityError:
        # Garde-fou si le verrou n'a pas joué (autre base) : la clé a été
        # enregistrée par une demande concurrente, notre action est annulée.
        db.rollback()
        row = _stored(db, channel, key)
        if row is None:
            raise
        return _replay(row, request_fingerprint)
    return Outcome(200, body, replayed=False)


def purge(db: Session, *, now: datetime | None = None) -> int:
    """Efface les clés plus vieilles que `RETENTION`."""
    cutoff = (now or datetime.utcnow()) - RETENTION
    deleted = db.query(IdempotencyKey).filter(IdempotencyKey.created_at < cutoff).delete(synchronize_session=False)
    db.commit()
    return deleted
