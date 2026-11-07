"""Téléphones et sessions de l'application mobile (étape 1, PR 3).

Plan : app-mobile/plan-etape1-connexion-api-2026-11-07.md, sections 5.5 et 5.6.

- **Clé d'appareil** : P-256, créée dans le coffre matériel du téléphone. Le
  backend n'en connaît que la clé publique. Chaque étape sensible (connexion,
  renouvellement) est signée par cette clé : un jeton ou un code volés seuls
  ne suffisent pas.
- **Connexion** (`sign_in`) : code juste + signature juste, dans une seule
  transaction : le code est consommé, l'appareil et la session naissent
  ensemble, ou rien ne change.
- **Délai de 72 heures** : un appareil ajouté à un compte qui existait déjà
  ne fera aucune action d'argent sortante avant 72 h (`money_unlocked_at`,
  appliqué par la PR 4). Seul le premier appareil d'un compte tout neuf, sans
  argent ni historique, n'a pas ce délai.
- **Jetons opaques**, aléatoires, stockés hachés et vérifiés en base à chaque
  demande : une coupure prend effet tout de suite.
- **Rotation** : chaque renouvellement remplace la session. Un ancien jeton
  de renouvellement présenté à nouveau coupe toute la famille de sessions
  (signe d'un vol ou d'une erreur de l'app) : il faudra se reconnecter par
  code.
- **Appareil coupé** : définitivement, avec toutes ses sessions. Sa clé ne
  pourra plus jamais servir.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from sqlalchemy.orm import Session

from backend.app import app_auth, ledger
from backend.app.app_auth import AuthError
from backend.app.models import DEVICE_PLATFORMS, AppSession, AuthEvent, ChannelIdentity, Device

ACCESS_TTL = timedelta(minutes=15)
REFRESH_TTL = timedelta(days=30)
NEW_DEVICE_MONEY_DELAY = timedelta(hours=72)
MAX_LABEL = 100
MAX_APP_VERSION = 20

# Préfixes des messages signés par l'appareil : une signature faite pour une
# étape ne peut pas servir à une autre.
LOGIN_CONTEXT = "nexis-app-login-v1"
REFRESH_CONTEXT = "nexis-app-refresh-v1"


@dataclass(frozen=True)
class SessionTokens:
    """Jetons rendus à l'app, une seule fois : la base n'en garde que
    l'empreinte."""

    access_token: str
    access_expires_at: datetime
    refresh_token: str
    refresh_expires_at: datetime
    device_id: int
    account_id: int


@dataclass(frozen=True)
class AppPrincipal:
    """La personne derrière une demande de l'app, d'après sa session."""

    account_id: int
    device_id: int
    session_id: int
    # Identité `app` du compte : c'est elle que l'API publique donne comme
    # acteur aux règles métier (canal `app`, jamais déclaré par l'app).
    identity_id: str


def _utcnow() -> datetime:
    return datetime.utcnow()


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _b64decode(value: str | None) -> bytes:
    try:
        return base64.b64decode((value or "").encode(), validate=True)
    except (binascii.Error, ValueError):
        raise AuthError("invalid_device_key")


def load_public_key(public_key_b64: str | None) -> tuple[ec.EllipticCurvePublicKey, str]:
    """Clé publique d'appareil (SubjectPublicKeyInfo DER, en base64) et son
    empreinte SHA-256. Seule une clé P-256 est acceptée."""
    der = _b64decode(public_key_b64)
    try:
        key = serialization.load_der_public_key(der)
    except (ValueError, TypeError):
        raise AuthError("invalid_device_key")
    if not isinstance(key, ec.EllipticCurvePublicKey) or not isinstance(key.curve, ec.SECP256R1):
        raise AuthError("invalid_device_key")
    canonical = key.public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    if canonical != der:
        raise AuthError("invalid_device_key")
    return key, hashlib.sha256(der).hexdigest()


def signature_is_valid(key: ec.EllipticCurvePublicKey, message: str, signature_b64: str | None) -> bool:
    """Signature ECDSA P-256 / SHA-256 (format DER, en base64) de `message`."""
    try:
        signature = base64.b64decode((signature_b64 or "").encode(), validate=True)
        key.verify(signature, message.encode(), ec.ECDSA(hashes.SHA256()))
        return True
    except (InvalidSignature, binascii.Error, ValueError):
        return False


def login_message(challenge_public_id: str) -> str:
    return f"{LOGIN_CONTEXT}\n{challenge_public_id}"


def refresh_message(refresh_token: str) -> str:
    # On signe l'empreinte du jeton : la signature ne révèle pas le jeton.
    return f"{REFRESH_CONTEXT}\n{_sha256(refresh_token)}"


