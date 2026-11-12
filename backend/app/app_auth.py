"""Codes de connexion de l'application mobile (étape 1, PR 2).

Plan : app-mobile/plan-etape1-connexion-api-2026-11-07.md, sections 5.1 à 5.4.

Ce module est la seule source des règles de connexion par code :

- **où part le code** : décidé ici à partir du numéro, jamais par l'app ;
- **numéro prouvé** : seul un numéro prouvé (contact Telegram de
  l'expéditeur, plus tard numéro WhatsApp) remplit `accounts.phone_e164` ;
  un numéro déjà prouvé sur un autre compte n'est jamais déplacé ;
- **code** : 6 chiffres tirés par `secrets`, haché avec une clé serveur
  (HMAC-SHA256, lié à la demande), valable 10 minutes, usage unique,
  5 essais au plus, et seulement pour la clé d'appareil qui l'a demandé ;
- **limites** : par numéro, par appareil et par adresse réseau, lues dans
  `login_challenges` (la base, une seule source), sous verrou par numéro
  sur Postgres pour que deux demandes simultanées ne dépassent pas la limite.

En cas de doute (clé de hachage absente, canal d'envoi pas encore branché),
on refuse : aucune demande n'est créée.

Aucune route publique n'appelle encore ce module : l'API de l'app arrive avec
la PR 5. Le bot Telegram l'appelle par `/api/bot/app-login/telegram-contact`.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from backend.app import ledger
from backend.app.models import (
    MAX_CODE_ATTEMPTS,
    AuthEvent,
    ChannelIdentity,
    LoginChallenge,
    NexisAccount,
)

CODE_TTL = timedelta(minutes=10)
CODE_DIGITS = 6
TELEGRAM_START_PREFIX = "app_"

# Limites de demandes de code (section 5.4 du plan).
PHONE_PER_HOUR = 3
PHONE_PER_DAY = 10
DEVICE_PER_HOUR = 5
IP_PER_HOUR = 20

# Canaux d'envoi branchés. WhatsApp attend le service d'envoi WhatsApp et le
# compte Meta Business vérifié (PR 6) : d'ici là, il est refusé.
AVAILABLE_DELIVERIES = ("telegram",)

_E164 = re.compile(r"^\+[1-9]\d{7,14}$")
_START_TOKEN = re.compile(r"^[A-Za-z0-9_-]{32}$")


class AuthError(Exception):
    """Refus d'une étape de connexion. `code` est stable et traduit par les
    canaux ; `http_status` sert aux routes."""

    def __init__(self, code: str, http_status: int = 400):
        super().__init__(code)
        self.code = code
        self.http_status = http_status


@dataclass(frozen=True)
class ChallengeCreated:
    public_id: str
    delivery: str
    expires_at: datetime
    # Lien de démarrage du bot, seulement pour une demande par Telegram. Le
    # jeton en clair n'est rendu qu'ici : la base n'en garde que l'empreinte.
    telegram_start_token: str | None


@dataclass(frozen=True)
class IssuedCode:
    code: str
    expires_at: datetime


@dataclass(frozen=True)
class VerifiedChallenge:
    """Code juste : le compte à qui ouvrir une session (PR 3), et si ce compte
    existait déjà (délai de 72 h sur l'argent sortant pour un appareil ajouté
    à un compte existant)."""

    account_id: int
    existing_account: bool


def _utcnow() -> datetime:
    return datetime.utcnow()


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _code_key() -> bytes:
    key = os.getenv("APP_CODE_HMAC_KEY", "")
    if len(key) < 32:
        # Sans clé solide, on ne crée ni ne vérifie aucun code.
        raise AuthError("auth_not_configured", 503)
    return key.encode()


def _code_hash(public_id: str, code: str) -> str:
    return hmac.new(_code_key(), f"{public_id}:{code}".encode(), hashlib.sha256).hexdigest()


def normalize_phone(raw: str | None) -> str:
    """Numéro au format E.164 (`+243812345678`). Telegram envoie parfois le
    numéro sans `+` : il est ajouté. Tout autre format est refusé."""
    if not raw:
        raise AuthError("invalid_phone")
    phone = re.sub(r"[\s\-().]", "", raw)
    if phone.startswith("00"):
        phone = "+" + phone[2:]
    elif not phone.startswith("+"):
        phone = "+" + phone
    if not _E164.match(phone):
        raise AuthError("invalid_phone")
    return phone


def _event(db: Session, type_: str, result: str, *, account_id=None, ip_hash=None, now=None) -> None:
    db.add(AuthEvent(account_id=account_id, type=type_, result=result, ip_hash=ip_hash, created_at=now or _utcnow()))


def record_event(db: Session, type_: str, result: str, *, account_id=None) -> None:
    """Ajoute une ligne au journal d'audit (sans numéro, code ni jeton). Ne
    valide pas la transaction."""
    _event(db, type_, result, account_id=account_id)


def _lock_phone(db: Session, phone: str) -> None:
    """Verrou de transaction par numéro (Postgres) : les comptages de limite
    et la création de la demande se font sans qu'une demande simultanée pour
    le même numéro s'intercale. SQLite n'a qu'un écrivain à la fois."""
    if db.get_bind().dialect.name == "postgresql":
        key = int.from_bytes(hashlib.sha256(f"app-login:{phone}".encode()).digest()[:8], "big", signed=True)
        db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})


