"""API publique de l'application mobile Nexis (étape 1, PR 5).

Plan : app-mobile/plan-etape1-connexion-api-2026-11-07.md, sections 5 et 6.

Lancement : `uvicorn backend.app.public:app`, sur un port distinct de l'API
du bot. Cette application n'a **aucune** route `/api/bot` ni `/api/admin` :
elle n'accepte ni la clé partagée du bot (`X-API-Key`) ni les en-têtes
`X-Actor-*`. Une personne est reconnue par sa session (jeton d'accès) et, pour
les actions qui touchent à l'argent ou aux téléphones, par la signature de la
clé de son téléphone (`app_sessions.verify_signed_request`).

Règles communes :
- `X-App-Version` obligatoire (sauf `/config`) ; version trop ancienne : 426.
- Erreurs au format du bot : `{"detail": {"code": ...}}`.
- Aucun identifiant Telegram, aucun identifiant interne de canal dans les
  réponses (`_public`), numéro masqué.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend.app import app_auth, app_sessions, crud, ledger
from backend.app.app_auth import AuthError
from backend.app.database import SessionLocal
from backend.app.models import BotMission, NexisAccount

logger = logging.getLogger(__name__)

PREFIX = "/api/app/v1"
MIN_VERSION_ENV = "NEXIS_APP_MIN_VERSION"
BOT_USERNAME_ENV = "NEXIS_BOT_USERNAME"
DEFAULT_MIN_VERSION = "1.0.0"
_VERSION = re.compile(r"[0-9]{1,4}(\.[0-9]{1,4}){0,2}")
_MISSION_FIELDS = (
    "mission_id",
    "service",
    "commune",
    "currency",
    "description",
    "urgent",
    "status",
    "payment_status",
    "commission_amount",
    "tola_fee",
    "aggregator_fee",
    "total_client",
    "net_provider",
    "dispute_reason",
)

app = FastAPI(title="Nexis Hub application mobile")


@app.exception_handler(AuthError)
async def _auth_error(request: Request, error: AuthError) -> JSONResponse:
    return JSONResponse(status_code=error.http_status, content={"detail": {"code": error.code}})


# --- Version de l'application -------------------------------------------------


def _version_key(value: str) -> tuple[int, int, int]:
    parts = [int(part) for part in value.split(".")]
    return tuple((parts + [0, 0, 0])[:3])  # type: ignore[return-value]


def require_current_app(x_app_version: str | None = Header(default=None)) -> str:
    """Refuse les versions absentes, mal écrites ou trop anciennes."""
    if not x_app_version or not _VERSION.fullmatch(x_app_version) or len(x_app_version) > app_sessions.MAX_APP_VERSION:
        raise HTTPException(status_code=400, detail={"code": "app_version_required"})
    minimum = os.getenv(MIN_VERSION_ENV, "").strip() or DEFAULT_MIN_VERSION
    if _version_key(x_app_version) < _version_key(minimum):
        raise HTTPException(status_code=426, detail={"code": "app_update_required"})
    return x_app_version


# --- Helpers ------------------------------------------------------------------


def _bearer(authorization: str | None) -> str | None:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    return authorization[len("Bearer "):].strip() or None


def _session(db, authorization: str | None) -> app_sessions.AppPrincipal:
    return app_sessions.authenticate(db, _bearer(authorization))


def _ip_hash(request: Request) -> str:
    host = request.client.host if request.client else ""
    return hashlib.sha256(host.encode()).hexdigest()


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _tokens_view(tokens: app_sessions.SessionTokens) -> dict[str, Any]:
    return {
        "access_token": tokens.access_token,
        "access_expires_at": _iso(tokens.access_expires_at),
        "refresh_token": tokens.refresh_token,
        "refresh_expires_at": _iso(tokens.refresh_expires_at),
        "device_id": tokens.device_id,
        "new_device": tokens.new_device,
    }


def _mask(phone: str | None) -> str | None:
    """`+243810000012` -> `+243•••••12`."""
    if not phone or len(phone) < 6:
        return None
    return f"{phone[:4]}•••••{phone[-2:]}"


def _is_internal(key: str) -> bool:
    lowered = key.lower()
    return "telegram" in lowered or "external_id" in lowered


def _public(value: Any) -> Any:
    """Retire de toute réponse les champs d'identité de canal."""
    if isinstance(value, dict):
        return {key: _public(item) for key, item in value.items() if not _is_internal(key)}
    if isinstance(value, list):
        return [_public(item) for item in value]
    return value