def _event(db: Session, type_: str, result: str, *, account_id=None, device_id=None, now=None) -> None:
    db.add(AuthEvent(account_id=account_id, device_id=device_id, type=type_, result=result, created_at=now or _utcnow()))


def _ensure_app_identity(db: Session, account_id: int, now: datetime) -> str:
    """Identité `app` du compte (une seule par compte, contrainte de base),
    créée à la première connexion depuis l'app."""
    identity = (
        db.query(ChannelIdentity)
        .filter(ChannelIdentity.account_id == account_id, ChannelIdentity.channel == ledger.APP)
        .one_or_none()
    )
    if identity is None:
        identity = ChannelIdentity(
            account_id=account_id, channel=ledger.APP, external_id=secrets.token_hex(16), verified_at=now
        )
        db.add(identity)
        db.flush()
    return identity.external_id


def _new_session(db: Session, device: Device, family_id: str, now: datetime) -> tuple[AppSession, str, str]:
    access, refresh = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    session = AppSession(
        device_id=device.id,
        family_id=family_id,
        access_hash=_sha256(access),
        access_expires_at=now + ACCESS_TTL,
        refresh_hash=_sha256(refresh),
        refresh_expires_at=now + REFRESH_TTL,
        created_at=now,
    )
    db.add(session)
    db.flush()
    return session, access, refresh


def _tokens(session: AppSession, access: str, refresh: str, device: Device) -> SessionTokens:
    return SessionTokens(access, session.access_expires_at, refresh, session.refresh_expires_at, device.id, device.account_id)


def sign_in(
    db: Session,
    *,
    challenge_public_id: str,
    code: str,
    public_key: str,
    signature: str,
    platform: str,
    app_version: str,
    label: str | None = None,
    now: datetime | None = None,
) -> SessionTokens:
    """Connexion par code. La signature prouve que la demande vient du
    téléphone qui détient la clé (celle à laquelle le code est lié)."""
    now = now or _utcnow()
    if platform not in DEVICE_PLATFORMS:
        raise AuthError("invalid_platform")
    if not app_version or len(app_version) > MAX_APP_VERSION:
        raise AuthError("invalid_app_version")
    key, thumbprint = load_public_key(public_key)
    if not signature_is_valid(key, login_message(challenge_public_id or ""), signature):
        raise AuthError("invalid_signature", 401)

    device = db.query(Device).filter(Device.key_thumbprint == thumbprint).with_for_update().one_or_none()
    if device is not None and device.revoked_at is not None:
        # Une clé coupée ne revit jamais : l'app doit en créer une nouvelle.
        raise AuthError("device_revoked", 401)

    verified = app_auth.verify_code(
        db, public_id=challenge_public_id, code=code, device_key_thumbprint=thumbprint, now=now, commit=False
    )
    if device is not None and device.account_id != verified.account_id:
        db.rollback()
        raise AuthError("device_key_in_use", 409)

    _ensure_app_identity(db, verified.account_id, now)
    if device is None:
        device = Device(
            account_id=verified.account_id,
            platform=platform,
            public_key=public_key,
            key_thumbprint=thumbprint,
            # Vérification d'intégrité Google / Apple : PR 4. D'ici là, aucun
            # appareil n'est « verified » : aucune action d'argent sortante.
            attestation="unverified",
            label=(label or "")[:MAX_LABEL] or None,
            app_version=app_version,
            created_at=now,
            money_unlocked_at=now if not verified.existing_account else now + NEW_DEVICE_MONEY_DELAY,
        )
        db.add(device)
        db.flush()
        _event(db, "device_added", "accepted", account_id=device.account_id, device_id=device.id, now=now)
    device.app_version = app_version
    device.last_seen_at = now
    session, access, refresh = _new_session(db, device, secrets.token_hex(16), now)
    _event(db, "signed_in", "accepted", account_id=device.account_id, device_id=device.id, now=now)
    db.commit()
    return _tokens(session, access, refresh, device)


def authenticate(db: Session, access_token: str | None, *, now: datetime | None = None) -> AppPrincipal:
    """Session d'une demande de l'app. Même refus pour un jeton inconnu,
    expiré, ou d'une session ou d'un appareil coupés."""
    now = now or _utcnow()
    if not access_token:
        raise AuthError("unauthorized", 401)
    row = (
        db.query(AppSession, Device)
        .join(Device, Device.id == AppSession.device_id)
        .filter(AppSession.access_hash == _sha256(access_token))
        .one_or_none()
    )
    if row is None:
        raise AuthError("unauthorized", 401)
    session, device = row
    if session.revoked_at is not None or device.revoked_at is not None or session.access_expires_at <= now:
        raise AuthError("unauthorized", 401)
    identity = (
        db.query(ChannelIdentity)
        .filter(ChannelIdentity.account_id == device.account_id, ChannelIdentity.channel == ledger.APP)
        .one_or_none()
    )
    if identity is None:  # pragma: no cover - créée avec la première session
        raise AuthError("unauthorized", 401)
    return AppPrincipal(device.account_id, device.id, session.id, identity.external_id)


