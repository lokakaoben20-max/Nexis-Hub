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

PR 4 (section 5.7) :

- **Demandes signées** (`verify_signed_request`) : la clé de l'appareil signe
  méthode, chemin, empreinte du corps, horodatage, nonce et empreinte du
  jeton de session. Refus : signature fausse, horodatage à plus de 5 minutes,
  nonce déjà vu (la base le refuse, même sous demandes simultanées).
- **Argent sortant** (`verify_money_request`) : en plus, l'appareil doit être
  vérifié par Google ou Apple (`attestation == "verified"`) et son délai de
  72 heures écoulé. En cas de doute, on refuse.
- **« Ce n'est pas moi »** (`report_not_me`) : la personne coupe, depuis un
  autre canal de son compte, un téléphone qu'elle ne reconnaît pas.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app import app_auth, ledger
from backend.app.app_auth import AuthError
from backend.app.models import DEVICE_PLATFORMS, AppSession, AuthEvent, ChannelIdentity, Device, RequestNonce

ACCESS_TTL = timedelta(minutes=15)
REFRESH_TTL = timedelta(days=30)
NEW_DEVICE_MONEY_DELAY = timedelta(hours=72)
MAX_LABEL = 100
MAX_APP_VERSION = 20

# Préfixes des messages signés par l'appareil : une signature faite pour une
# étape ne peut pas servir à une autre.
LOGIN_CONTEXT = "nexis-app-login-v1"
REFRESH_CONTEXT = "nexis-app-refresh-v1"
REQUEST_CONTEXT = "nexis-app-request-v1"

# Demandes signées : écart d'horloge toléré, et durée pendant laquelle un
# nonce est gardé. Elle dépasse largement l'écart toléré : une demande assez
# vieille pour que son nonce soit effacé est déjà refusée par son horodatage.
REQUEST_MAX_SKEW = timedelta(minutes=5)
NONCE_RETENTION = timedelta(hours=24)
_NONCE = re.compile(r"[A-Za-z0-9_-]{22,64}")
_TIMESTAMP = re.compile(r"[0-9]{1,12}")
_EPOCH = datetime(1970, 1, 1)


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
    # Téléphone créé par cette connexion (l'alerte « Nouvel appareil », s'il
    # en faut une, est déjà dans la boîte d'envoi : Device.alert_due_at).
    new_device: bool = False


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


def _tokens(session: AppSession, access: str, refresh: str, device: Device, new_device: bool = False) -> SessionTokens:
    return SessionTokens(
        access, session.access_expires_at, refresh, session.refresh_expires_at, device.id, device.account_id, new_device
    )


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
    new_device = device is None
    if new_device:
        device = Device(
            account_id=verified.account_id,
            platform=platform,
            public_key=public_key,
            key_thumbprint=thumbprint,
            # Vérification d'intégrité Google / Apple : elle arrive avec l'app
            # (attestations réelles de vrais téléphones). D'ici là, aucun
            # appareil n'est « verified » : aucune action d'argent sortante.
            attestation="unverified",
            label=(label or "")[:MAX_LABEL] or None,
            app_version=app_version,
            created_at=now,
            money_unlocked_at=now if not verified.existing_account else now + NEW_DEVICE_MONEY_DELAY,
            # Téléphone ajouté à un compte existant : l'alerte part avec la
            # transaction (tasks.send_pending_device_alerts), jamais perdue.
            alert_due_at=now if verified.existing_account else None,
        )
        db.add(device)
        db.flush()
        _event(db, "device_added", "accepted", account_id=device.account_id, device_id=device.id, now=now)
    device.app_version = app_version
    device.last_seen_at = now
    session, access, refresh = _new_session(db, device, secrets.token_hex(16), now)
    _event(db, "signed_in", "accepted", account_id=device.account_id, device_id=device.id, now=now)
    db.commit()
    return _tokens(session, access, refresh, device, new_device)


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


# --- Demandes signées et argent sortant (PR 4, section 5.7) ----------------------


def request_message(*, method: str, path: str, body: bytes, timestamp: str, nonce: str, access_token: str) -> str:
    """Ce que l'appareil signe pour une demande. Le corps et le jeton n'y
    figurent que par leur empreinte."""
    return "\n".join(
        [
            REQUEST_CONTEXT,
            method.upper(),
            path,
            hashlib.sha256(body).hexdigest(),
            timestamp,
            nonce,
            _sha256(access_token),
        ]
    )