def _mission(mission: BotMission) -> dict[str, Any]:
    data = {field: getattr(mission, field) for field in _MISSION_FIELDS}
    data["dispute_deadline"] = _iso(mission.dispute_deadline)
    return data


def _schedule_new_device_alert(device_id: int) -> None:
    """Prévient la personne sur Telegram d'un nouveau téléphone. Un échec
    d'envoi ne fait pas échouer la connexion : la tâche réessaie, et le délai
    de 72 h protège l'argent de toute façon."""
    from backend.app.tasks import alert_new_app_device

    try:
        alert_new_app_device.delay(device_id)
    except Exception:  # pragma: no cover - broker indisponible
        logger.exception("Alerte « Nouvel appareil » non programmée (appareil %s)", device_id)


# --- Modèles ------------------------------------------------------------------


class ChallengePayload(BaseModel):
    phone: str = Field(max_length=32)
    channel: str = Field(default="telegram", max_length=12)
    public_key: str = Field(max_length=512)


class VerifyPayload(BaseModel):
    code: str = Field(max_length=12)
    public_key: str = Field(max_length=512)
    signature: str = Field(max_length=256)
    platform: str = Field(max_length=10)
    label: str | None = Field(default=None, max_length=100)


class RefreshPayload(BaseModel):
    refresh_token: str = Field(max_length=256)
    signature: str = Field(max_length=256)


# --- Routes sans session -------------------------------------------------------

open_router = APIRouter(prefix=PREFIX)
router = APIRouter(prefix=PREFIX, dependencies=[Depends(require_current_app)])


@open_router.get("/config")
def config() -> dict[str, Any]:
    """Sans version exigée : l'app affiche « mise à jour requise » grâce à ça."""
    return {
        "min_version": os.getenv(MIN_VERSION_ENV, "").strip() or DEFAULT_MIN_VERSION,
        "channels": list(app_auth.AVAILABLE_DELIVERIES),
    }


@router.post("/auth/challenges")
def create_challenge(payload: ChallengePayload, request: Request) -> dict[str, Any]:
    """Demande un code. La réponse est la même, que le numéro soit connu ou non."""
    if payload.channel not in ("telegram", "whatsapp"):
        raise AuthError("invalid_delivery")
    _, thumbprint = app_sessions.load_public_key(payload.public_key)
    bot = os.getenv(BOT_USERNAME_ENV, "").strip().lstrip("@")
    if payload.channel == "telegram" and not bot:
        raise HTTPException(status_code=503, detail={"code": "auth_not_configured"})
    with SessionLocal() as db:
        created = app_auth.create_challenge(
            db,
            phone=payload.phone,
            delivery=payload.channel,
            device_key_thumbprint=thumbprint,
            ip_hash=_ip_hash(request),
        )
    body: dict[str, Any] = {
        "public_id": created.public_id,
        "channel": created.delivery,
        "expires_at": _iso(created.expires_at),
    }
    if created.telegram_start_token:
        start = app_auth.telegram_start_payload(created.telegram_start_token)
        body["telegram_link"] = f"https://t.me/{bot}?start={start}"
    return body


@router.post("/auth/challenges/{public_id}/verify")
def verify_challenge(
    public_id: str, payload: VerifyPayload, app_version: str = Depends(require_current_app)
) -> dict[str, Any]:
    """Code juste + signature du téléphone : session et téléphone créés."""
    with SessionLocal() as db:
        tokens = app_sessions.sign_in(
            db,
            challenge_public_id=public_id,
            code=payload.code,
            public_key=payload.public_key,
            signature=payload.signature,
            platform=payload.platform,
            app_version=app_version,
            label=payload.label,
        )
    if tokens.new_device:
        _schedule_new_device_alert(tokens.device_id)
    return _tokens_view(tokens)


