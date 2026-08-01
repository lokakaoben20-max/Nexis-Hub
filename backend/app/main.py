from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from backend.app import crud
from backend.app.database import SessionLocal, init_db
from backend.app.models import BotMission, BotProvider, BotQuote, BotUser


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


class ProviderServicesPayload(BaseModel):
    services: list[str]


class ProviderStatusPayload(BaseModel):
    status: str


class QuoteCreatePayload(BaseModel):
    mission_id: int
    provider_telegram_id: int
    amount: float
    currency: str = "USD"
    delay_hours: int
    message: str = ""


class MissionActionPayload(BaseModel):
    provider_telegram_id: int


class PaymentOperatorPayload(BaseModel):
    operator: str = "simulation"


def _user_to_dict(user: BotUser) -> dict:
    return {
        "telegram_id": user.telegram_id,
        "first_name": user.first_name,
        "phone_number": user.phone_number,
        "language": user.language,
        "wallet_balance_usd": user.wallet_balance_usd,
        "wallet_balance_cdf": user.wallet_balance_cdf,
        "total_missions": user.total_missions,
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
        "module": provider.module,
        "badge": provider.badge,
        "rating": provider.rating,
        "total_missions": provider.total_missions,
        "success_rate": provider.success_rate,
        "is_verified": provider.is_verified,
        "is_active": provider.is_active,
        "is_suspended": provider.is_suspended,
        "consecutive_ignored": provider.consecutive_ignored,
        "wallet_balance_usd": provider.wallet_balance_usd,
        "wallet_balance_cdf": provider.wallet_balance_cdf,
    }


def _mission_to_dict(mission: BotMission) -> dict:
    return {
        "mission_id": mission.mission_id,
        "telegram_id": mission.telegram_id,
        "provider_telegram_id": mission.provider_telegram_id,
        "service": mission.service,
        "commune": mission.commune,
        "currency": mission.currency,
        "description": mission.description,
        "urgent": mission.urgent,
        "status": mission.status,
        "payment_status": mission.payment_status,
        "commission_amount": mission.commission_amount,
        "tola_fee": mission.tola_fee,
        "aggregator_fee": mission.aggregator_fee,
        "total_client": mission.total_client,
        "net_provider": mission.net_provider,
        "dispute_reason": mission.dispute_reason,
    }


def _quote_to_dict(quote: BotQuote) -> dict:
    return {
        "id": quote.id,
        "mission_id": quote.mission_id,
        "provider_telegram_id": quote.provider_telegram_id,
        "amount": quote.amount,
        "currency": quote.currency,
        "delay_hours": quote.delay_hours,
        "message": quote.message,
        "status": quote.status,
    }


@app.get("/health")
def health():
    return {"status": "ok", "service": "nexis-hub-v5"}


@app.post("/api/bot/users")
def create_bot_user(payload: BotUserPayload):
    with SessionLocal() as db:
        user = crud.upsert_user(db, payload.telegram_id, payload.first_name, payload.phone_number, payload.language)
        return {"status": "ok", "user": _user_to_dict(user)}


@app.post("/api/bot/missions")
def create_bot_mission(payload: BotMissionPayload):
    with SessionLocal() as db:
        mission = crud.create_mission(
            db,
            telegram_id=payload.telegram_id,
            mission_id=payload.mission_id,
            service=payload.service,
            commune=payload.commune,
            currency=payload.currency,
            description=payload.description,
            urgent=payload.urgent,
        )
        return {"status": "ok", "mission": _mission_to_dict(mission)}


@app.post("/api/bot/providers")
def create_bot_provider(payload: BotProviderPayload):
    with SessionLocal() as db:
        provider = crud.upsert_provider(
            db,
            telegram_id=payload.telegram_id,
            full_name=payload.full_name,
            phone_number=payload.phone_number,
            services=payload.services or [],
            communes=payload.communes or [],
            language=payload.language,
        )
        return {"status": "ok", "provider": _provider_to_dict(provider)}


@app.patch("/api/bot/providers/{telegram_id}/services")
def update_provider_services(telegram_id: int, payload: ProviderServicesPayload):
    with SessionLocal() as db:
        provider = crud.update_provider_services(db, telegram_id, payload.services)
        if provider is None:
            raise HTTPException(status_code=404, detail="provider_not_found")
        return {"status": "ok", "provider": _provider_to_dict(provider)}


@app.patch("/api/bot/providers/{telegram_id}/status")
def update_provider_status(telegram_id: int, payload: ProviderStatusPayload):
    with SessionLocal() as db:
        provider = crud.update_provider_status(db, telegram_id, payload.status)
        if provider is None:
            raise HTTPException(status_code=404, detail="provider_not_found")
        return {"status": "ok", "provider": _provider_to_dict(provider)}


