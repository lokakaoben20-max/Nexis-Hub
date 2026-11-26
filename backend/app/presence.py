"""Arrivée confirmée du prestataire chez le client.

Conception : localisation/confirmation-arrivee-et-devis-sur-place-2026-11-08.md
(décisions de Ben du 8 novembre 2026) et CONCEPTION_MISSIONS.md, « Arrivée
confirmée ».

- Le prestataire signale « je suis arrivé » : le client reçoit la question
  « Votre prestataire est-il arrivé ? », avec la photo et le prénom du
  prestataire et son code de présence.
- La présence est confirmée par **un seul geste avec preuve** : l'appui du
  client (« Oui, il est là ») ou le code de présence du client, tapé par le
  prestataire. Le « je suis arrivé » du prestataire seul ne confirme rien.
- Présence confirmée = mission démarrée, dans la même transaction (plus de
  bouton « Démarrer »).
- « Ce n'est pas lui » : litige ouvert, fonds gelés, admin prévenu.

Le code de présence n'est jamais enregistré : il est recalculé à partir de la
clé `PRESENCE_CODE_KEY` et du numéro de mission. Il n'est donné qu'au client
de la mission, jamais au prestataire, jamais dans un journal. Cinq mauvais
codes par mission au plus ; ensuite seul l'appui du client confirme, et
l'admin est prévenu.

Toutes les décisions passent par le verrou de la mission : deux réponses
simultanées (le client appuie, le prestataire tape le code) n'enregistrent
qu'une présence. Les messages sont des notifications écrites dans la même
transaction que la décision (backend/app/evenements.py) : un message ne
décrit que ce qui est enregistré, et rien d'enregistré n'est oublié.
"""

import hashlib
import hmac
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from backend.app import evenements, ledger
from backend.app.models import BotMission, MissionPresence

logger = logging.getLogger(__name__)

MAX_CODE_ATTEMPTS = 5
# Un nouvel appui sur « Je suis arrivé » repose la question au client (message
# perdu, client qui n'a pas vu), mais pas plus d'une fois toutes les 2 minutes :
# le bouton ne doit pas servir à harceler le client.
ASK_AGAIN_AFTER = timedelta(minutes=2)
WRONG_PERSON_REASON = "Personne arrivée différente du prestataire inscrit (signalé par le client à l'arrivée)"
CODE_LENGTH = 4


class PresenceCodeRefused(ledger.MoneyError):
    """Mauvais code de présence (compté), ou code bloqué. `just_locked` : ce
    code-ci a épuisé les essais, l'admin doit être prévenu une fois."""

    def __init__(self, code: str, mission: BotMission, attempts_left: int, just_locked: bool = False):
        super().__init__(code, 403 if code == "presence_code_locked" else 400, mission)
        self.attempts_left = attempts_left
        self.just_locked = just_locked


@dataclass
class PresenceResult:
    mission: BotMission
    presence: MissionPresence
    # Ce que cet appel a changé, pour n'envoyer chaque message qu'une fois
    # (une réponse rejouée ne prévient personne une seconde fois).
    changed: bool = False
    client_asked: bool = False
    events: list[str] = field(default_factory=list)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _code_key() -> bytes:
    key = os.getenv("PRESENCE_CODE_KEY", "")
    if len(key) < 32:
        # Sans clé solide, aucun code n'est donné ni vérifié.
        raise ledger.MoneyError("presence_not_configured", 503)
    return key.encode()


def presence_code(mission_id: int) -> str:
    """Code de présence de la mission : 4 chiffres, propre à la mission,
    recalculé à la demande (rien en base)."""
    digest = hmac.new(_code_key(), f"presence-code:v1:{mission_id}".encode(), hashlib.sha256).digest()
    return f"{int.from_bytes(digest[:8], 'big') % 10 ** CODE_LENGTH:0{CODE_LENGTH}d}"


def _presence(db: Session, mission_id: int, create: bool = False) -> MissionPresence | None:
    presence = db.get(MissionPresence, mission_id)
    if presence is None and create:
        presence = MissionPresence(mission_id=mission_id, failed_code_attempts=0)
        db.add(presence)
        db.flush()
    return presence


