import os
import secrets
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Nexis Hub V5 Backend")

APP_STATE: dict[str, Any] = {"users": {}, "missions": {}, "providers": {}}



def require_internal_api_key(
    provided_key: str | None = Header(default=None, alias="X-Nexis-Internal-Key"),
) -> None:
    """Reject external requests to internal bot and profile APIs."""
    configured_key = os.getenv("BACKEND_API_KEY")
    if not configured_key:
        raise HTTPException(status_code=503, detail="Backend API key is not configured")
    if not provided_key or not secrets.compare_digest(provided_key, configured_key):
        raise HTTPException(status_code=401, detail="Invalid backend API key")


class BotUserPayload(BaseModel):
    telegram_id: int
    first_name: str | None = None
    phone_number: str | None = None
    language: str = "fr"


class BotMissionPayload(BaseModel):
    telegram_id: int
    mission_id: int
    service: str
    commune: str
    currency: str = "USD"
    description: str = ""
    urgent: bool = False


class BotProviderPayload(BaseModel):
    telegram_id: int
    full_name: str
    phone_number: str | None = None
    services: list[str] | None = None
    communes: list[str] | None = None
    language: str = "fr"


class MissionStatusPayload(BaseModel):
    mission_id: int
    status: str
    payment_status: str | None = None


class PaymentPayload(BaseModel):
    quote_id: int
    payment_status: str
    mission_id: int | None = None


@app.get("/health")
def health():
    return {"status": "ok", "service": "nexis-hub-v5"}


@app.post("/api/bot/users", dependencies=[Depends(require_internal_api_key)])
def create_bot_user(payload: BotUserPayload):
    APP_STATE["users"][payload.telegram_id] = {
        "telegram_id": payload.telegram_id,
        "first_name": payload.first_name or "Client",
        "phone_number": payload.phone_number,
        "language": payload.language,
    }
    return {"status": "ok", "user": APP_STATE["users"][payload.telegram_id]}


@app.post("/api/bot/missions", dependencies=[Depends(require_internal_api_key)])
def create_bot_mission(payload: BotMissionPayload):
    APP_STATE["missions"][payload.mission_id] = {
        "mission_id": payload.mission_id,
        "telegram_id": payload.telegram_id,
        "service": payload.service,
        "commune": payload.commune,
        "currency": payload.currency,
        "description": payload.description,
        "urgent": payload.urgent,
    }
    return {"status": "ok", "mission": APP_STATE["missions"][payload.mission_id]}


@app.post("/api/bot/providers", dependencies=[Depends(require_internal_api_key)])
def create_bot_provider(payload: BotProviderPayload):
    APP_STATE["providers"][payload.telegram_id] = {
        "telegram_id": payload.telegram_id,
        "full_name": payload.full_name,
        "phone_number": payload.phone_number,
        "services": payload.services or [],
        "communes": payload.communes or [],
        "language": payload.language,
        "status": "available",
    }
    return {"status": "ok", "provider": APP_STATE["providers"][payload.telegram_id]}


@app.post("/api/bot/missions/status", dependencies=[Depends(require_internal_api_key)])
def update_mission_status(payload: MissionStatusPayload):
    mission = APP_STATE["missions"].get(payload.mission_id)
    if mission is None:
        return {"status": "not_found"}
    mission["status"] = payload.status
    if payload.payment_status:
        mission["payment_status"] = payload.payment_status
    return {"status": "ok", "mission": mission}


@app.post("/api/bot/payments", dependencies=[Depends(require_internal_api_key)])
def update_payment(payload: PaymentPayload):
    mission = APP_STATE["missions"].get(payload.mission_id) if payload.mission_id is not None else None
    if mission is not None:
        mission["payment_status"] = payload.payment_status
    return {"status": "ok", "payment_status": payload.payment_status, "mission": mission}


@app.get("/api/profile/{telegram_id}", dependencies=[Depends(require_internal_api_key)])
def profile(telegram_id: int):
    user = APP_STATE["users"].get(telegram_id)
    provider = APP_STATE["providers"].get(telegram_id)
    missions = [mission for mission in APP_STATE["missions"].values() if mission["telegram_id"] == telegram_id]
    return {
        "telegram_id": telegram_id,
        "client": user or {"telegram_id": telegram_id, "first_name": "Client"},
        "provider": provider,
        "client_missions": missions,
        "provider_missions": missions,
        "service_requests": [],
        "profile_type": "client" if user else "provider" if provider else "guest",
    }