def _count_since(db: Session, column, value, since: datetime) -> int:
    return (
        db.query(func.count(LoginChallenge.id))
        .filter(column == value, LoginChallenge.created_at >= since)
        .scalar()
    )


def account_with_proven_phone(db: Session, phone: str) -> NexisAccount | None:
    return (
        db.query(NexisAccount)
        .filter(NexisAccount.phone_e164 == phone, NexisAccount.phone_verified_at.isnot(None))
        .one_or_none()
    )


def prove_phone(db: Session, account_id: int, phone: str, *, now: datetime | None = None) -> bool:
    """Enregistre sur le compte un numéro que le canal a prouvé. Ne valide pas
    la transaction (l'appelant le fait).

    Refus sans rien changer (False) si ce numéro est déjà le numéro prouvé
    d'un autre compte : un numéro ne déplace jamais un compte, ni son argent
    (numéros réattribués, docs/ARCHITECTURE_WHATSAPP.md). L'événement est
    journalisé pour l'admin."""
    now = now or _utcnow()
    phone = normalize_phone(phone)
    holder = account_with_proven_phone(db, phone)
    if holder is not None and holder.id != account_id:
        _event(db, "phone_conflict", "refused", account_id=account_id, now=now)
        return False
    account = db.get(NexisAccount, account_id, with_for_update=True)
    if account is None:
        raise AuthError("account_not_found", 404)
    if account.phone_e164 == phone and account.phone_verified_at is not None:
        return True
    changed = account.phone_verified_at is not None
    account.phone_e164 = phone
    account.phone_verified_at = now
    _event(db, "phone_changed" if changed else "phone_proven", "accepted", account_id=account_id, now=now)
    return True


def create_challenge(
    db: Session,
    *,
    phone: str,
    delivery: str,
    device_key_thumbprint: str,
    ip_hash: str | None = None,
    now: datetime | None = None,
) -> ChallengeCreated:
    """Nouvelle demande de code. La réponse ne dit jamais si le numéro est
    connu : pour un compte existant, le code ne partira que si le canal
    choisi est relié à ce compte (vérifié à l'envoi)."""
    now = now or _utcnow()
    _code_key()  # refus immédiat si la clé manque
    if delivery not in ("whatsapp", "telegram"):
        raise AuthError("invalid_delivery")
    if delivery not in AVAILABLE_DELIVERIES:
        raise AuthError("delivery_unavailable", 503)
    if not re.fullmatch(r"[0-9a-f]{64}", device_key_thumbprint or ""):
        raise AuthError("invalid_device_key")
    phone = normalize_phone(phone)

    _lock_phone(db, phone)
    hour_ago, day_ago = now - timedelta(hours=1), now - timedelta(days=1)
    limited = (
        _count_since(db, LoginChallenge.phone_e164, phone, hour_ago) >= PHONE_PER_HOUR
        or _count_since(db, LoginChallenge.phone_e164, phone, day_ago) >= PHONE_PER_DAY
        or _count_since(db, LoginChallenge.device_key_thumbprint, device_key_thumbprint, hour_ago) >= DEVICE_PER_HOUR
        or (ip_hash is not None and _count_since(db, LoginChallenge.ip_hash, ip_hash, hour_ago) >= IP_PER_HOUR)
    )
    if limited:
        _event(db, "challenge_requested", "rate_limited", ip_hash=ip_hash, now=now)
        db.commit()
        raise AuthError("rate_limited", 429)

    holder = account_with_proven_phone(db, phone)
    start_token = secrets.token_urlsafe(24) if delivery == "telegram" else None
    challenge = LoginChallenge(
        public_id=secrets.token_hex(16),
        phone_e164=phone,
        purpose="login" if holder is not None else "signup",
        delivery=delivery,
        account_id=holder.id if holder is not None else None,
        device_key_thumbprint=device_key_thumbprint,
        telegram_start_hash=_sha256(start_token) if start_token else None,
        attempts=0,
        ip_hash=ip_hash,
        created_at=now,
        expires_at=now + CODE_TTL,
    )
    db.add(challenge)
    _event(db, "challenge_requested", "accepted", account_id=challenge.account_id, ip_hash=ip_hash, now=now)
    db.commit()
    return ChallengeCreated(challenge.public_id, delivery, challenge.expires_at, start_token)