@app.post("/api/bot/providers/{telegram_id}/verify")
def verify_provider(telegram_id: int):
    with SessionLocal() as db:
        provider = crud.set_provider_verified(db, telegram_id, True)
        if provider is None:
            raise HTTPException(status_code=404, detail="provider_not_found")
        return {"status": "ok", "provider": _provider_to_dict(provider)}


@app.post("/api/bot/providers/{telegram_id}/suspend")
def suspend_provider(telegram_id: int):
    with SessionLocal() as db:
        provider = crud.set_provider_suspended(db, telegram_id, True)
        if provider is None:
            raise HTTPException(status_code=404, detail="provider_not_found")
        return {"status": "ok", "provider": _provider_to_dict(provider)}


@app.post("/api/bot/providers/{telegram_id}/ignored")
def increment_provider_ignored(telegram_id: int):
    with SessionLocal() as db:
        provider = crud.update_consecutive_ignored(db, telegram_id)
        if provider is None:
            raise HTTPException(status_code=404, detail="provider_not_found")
        return {"status": "ok", "provider": _provider_to_dict(provider)}


@app.post("/api/bot/providers/{telegram_id}/ignored/reset")
def reset_provider_ignored(telegram_id: int):
    with SessionLocal() as db:
        provider = crud.reset_consecutive_ignored(db, telegram_id)
        if provider is None:
            raise HTTPException(status_code=404, detail="provider_not_found")
        return {"status": "ok", "provider": _provider_to_dict(provider)}


@app.get("/api/bot/providers/matching")
def matching_providers(service: str, commune: str):
    with SessionLocal() as db:
        providers = crud.find_matching_providers(db, service, commune)
        return {"status": "ok", "providers": [_provider_to_dict(provider) for provider in providers]}


@app.post("/api/bot/quotes")
def create_quote(payload: QuoteCreatePayload):
    with SessionLocal() as db:
        quote = crud.create_quote(
            db,
            mission_id=payload.mission_id,
            provider_telegram_id=payload.provider_telegram_id,
            amount=payload.amount,
            currency=payload.currency,
            delay_hours=payload.delay_hours,
            message=payload.message,
        )
        if quote is None:
            raise HTTPException(status_code=404, detail="mission_not_found")
        return {"status": "ok", "quote": _quote_to_dict(quote)}


@app.post("/api/bot/quotes/{quote_id}/accept")
def accept_quote(quote_id: int):
    with SessionLocal() as db:
        quote = crud.accept_quote(db, quote_id)
        if quote is None:
            raise HTTPException(status_code=404, detail="quote_not_found")
        return {"status": "ok", "quote": _quote_to_dict(quote)}


@app.post("/api/bot/quotes/{quote_id}/reject")
def reject_quote(quote_id: int):
    with SessionLocal() as db:
        quote = crud.reject_quote(db, quote_id)
        if quote is None:
            raise HTTPException(status_code=404, detail="quote_not_found")
        return {"status": "ok", "quote": _quote_to_dict(quote)}


@app.post("/api/bot/quotes/{quote_id}/pay")
def pay_quote(quote_id: int, payload: PaymentOperatorPayload):
    with SessionLocal() as db:
        result = crud.mark_quote_paid(db, quote_id, payload.operator)
        if result is None:
            raise HTTPException(status_code=404, detail="quote_not_found")
        return {"status": "ok", **result}


@app.post("/api/bot/quotes/{quote_id}/pay-wallet")
def pay_quote_with_wallet(quote_id: int, payload: PaymentOperatorPayload):
    with SessionLocal() as db:
        try:
            result = crud.mark_quote_paid_with_wallet(db, quote_id, payload.operator)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"status": "ok", **result}


@app.post("/api/bot/missions/{mission_id}/start")
def start_mission(mission_id: int, payload: MissionActionPayload):
    with SessionLocal() as db:
        try:
            mission = crud.start_mission(db, mission_id, payload.provider_telegram_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"status": "ok", "mission": _mission_to_dict(mission)}


@app.post("/api/bot/missions/{mission_id}/finish")
def finish_mission(mission_id: int, payload: MissionActionPayload):
    with SessionLocal() as db:
        try:
            mission = crud.finish_mission(db, mission_id, payload.provider_telegram_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"status": "ok", "mission": _mission_to_dict(mission)}


@app.post("/api/bot/missions/{mission_id}/release")
def release_payment(mission_id: int):
    with SessionLocal() as db:
        try:
            mission = crud.release_payment(db, mission_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"status": "ok", "mission": _mission_to_dict(mission)}


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