def _revoke_family(db: Session, family_id: str, reason: str, now: datetime) -> None:
    for session in db.query(AppSession).filter(AppSession.family_id == family_id, AppSession.revoked_at.is_(None)):
        session.revoked_at, session.revoked_reason = now, reason


def refresh(db: Session, *, refresh_token: str, signature: str, now: datetime | None = None) -> SessionTokens:
    """Renouvelle une session. La demande doit être signée par la clé de
    l'appareil de la session : un jeton de renouvellement volé seul ne sert à
    rien. Un ancien jeton (déjà remplacé) coupe toute la famille."""
    now = now or _utcnow()
    session = (
        db.query(AppSession)
        .filter(AppSession.refresh_hash == _sha256(refresh_token or ""))
        .with_for_update()
        .one_or_none()
    )
    if session is None:
        raise AuthError("unauthorized", 401)
    device = db.get(Device, session.device_id)
    if device.revoked_at is not None:
        raise AuthError("unauthorized", 401)
    key, _ = load_public_key(device.public_key)
    if not signature_is_valid(key, refresh_message(refresh_token), signature):
        _event(db, "session_refreshed", "bad_signature", account_id=device.account_id, device_id=device.id, now=now)
        db.commit()
        raise AuthError("invalid_signature", 401)
    if session.replaced_by_id is not None:
        _revoke_family(db, session.family_id, "token_reuse", now)
        _event(db, "session_refreshed", "token_reuse", account_id=device.account_id, device_id=device.id, now=now)
        db.commit()
        raise AuthError("unauthorized", 401)
    if session.revoked_at is not None or session.refresh_expires_at <= now:
        raise AuthError("unauthorized", 401)

    new_session, access, new_refresh = _new_session(db, device, session.family_id, now)
    session.replaced_by_id = new_session.id
    session.revoked_at, session.revoked_reason = now, "rotated"
    device.last_seen_at = now
    _event(db, "session_refreshed", "accepted", account_id=device.account_id, device_id=device.id, now=now)
    db.commit()
    return _tokens(new_session, access, new_refresh, device)


def sign_out(db: Session, principal: AppPrincipal, *, now: datetime | None = None) -> None:
    """Déconnexion de ce téléphone : sa session (et ses renouvellements)
    est coupée. L'appareil reste connu : une reconnexion par code repart
    de lui, sans nouveau délai de 72 h."""
    now = now or _utcnow()
    session = db.get(AppSession, principal.session_id)
    _revoke_family(db, session.family_id, "logout", now)
    _event(db, "signed_out", "accepted", account_id=principal.account_id, device_id=principal.device_id, now=now)
    db.commit()


def _revoke_device(db: Session, device: Device, reason: str, now: datetime) -> None:
    if device.revoked_at is None:
        device.revoked_at, device.revoked_reason = now, reason
    for session in db.query(AppSession).filter(AppSession.device_id == device.id, AppSession.revoked_at.is_(None)):
        session.revoked_at, session.revoked_reason = now, reason


def list_devices(db: Session, account_id: int) -> list[Device]:
    return db.query(Device).filter(Device.account_id == account_id).order_by(Device.created_at.desc(), Device.id.desc()).all()


def revoke_own_device(db: Session, principal: AppPrincipal, device_id: int, *, now: datetime | None = None) -> Device:
    """La personne coupe un de ses téléphones (perdu, volé, vendu). Un
    téléphone d'un autre compte « n'existe pas » pour elle."""
    now = now or _utcnow()
    device = db.query(Device).filter(Device.id == device_id).with_for_update().one_or_none()
    if device is None or device.account_id != principal.account_id:
        raise AuthError("device_not_found", 404)
    _revoke_device(db, device, "revoked_by_owner", now)
    _event(db, "device_revoked", "by_owner", account_id=device.account_id, device_id=device.id, now=now)
    db.commit()
    return device


def revoke_all_devices(db: Session, account_id: int, *, reason: str = "revoked_by_admin", now: datetime | None = None) -> int:
    """Coupe tous les téléphones d'un compte (décision de l'admin, ou plus
    tard « Ce n'est pas moi »). Renvoie le nombre de téléphones coupés."""
    now = now or _utcnow()
    devices = (
        db.query(Device)
        .filter(Device.account_id == account_id, Device.revoked_at.is_(None))
        .with_for_update()
        .all()
    )
    for device in devices:
        _revoke_device(db, device, reason, now)
        _event(db, "device_revoked", reason, account_id=account_id, device_id=device.id, now=now)
    db.commit()
    return len(devices)