@router.post("/auth/refresh")
def refresh(payload: RefreshPayload) -> dict[str, Any]:
    with SessionLocal() as db:
        tokens = app_sessions.refresh(db, refresh_token=payload.refresh_token, signature=payload.signature)
    return _tokens_view(tokens)


# --- Routes avec session -------------------------------------------------------


@router.post("/auth/logout")
def logout(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    with SessionLocal() as db:
        app_sessions.sign_out(db, _session(db, authorization))
    return {"status": "ok"}


@router.get("/me")
def me(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    with SessionLocal() as db:
        principal = _session(db, authorization)
        account = db.get(NexisAccount, principal.account_id)
        verified = account is not None and account.phone_verified_at is not None
        return {
            "language": account.language if account is not None else "fr",
            "phone_masked": _mask(account.phone_e164) if verified else None,
        }


@router.get("/me/devices")
def my_devices(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    with SessionLocal() as db:
        principal = _session(db, authorization)
        devices = app_sessions.list_devices(db, principal.account_id)
        return {
            "devices": [
                {
                    "id": device.id,
                    "platform": device.platform,
                    "label": device.label,
                    "attestation": device.attestation,
                    "created_at": _iso(device.created_at),
                    "last_seen_at": _iso(device.last_seen_at),
                    "money_unlocked_at": _iso(device.money_unlocked_at),
                    "revoked_at": _iso(device.revoked_at),
                    "current": device.id == principal.device_id,
                }
                for device in devices
            ]
        }


@router.delete("/me/devices/{device_id}")
def revoke_device(
    device_id: int,
    request: Request,
    authorization: str | None = Header(default=None),
    x_request_timestamp: str | None = Header(default=None),
    x_request_nonce: str | None = Header(default=None),
    x_request_signature: str | None = Header(default=None),
) -> dict[str, Any]:
    """Couper un de ses téléphones : demande signée. Cette route n'a pas de
    corps : la signature porte donc l'empreinte du corps vide."""
    with SessionLocal() as db:
        principal = app_sessions.verify_signed_request(
            db,
            access_token=_bearer(authorization),
            method=request.method,
            path=request.url.path,
            body=b"",
            timestamp=x_request_timestamp,
            nonce=x_request_nonce,
            signature=x_request_signature,
        )
        app_sessions.revoke_own_device(db, principal, device_id)
    return {"status": "ok", "revoked": True}


@router.get("/me/wallet")
def my_wallet(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    """Mêmes chiffres que `/api/me/wallet` du bot, pour le compte de la session."""
    with SessionLocal() as db:
        principal = _session(db, authorization)
        balances = ledger.wallet_balances(db, principal.account_id)
    return {
        "wallet_balance_usd": float(balances["USD"]),
        "wallet_balance_cdf": float(balances["CDF"]),
    }


@router.get("/me/missions")
def my_missions(
    role: str = "client", limit: int = 20, authorization: str | None = Header(default=None)
) -> dict[str, Any]:
    if role not in ("client", "provider"):
        raise HTTPException(status_code=400, detail={"code": "invalid_role"})
    limit = max(1, min(limit, 50))
    with SessionLocal() as db:
        principal = _session(db, authorization)
        listing = crud.client_missions if role == "client" else crud.provider_missions
        missions = [_mission(mission) for mission in listing(db, principal.account_id, limit)]
    return {"missions": missions}


@router.get("/missions/{mission_id}")
def get_mission(mission_id: int, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    """Mêmes droits de lecture que le bot. Pour quelqu'un d'autre, la mission
    n'existe pas (même réponse qu'un numéro inconnu)."""
    with SessionLocal() as db:
        principal = _session(db, authorization)
        mission = db.get(BotMission, mission_id)
        role = crud.mission_viewer_role(db, mission, principal.account_id) if mission is not None else None
        if role is None:
            raise HTTPException(status_code=404, detail={"code": "mission_not_found"})
        view = {
            "mission": _mission(mission),
            "money": ledger.mission_money_state(db, mission_id),
            "viewer_role": role,
        }
    return _public(view)


app.include_router(open_router)
app.include_router(router)