def verify_signed_request(
    db: Session,
    *,
    access_token: str | None,
    method: str,
    path: str,
    body: bytes,
    timestamp: str | None,
    nonce: str | None,
    signature: str | None,
    now: datetime | None = None,
) -> AppPrincipal:
    """Vérifie une demande signée par la clé de l'appareil de la session.

    Le nonce est enregistré (et validé en base) avant que l'action ne
    commence : une demande ne passe qu'une fois, même si l'action échoue
    ensuite. L'app en crée un nouveau à chaque essai. L'action garde sa propre
    clé d'idempotence : la signature prouve qui demande, la clé empêche de le
    faire deux fois."""
    now = now or _utcnow()
    principal = authenticate(db, access_token, now=now)
    if not _TIMESTAMP.fullmatch(timestamp or ""):
        raise AuthError("invalid_timestamp")
    if not _NONCE.fullmatch(nonce or ""):
        raise AuthError("invalid_nonce")
    device = db.get(Device, principal.device_id)
    key, _ = load_public_key(device.public_key)
    message = request_message(
        method=method, path=path, body=body, timestamp=timestamp, nonce=nonce, access_token=access_token
    )
    if not signature_is_valid(key, message, signature):
        _event(db, "signed_request", "bad_signature", account_id=device.account_id, device_id=device.id, now=now)
        db.commit()
        raise AuthError("invalid_signature", 401)
    sent_at = _EPOCH + timedelta(seconds=int(timestamp))
    if abs(now - sent_at) > REQUEST_MAX_SKEW:
        raise AuthError("stale_request", 401)
    db.add(RequestNonce(device_id=device.id, nonce=nonce, seen_at=now))
    device.last_seen_at = now
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        _event(db, "signed_request", "replayed", account_id=principal.account_id, device_id=principal.device_id, now=now)
        db.commit()
        raise AuthError("replayed_request", 409)
    return principal


def money_allowed(device: Device, now: datetime) -> str | None:
    """Pourquoi ce téléphone ne peut pas faire sortir d'argent, ou None.
    Même règle pour l'API et pour l'écran de l'app qui l'explique."""
    if device.revoked_at is not None:
        return "unauthorized"
    if device.attestation != "verified":
        return "device_not_attested"
    if now < device.money_unlocked_at:
        return "new_device_locked"
    return None


def verify_money_request(db: Session, *, now: datetime | None = None, **request) -> AppPrincipal:
    """Demande signée d'une action d'argent sortante (retrait, changement du
    numéro de retrait, paiement par portefeuille) : en plus de la signature,
    le téléphone doit être vérifié par Google ou Apple et son délai de
    72 heures écoulé."""
    now = now or _utcnow()
    principal = verify_signed_request(db, now=now, **request)
    device = db.get(Device, principal.device_id)
    refusal = money_allowed(device, now)
    if refusal is not None:
        _event(db, "money_request", refusal, account_id=principal.account_id, device_id=principal.device_id, now=now)
        db.commit()
        raise AuthError(refusal, 401 if refusal == "unauthorized" else 403)
    return principal


def purge_request_nonces(db: Session, *, now: datetime | None = None) -> int:
    """Efface les nonces de plus de 24 heures (tâche planifiée)."""
    now = now or _utcnow()
    deleted = db.query(RequestNonce).filter(RequestNonce.seen_at < now - NONCE_RETENTION).delete(synchronize_session=False)
    db.commit()
    return deleted


# --- « Ce n'est pas moi » (PR 4, section 5.5) -------------------------------------


def needs_new_device_alert(device: Device) -> bool:
    """Un téléphone ajouté à un compte qui existait déjà : les autres canaux
    du compte sont prévenus. Le premier téléphone d'un compte tout neuf, non."""
    return device.revoked_at is None and device.money_unlocked_at > device.created_at


def report_not_me(db: Session, *, account_id: int, device_id: int, now: datetime | None = None) -> tuple[Device, bool]:
    """La personne ne reconnaît pas ce téléphone : il est coupé tout de suite,
    avec toutes ses sessions. Rend `(appareil, coupé_maintenant)` ; un second
    appui ne change rien. Un téléphone d'un autre compte « n'existe pas »."""
    now = now or _utcnow()
    device = db.query(Device).filter(Device.id == device_id).with_for_update().one_or_none()
    if device is None or device.account_id != account_id:
        raise AuthError("device_not_found", 404)
    if device.revoked_at is not None:
        db.rollback()
        return device, False
    _revoke_device(db, device, "not_me", now)
    _event(db, "device_revoked", "not_me", account_id=account_id, device_id=device.id, now=now)
    db.commit()
    return device, True