def issue_code_for_telegram_contact(
    db: Session,
    *,
    start_token: str,
    telegram_id: int,
    contact_phone: str,
    now: datetime | None = None,
) -> IssuedCode:
    """La personne a ouvert le bot par le lien de l'app et partagé son propre
    contact (le bot l'a vérifié : contact de l'expéditeur). Le backend prouve
    le numéro, rattache la demande au compte de ce Telegram, et rend le code
    que le bot affiche. Un seul code par demande."""
    now = now or _utcnow()
    _code_key()
    if not _START_TOKEN.fullmatch(start_token or ""):
        raise AuthError("link_invalid")
    challenge = (
        db.query(LoginChallenge)
        .filter(LoginChallenge.telegram_start_hash == _sha256(start_token))
        .with_for_update()
        .one_or_none()
    )
    if (
        challenge is None
        or challenge.delivery != "telegram"
        or challenge.code_hash is not None
        or challenge.consumed_at is not None
        or challenge.expires_at <= now
    ):
        raise AuthError("link_invalid")

    phone = normalize_phone(contact_phone)
    if phone != challenge.phone_e164:
        _event(db, "telegram_contact", "phone_mismatch", account_id=challenge.account_id, now=now)
        db.commit()
        raise AuthError("phone_mismatch")

    telegram_account_id = ledger.account_id_for(db, ledger.TELEGRAM, telegram_id)
    holder = account_with_proven_phone(db, phone)
    if holder is not None:
        # Numéro déjà prouvé sur un compte : le code ne va qu'au Telegram de
        # ce compte-là, jamais à un autre (numéro réattribué, conflit).
        if telegram_account_id != holder.id:
            _event(db, "telegram_contact", "phone_conflict", account_id=telegram_account_id, now=now)
            db.commit()
            raise AuthError("phone_conflict", 409)
        account_id, existing = holder.id, True
    elif telegram_account_id is not None:
        if not prove_phone(db, telegram_account_id, phone, now=now):  # pragma: no cover - holder vérifié juste au-dessus
            db.commit()
            raise AuthError("phone_conflict", 409)
        account_id, existing = telegram_account_id, True
    else:
        account_id = ledger.account_id_for(db, ledger.TELEGRAM, telegram_id, create=True)
        if not prove_phone(db, account_id, phone, now=now):  # pragma: no cover
            db.commit()
            raise AuthError("phone_conflict", 409)
        existing = False

    code = f"{secrets.randbelow(10 ** CODE_DIGITS):0{CODE_DIGITS}d}"
    challenge.account_id = account_id
    challenge.purpose = "login" if existing else "signup"
    challenge.code_hash = _code_hash(challenge.public_id, code)
    challenge.expires_at = min(challenge.expires_at, now + CODE_TTL)
    _event(db, "code_issued", "accepted", account_id=account_id, now=now)
    db.commit()
    return IssuedCode(code, challenge.expires_at)


def verify_code(
    db: Session,
    *,
    public_id: str,
    code: str,
    device_key_thumbprint: str,
    now: datetime | None = None,
    commit: bool = True,
) -> VerifiedChallenge:
    """Vérifie un code. Chaque échec compte un essai, enregistré même quand
    la demande est refusée. Un code juste consomme la demande : il ne sert
    qu'une fois. Les refus ne disent pas pourquoi le code est faux (demande
    inconnue, autre appareil, mauvais chiffres : même réponse).

    `commit=False` : un code juste n'est pas encore validé en base, pour que
    l'appelant consomme le code et ouvre la session dans la même transaction
    (`app_sessions.sign_in`) : jamais de code consommé sans session, ni
    l'inverse. Les échecs, eux, sont toujours enregistrés."""
    now = now or _utcnow()
    _code_key()  # clé requise avant tout
    challenge = (
        db.query(LoginChallenge)
        .filter(LoginChallenge.public_id == (public_id or ""))
        .with_for_update()
        .one_or_none()
    )
    if challenge is None or challenge.consumed_at is not None:
        raise AuthError("invalid_code")
    if challenge.attempts >= MAX_CODE_ATTEMPTS:
        raise AuthError("too_many_attempts", 429)
    if challenge.expires_at <= now:
        raise AuthError("code_expired")

    good = (
        challenge.code_hash is not None
        and re.fullmatch(rf"\d{{{CODE_DIGITS}}}", code or "") is not None
        and hmac.compare_digest(challenge.device_key_thumbprint, device_key_thumbprint or "")
        and hmac.compare_digest(challenge.code_hash, _code_hash(challenge.public_id, code))
    )
    if not good:
        challenge.attempts += 1
        _event(db, "code_verified", "refused", account_id=challenge.account_id, now=now)
        db.commit()
        if challenge.attempts >= MAX_CODE_ATTEMPTS:
            raise AuthError("too_many_attempts", 429)
        raise AuthError("invalid_code")

    if challenge.account_id is None:  # pragma: no cover - un code n'est émis qu'avec un compte
        raise AuthError("invalid_code")
    challenge.consumed_at = now
    _event(db, "code_verified", "accepted", account_id=challenge.account_id, now=now)
    if commit:
        db.commit()
    return VerifiedChallenge(challenge.account_id, existing_account=challenge.purpose == "login")


def telegram_start_payload(token: str) -> str:
    """Paramètre `start` du lien `t.me/<bot>?start=...` (64 caractères au plus,
    lettres, chiffres, `_` et `-`)."""
    return f"{TELEGRAM_START_PREFIX}{token}"


def has_identity(db: Session, account_id: int, channel: str) -> bool:
    return (
        db.query(ChannelIdentity.id)
        .filter(ChannelIdentity.account_id == account_id, ChannelIdentity.channel == channel)
        .first()
        is not None
    )
