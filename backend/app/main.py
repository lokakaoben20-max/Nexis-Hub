from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel

from backend.app.database import SessionLocal, init_db
from backend.app.models import BotMission, BotProvider, BotUser


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Nexis Hub V5 Backend", lifespan=lifespan)


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


def _user_to_dict(user: BotUser) -> dict:
    return {
        "telegram_id": user.telegram_id,
        "first_name": user.first_name,
        "phone_number": user.phone_number,
        "language": user.language,
    }


def _provider_to_dict(provider: BotProvider) -> dict:
    return {
        "telegram_id": provider.telegram_id,
        "full_name": provider.full_name,
        "phone_number": provider.phone_number,
        "services": provider.services,
        "communes": provider.communes,
        "language": provider.language,
        "status": provider.status,
    }


def _mission_to_dict(mission: BotMission) -> dict:
    return {
        "mission_id": mission.mission_id,
        "telegram_id": mission.telegram_id,
        "service": mission.service,
        "commune": mission.commune,
        "currency": mission.currency,
        "description": mission.description,
        "urgent": mission.urgent,
        "status": mission.status,
        "payment_status": mission.payment_status,
    }


@app.get("/health")
def health():
    return {"status": "ok", "service": "nexis-hub-v5"}


@app.post("/api/bot/users")
def create_bot_user(payload: BotUserPayload):
    with SessionLocal() as db:
        user = db.get(BotUser, payload.telegram_id)
        if user is None:
            user = BotUser(telegram_id=payload.telegram_id)
        user.first_name = payload.first_name or "Client"
        user.phone_number = payload.phone_number
        user.language = payload.language
        db.merge(user)
        db.commit()
        user = db.get(BotUser, payload.telegram_id)
        return {"status": "ok", "user": _user_to_dict(user)}


@app.post("/api/bot/missions")
def create_bot_mission(payload: BotMissionPayload):
    with SessionLocal() as db:
        mission = BotMission(
            mission_id=payload.mission_id,
            telegram_id=payload.telegram_id,
            service=payload.service,
            commune=payload.commune,
            currency=payload.currency,
            description=payload.description,
            urgent=payload.urgent,
        )
        db.merge(mission)
        db.commit()
        mission = db.get(BotMission, payload.mission_id)
        return {"status": "ok", "mission": _mission_to_dict(mission)}


@app.post("/api/bot/providers")
def create_bot_provider(payload: BotProviderPayload):
    with SessionLocal() as db:
        provider = db.get(BotProvider, payload.telegram_id)
        if provider is None:
            provider = BotProvider(telegram_id=payload.telegram_id, full_name=payload.full_name)
        provider.full_name = payload.full_name
        provider.phone_number = payload.phone_number
        provider.services = payload.services or []
        provider.communes = payload.communes or []
        provider.language = payload.language
        provider.status = provider.status or "available"
        db.merge(provider)
        db.commit()
        provider = db.get(BotProvider, payload.telegram_id)
        return {"status": "ok", "provider": _provider_to_dict(provider)}


@app.post("/api/bot/missions/status")
def update_mission_status(payload: MissionStatusPayload):
    with SessionLocal() as db:
        mission = db.get(BotMission, payload.mission_id)
        if mission is None:
            return {"status": "not_found"}
        mission.status = payload.status
        if payload.payment_status:
            mission.payment_status = payload.payment_status
        db.commit()
        db.refresh(mission)
        return {"status": "ok", "mission": _mission_to_dict(mission)}


@app.post("/api/bot/payments")
def update_payment(payload: PaymentPayload):
    with SessionLocal() as db:
        mission = db.get(BotMission, payload.mission_id) if payload.mission_id is not None else None
        if mission is not None:
            mission.payment_status = payload.payment_status
            db.commit()
            db.refresh(mission)
        return {
            "status": "ok",
            "payment_status": payload.payment_status,
            "mission": _mission_to_dict(mission) if mission is not None else None,
        }


@app.get("/api/profile/{telegram_id}")
def profile(telegram_id: int):
    with SessionLocal() as db:
        user = db.get(BotUser, telegram_id)
        provider = db.get(BotProvider, telegram_id)
        missions = [
            _mission_to_dict(mission)
            for mission in db.query(BotMission).filter(BotMission.telegram_id == telegram_id).all()
        ]
        return {
            "telegram_id": telegram_id,
            "client": _user_to_dict(user) if user else {"telegram_id": telegram_id, "first_name": "Client"},
            "provider": _provider_to_dict(provider) if provider else None,
            "client_missions": missions,
            "provider_missions": missions,
            "service_requests": [],
            "profile_type": "client" if user else "provider" if provider else "guest",
        }
