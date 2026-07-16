import json
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Nexis Hub V5 Backend")

STATE_FILE = Path(os.getenv("BACKEND_STATE_FILE", "backend_state.json"))


def _load_state() -> dict[str, Any]:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"users": {}, "missions": {}, "providers": {}}
    return {"users": {}, "missions": {}, "providers": {}}


def _save_state(state: dict[str, Any]) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


APP_STATE: dict[str, Any] = _load_state()


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


@app.post("/api/bot/users")
def create_bot_user(payload: BotUserPayload):
    APP_STATE["users"][payload.telegram_id] = {
        "telegram_id": payload.telegram_id,
        "first_name": payload.first_name or "Client",
        "phone_number": payload.phone_number,
        "language": payload.language,
    }
    _save_state(APP_STATE)
    return {"status": "ok", "user": APP_STATE["users"][payload.telegram_id]}


@app.post("/api/bot/missions")
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
    _save_state(APP_STATE)
    return {"status": "ok", "mission": APP_STATE["missions"][payload.mission_id]}


@app.post("/api/bot/providers")
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
    _save_state(APP_STATE)
    return {"status": "ok", "provider": APP_STATE["providers"][payload.telegram_id]}


@app.post("/api/bot/missions/status")
def update_mission_status(payload: MissionStatusPayload):
    mission = APP_STATE["missions"].get(payload.mission_id)
    if mission is None:
        return {"status": "not_found"}
    mission["status"] = payload.status
    if payload.payment_status:
        mission["payment_status"] = payload.payment_status
    _save_state(APP_STATE)
    return {"status": "ok", "mission": mission}


@app.post("/api/bot/payments")
def update_payment(payload: PaymentPayload):
    mission = APP_STATE["missions"].get(payload.mission_id) if payload.mission_id is not None else None
    if mission is not None:
        mission["payment_status"] = payload.payment_status
    _save_state(APP_STATE)
    return {"status": "ok", "payment_status": payload.payment_status, "mission": mission}


@app.get("/api/profile/{telegram_id}")
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