def _require_waiting_for_arrival(db: Session, mission: BotMission) -> None:
    """Payée, ni en litige ni réglée, et pas encore démarrée."""
    ledger.require_open_escrow(db, mission)
    if mission.status != "confirmed":
        raise ledger.MoneyError("invalid_state", mission=mission)


def _confirm(db: Session, mission: BotMission, presence: MissionPresence, by: str) -> None:
    presence.confirmed_at = _utcnow()
    presence.confirmed_by = by
    ledger.begin_work(db, mission)


def declare_arrival(db: Session, mission_id: int, provider_account_id: int) -> PresenceResult:
    """« Je suis arrivé » : ne confirme rien, pose la question au client."""
    mission = ledger.lock_mission(db, mission_id)
    ledger.require_mission_provider(db, mission, provider_account_id)
    presence = _presence(db, mission_id)
    if presence is not None and presence.confirmed_at is not None:
        return PresenceResult(mission, presence)
    _require_waiting_for_arrival(db, mission)
    presence = presence or _presence(db, mission_id, create=True)
    now = _utcnow()
    result = PresenceResult(mission, presence)
    if presence.arrival_declared_at is None:
        presence.arrival_declared_at = now
        result.changed = True
    answered_not_yet = presence.not_yet_at is not None and presence.client_asked_at is not None and presence.not_yet_at >= presence.client_asked_at
    if presence.client_asked_at is None or answered_not_yet or now - presence.client_asked_at >= ASK_AGAIN_AFTER:
        presence.client_asked_at = now
        result.client_asked = result.changed = True
        # La question part avec ce qui l'a causée, dans la même transaction.
        evenements.presence_question(db, mission, presence_code(mission_id), now)
    db.commit()
    return result


def confirm_by_client(db: Session, mission_id: int, client_account_id: int) -> PresenceResult:
    """« Oui, il est là » : présence confirmée et mission démarrée."""
    mission = ledger.lock_mission(db, mission_id)
    ledger.require_mission_client(mission, client_account_id)
    presence = _presence(db, mission_id)
    if presence is not None and presence.confirmed_at is not None:
        return PresenceResult(mission, presence)
    _require_waiting_for_arrival(db, mission)
    presence = presence or _presence(db, mission_id, create=True)
    _confirm(db, mission, presence, "client")
    # Le client voit la réponse dans son canal ; le prestataire est prévenu.
    evenements.presence_confirmed(db, mission, tell_client=False, tell_provider=True)
    db.commit()
    return PresenceResult(mission, presence, changed=True, events=["confirmed"])


def confirm_by_code(db: Session, mission_id: int, provider_account_id: int, code: str) -> PresenceResult:
    """Code de présence donné de vive voix par le client et tapé par le
    prestataire. Un code mal formé n'est pas compté ; un mauvais code l'est,
    et le compte est enregistré avant le refus."""
    code = (code or "").strip()
    if len(code) != CODE_LENGTH or not code.isascii() or not code.isdigit():
        raise ledger.MoneyError("invalid_presence_code", 400)
    mission = ledger.lock_mission(db, mission_id)
    ledger.require_mission_provider(db, mission, provider_account_id)
    presence = _presence(db, mission_id)
    if presence is not None and presence.confirmed_at is not None:
        return PresenceResult(mission, presence)
    _require_waiting_for_arrival(db, mission)
    expected = presence_code(mission_id)
    presence = presence or _presence(db, mission_id, create=True)
    if presence.code_locked_at is not None:
        raise PresenceCodeRefused("presence_code_locked", mission, 0)
    if hmac.compare_digest(code, expected):
        _confirm(db, mission, presence, "presence_code")
        evenements.presence_confirmed(db, mission, tell_client=True, tell_provider=False)
        db.commit()
        return PresenceResult(mission, presence, changed=True, events=["confirmed"])
    presence.failed_code_attempts += 1
    just_locked = presence.failed_code_attempts >= MAX_CODE_ATTEMPTS
    if just_locked:
        presence.code_locked_at = _utcnow()
        evenements.presence_code_locked(db, mission, MAX_CODE_ATTEMPTS)
    attempts_left = MAX_CODE_ATTEMPTS - presence.failed_code_attempts
    # Enregistré avant le refus : l'appelant annule la transaction en cours
    # sur un refus, l'essai doit rester compté.
    db.commit()
    raise PresenceCodeRefused("presence_code_locked" if just_locked else "wrong_presence_code", mission, attempts_left, just_locked)


def answer_not_yet(db: Session, mission_id: int, client_account_id: int) -> PresenceResult:
    """« Pas encore » : rien ne bouge ; le prestataire est prévenu une fois
    par question."""
    mission = ledger.lock_mission(db, mission_id)
    ledger.require_mission_client(mission, client_account_id)
    presence = _presence(db, mission_id)
    if presence is not None and presence.confirmed_at is not None:
        return PresenceResult(mission, presence)
    _require_waiting_for_arrival(db, mission)
    presence = presence or _presence(db, mission_id, create=True)
    first_answer = presence.not_yet_at is None or (
        presence.client_asked_at is not None and presence.not_yet_at < presence.client_asked_at
    )
    presence.not_yet_at = _utcnow()
    if first_answer:
        evenements.presence_not_yet(db, mission, presence.not_yet_at)
    db.commit()
    return PresenceResult(mission, presence, changed=first_answer, events=["not_yet"] if first_answer else [])


def report_wrong_person(db: Session, mission_id: int, client_account_id: int) -> PresenceResult:
    """« Ce n'est pas lui » : litige ouvert dans la même transaction, fonds
    gelés jusqu'à la décision de l'admin."""
    mission = ledger.lock_mission(db, mission_id)
    ledger.require_mission_client(mission, client_account_id)
    presence = _presence(db, mission_id)
    if presence is not None and presence.wrong_person_reported_at is not None:
        return PresenceResult(mission, presence)
    presence = presence or _presence(db, mission_id, create=True)
    presence.wrong_person_reported_at = _utcnow()
    # Prestataire et équipe prévenus dans la transaction du litige (écrits
    # avant : `open_dispute` valide). Mêmes règles qu'un litige ordinaire
    # (payée, pas réglée, état permis) ; un refus annule tout.
    evenements.presence_wrong_person(db, mission)
    mission = ledger.open_dispute(db, mission_id, client_account_id, WRONG_PERSON_REASON, notify_provider=False)
    db.commit()
    return PresenceResult(mission, db.get(MissionPresence, mission_id), changed=True, events=["wrong_person"])


def presence_state(db: Session, mission: BotMission, role: str) -> dict:
    """État de la présence vu par `role` (client, provider, admin). Le code
    n'est donné qu'au client, tant que la mission payée attend l'arrivée."""
    presence = _presence(db, mission.mission_id)
    confirmed = presence is not None and presence.confirmed_at is not None
    state = {
        "arrival_declared": presence is not None and presence.arrival_declared_at is not None,
        "confirmed": confirmed,
        "confirmed_by": presence.confirmed_by if presence is not None else None,
        "code_locked": presence is not None and presence.code_locked_at is not None,
        "code_attempts_left": MAX_CODE_ATTEMPTS - (presence.failed_code_attempts if presence is not None else 0),
        "wrong_person_reported": presence is not None and presence.wrong_person_reported_at is not None,
    }
    if role == "client":
        waiting = not confirmed and mission.status == "confirmed" and ledger.mission_operation(db, mission.mission_id, ledger.FUNDING) is not None
        state["code"] = presence_code(mission.mission_id) if waiting else None
    return state


def viewer_role(db: Session, mission: BotMission, account_id: int | None, is_admin: bool) -> str | None:
    if is_admin:
        return "admin"
    if account_id is None:
        return None
    if mission.client_account_id == account_id:
        return "client"
    if mission.provider_account_id == account_id:
        return "provider"
    return None
