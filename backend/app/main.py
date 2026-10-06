import hmac
import os

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field

from backend.app import crud, ledger, mobile_money, payment_gateway
from backend.app.database import SessionLocal
from backend.app.models import BotMission, BotProvider, BotQuote, BotReview, BotServiceRequest, BotUser, PaymentIntent, Payout

load_dotenv()
BACKEND_API_KEY = os.getenv("BACKEND_API_KEY", "")


# Le schéma est géré uniquement par Alembic (`alembic upgrade head` avant tout
# démarrage). Plus de `create_all` au démarrage : il créait des tables hors
# migrations, et la migration suivante échouait sur une table déjà là.
app = FastAPI(title="Nexis Hub V5 Backend")


def verify_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """Authentifie le bot (seul client légitime) sur toutes les routes /api/*.

    Ce backend n'a aucune authentification par utilisateur final : le bot est
    censé être le seul appelant, via une clé partagée envoyée dans l'en-tête
    X-API-Key. Voir le skill `securite-backend` avant d'exposer ce service
    au-delà de 127.0.0.1.
    """
    if not BACKEND_API_KEY:
        raise HTTPException(status_code=500, detail="BACKEND_API_KEY manquant côté serveur")
    if not x_api_key or not hmac.compare_digest(x_api_key, BACKEND_API_KEY):
        raise HTTPException(status_code=401, detail="Clé API invalide ou manquante")


# Toutes les routes /api/* passent par ce router protégé. /health reste sur
# `app` directement, sans authentification, pour rester utilisable par un
# outil de supervision externe.
router = APIRouter(dependencies=[Depends(verify_api_key)])


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
    id_document_file_id: str | None = None
    selfie_file_id: str | None = None
    portfolio_file_ids: list[str] | None = None


class ProviderServicesPayload(BaseModel):
    services: list[str]


class ProviderStatusPayload(BaseModel):
    status: str


class LanguagePayload(BaseModel):
    language: str


class NamePayload(BaseModel):
    first_name: str


class QuoteCreatePayload(BaseModel):
    mission_id: int
    provider_telegram_id: int
    amount: float
    currency: str = "USD"
    delay_hours: int
    message: str = ""


class FundPayload(BaseModel):
    method: str
    client_telegram_id: int
    provider_telegram_id: int
    quote_ref: int
    amount: float
    currency: str
    urgent: bool = False
    service: str
    commune: str
    description: str = ""


class PaymentIntentPayload(FundPayload):
    method: str = "mobile_money"
    phone: str
    operator: str


class PayoutPayload(BaseModel):
    telegram_id: int
    amount: float
    currency: str
    phone: str
    operator: str


class PayoutDecisionPayload(BaseModel):
    admin_telegram_id: int
    reason: str = ""


class ProviderActionPayload(BaseModel):
    provider_telegram_id: int


class ClientActionPayload(BaseModel):
    client_telegram_id: int


class DisputeOpenPayload(BaseModel):
    client_telegram_id: int
    reason: str


class DisputeResolvePayload(BaseModel):
    decision: str
    admin_telegram_id: int
    provider_percentage: float | None = None


class ReviewCreatePayload(BaseModel):
    mission_id: int
    client_telegram_id: int
    rating: int
    comment: str | None = None


class ProviderRankPayload(BaseModel):
    telegram_ids: list[int] = Field(max_length=100)


class ServiceRequestPayload(BaseModel):
    provider_telegram_id: int
    service_name: str
    description: str = ""


class ServiceRequestStatusPayload(BaseModel):
    status: str
    admin_note: str = ""


def _wallet_fields(db, telegram_id: int) -> dict:
    # Calculés depuis le registre, seule source de vérité (backend/app/ledger.py).
    # Un seul wallet par personne, qu'elle soit cliente, prestataire ou les deux.
    balances = ledger.wallet_balances(db, ledger.TELEGRAM, telegram_id)
    return {"wallet_balance_usd": float(balances["USD"]), "wallet_balance_cdf": float(balances["CDF"])}


def _user_to_dict(user: BotUser, db) -> dict:
    return {
        "telegram_id": user.telegram_id,
        "first_name": user.first_name,
        "phone_number": user.phone_number,
        "language": user.language,
        **_wallet_fields(db, user.telegram_id),
        "total_missions": user.total_missions,
    }


def _provider_to_dict(provider: BotProvider, db) -> dict:
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
        "average_rating": provider.average_rating,
        "total_reviews": provider.total_reviews,
        "is_verified": provider.is_verified,
        "is_active": provider.is_active,
        "is_suspended": provider.is_suspended,
        "consecutive_ignored": provider.consecutive_ignored,
        **_wallet_fields(db, provider.telegram_id),
        "id_document_file_id": provider.id_document_file_id,
        "selfie_file_id": provider.selfie_file_id,
        "portfolio_file_ids": provider.portfolio_file_ids,
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
        "dispute_deadline": mission.dispute_deadline.isoformat() if mission.dispute_deadline else None,
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


def _review_to_dict(review: BotReview) -> dict:
    return {
        "id": review.id,
        "mission_id": review.mission_id,
        "client_telegram_id": review.client_telegram_id,
        "provider_telegram_id": review.provider_telegram_id,
        "rating": review.rating,
        "comment": review.comment,
        "created_at": review.created_at.isoformat() if review.created_at else None,
    }


def _service_request_to_dict(req: BotServiceRequest, provider: BotProvider | None = None) -> dict:
    data = {
        "id": req.id,
        "provider_telegram_id": req.provider_telegram_id,
        "service_name": req.service_name,
        "description": req.description,
        "status": req.status,
        "admin_note": req.admin_note,
        "created_at": req.created_at.isoformat() if req.created_at else None,
        "reviewed_at": req.reviewed_at.isoformat() if req.reviewed_at else None,
    }
    if provider is not None:
        data["provider_name"] = provider.full_name
    return data


@app.get("/health")
def health():
    return {"status": "ok", "service": "nexis-hub-v5"}


@router.post("/api/bot/users")
def create_bot_user(payload: BotUserPayload):
    with SessionLocal() as db:
        user = crud.upsert_user(db, payload.telegram_id, payload.first_name, payload.phone_number, payload.language)
        return {"status": "ok", "user": _user_to_dict(user, db)}


@router.post("/api/bot/missions")
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


@router.post("/api/bot/providers")
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
            id_document_file_id=payload.id_document_file_id,
            selfie_file_id=payload.selfie_file_id,
            portfolio_file_ids=payload.portfolio_file_ids,
        )
        return {"status": "ok", "provider": _provider_to_dict(provider, db)}


@router.patch("/api/bot/users/{telegram_id}/language")
def update_user_language(telegram_id: int, payload: LanguagePayload):
    with SessionLocal() as db:
        user = crud.update_user_language(db, telegram_id, payload.language)
        if user is None:
            raise HTTPException(status_code=404, detail="user_not_found")
        return {"status": "ok", "user": _user_to_dict(user, db)}


@router.patch("/api/bot/users/{telegram_id}/name")
def update_user_name(telegram_id: int, payload: NamePayload):
    with SessionLocal() as db:
        user = crud.update_user_name(db, telegram_id, payload.first_name)
        if user is None:
            raise HTTPException(status_code=404, detail="user_not_found")
        return {"status": "ok", "user": _user_to_dict(user, db)}


@router.patch("/api/bot/providers/{telegram_id}/language")
def update_provider_language(telegram_id: int, payload: LanguagePayload):
    with SessionLocal() as db:
        provider = crud.update_provider_language(db, telegram_id, payload.language)
        if provider is None:
            raise HTTPException(status_code=404, detail="provider_not_found")
        return {"status": "ok", "provider": _provider_to_dict(provider, db)}


@router.patch("/api/bot/providers/{telegram_id}/services")
def update_provider_services(telegram_id: int, payload: ProviderServicesPayload):
    with SessionLocal() as db:
        provider = crud.update_provider_services(db, telegram_id, payload.services)
        if provider is None:
            raise HTTPException(status_code=404, detail="provider_not_found")
        return {"status": "ok", "provider": _provider_to_dict(provider, db)}


@router.patch("/api/bot/providers/{telegram_id}/status")
def update_provider_status(telegram_id: int, payload: ProviderStatusPayload):
    with SessionLocal() as db:
        provider = crud.update_provider_status(db, telegram_id, payload.status)
        if provider is None:
            raise HTTPException(status_code=404, detail="provider_not_found")
        return {"status": "ok", "provider": _provider_to_dict(provider, db)}


@router.post("/api/bot/providers/{telegram_id}/verify")
def verify_provider(telegram_id: int):
    with SessionLocal() as db:
        provider = crud.set_provider_verified(db, telegram_id, True)
        if provider is None:
            raise HTTPException(status_code=404, detail="provider_not_found")
        return {"status": "ok", "provider": _provider_to_dict(provider, db)}


@router.post("/api/bot/providers/{telegram_id}/suspend")
def suspend_provider(telegram_id: int):
    with SessionLocal() as db:
        provider = crud.set_provider_suspended(db, telegram_id, True)
        if provider is None:
            raise HTTPException(status_code=404, detail="provider_not_found")
        return {"status": "ok", "provider": _provider_to_dict(provider, db)}


@router.post("/api/bot/providers/{telegram_id}/unsuspend")
def unsuspend_provider(telegram_id: int):
    with SessionLocal() as db:
        provider = crud.set_provider_suspended(db, telegram_id, False)
        if provider is None:
            raise HTTPException(status_code=404, detail="provider_not_found")
        return {"status": "ok", "provider": _provider_to_dict(provider, db)}


@router.post("/api/bot/providers/{telegram_id}/ignored")
def increment_provider_ignored(telegram_id: int):
    with SessionLocal() as db:
        provider = crud.update_consecutive_ignored(db, telegram_id)
        if provider is None:
            raise HTTPException(status_code=404, detail="provider_not_found")
        return {"status": "ok", "provider": _provider_to_dict(provider, db)}


@router.post("/api/bot/providers/{telegram_id}/ignored/reset")
def reset_provider_ignored(telegram_id: int):
    with SessionLocal() as db:
        provider = crud.reset_consecutive_ignored(db, telegram_id)
        if provider is None:
            raise HTTPException(status_code=404, detail="provider_not_found")
        return {"status": "ok", "provider": _provider_to_dict(provider, db)}


@router.get("/api/bot/providers/matching")
def matching_providers(service: str, commune: str):
    with SessionLocal() as db:
        providers = crud.find_matching_providers(db, service, commune)
        return {"status": "ok", "providers": [_provider_to_dict(provider, db) for provider in providers]}


@router.post("/api/bot/providers/rank")
def rank_providers(payload: ProviderRankPayload):
    # Ne renvoie que l'ordre (pas de téléphone ni de pièce d'identité) : le bot
    # a déjà la liste des prestataires disponibles, il lui manque le score.
    with SessionLocal() as db:
        return {"status": "ok", "telegram_ids": crud.rank_providers(db, payload.telegram_ids)}


@router.post("/api/bot/quotes")
def create_quote(payload: QuoteCreatePayload):
    with SessionLocal() as db:
        try:
            quote = crud.create_quote(
                db,
                mission_id=payload.mission_id,
                provider_telegram_id=payload.provider_telegram_id,
                amount=payload.amount,
                currency=payload.currency,
                delay_hours=payload.delay_hours,
                message=payload.message,
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail={"code": str(exc)}) from exc
        if quote is None:
            raise HTTPException(status_code=404, detail="mission_not_found")
        return {"status": "ok", "quote": _quote_to_dict(quote)}


@router.post("/api/bot/reviews")
def create_review(payload: ReviewCreatePayload):
    with SessionLocal() as db:
        try:
            review = crud.create_review(
                db,
                mission_id=payload.mission_id,
                client_telegram_id=payload.client_telegram_id,
                rating=payload.rating,
                comment=payload.comment,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"status": "ok", "review": _review_to_dict(review)}


@router.post("/api/bot/quotes/{quote_id}/accept")
def accept_quote(quote_id: int):
    with SessionLocal() as db:
        quote = crud.accept_quote(db, quote_id)
        if quote is None:
            raise HTTPException(status_code=404, detail="quote_not_found")
        return {"status": "ok", "quote": _quote_to_dict(quote)}


@router.post("/api/bot/quotes/{quote_id}/reject")
def reject_quote(quote_id: int):
    with SessionLocal() as db:
        quote = crud.reject_quote(db, quote_id)
        if quote is None:
            raise HTTPException(status_code=404, detail="quote_not_found")
        return {"status": "ok", "quote": _quote_to_dict(quote)}


def _money_response(db, mission: BotMission) -> dict:
    return {
        "status": "ok",
        "mission": _mission_to_dict(mission),
        "money": ledger.mission_money_state(db, mission.mission_id),
    }


def _money_refusal(db, error: ledger.MoneyError) -> HTTPException:
    """Refus métier : code stable + état courant de la mission, que le bot
    recopie pour ne jamais afficher un état périmé."""
    # Id lu avant l'annulation : une mission créée par cette même demande
    # disparaît avec elle et l'objet n'est plus lisible ensuite.
    mission_id = error.mission.mission_id if error.mission is not None else None
    db.rollback()
    detail = {"code": error.code}
    if mission_id is not None:
        mission = db.get(BotMission, mission_id)
        if mission is not None:
            detail["mission"] = _mission_to_dict(mission)
            detail["money"] = ledger.mission_money_state(db, mission.mission_id)
    return HTTPException(status_code=error.http_status, detail=detail)


def _money_call(operation):
    with SessionLocal() as db:
        try:
            mission = operation(db)
        except ledger.MoneyError as error:
            raise _money_refusal(db, error) from error
        return _money_response(db, mission)


@router.post("/api/bot/missions/{mission_id}/fund")
def fund_mission(mission_id: int, payload: FundPayload):
    # Seul le wallet paie directement : un paiement Mobile Money n'existe que
    # confirmé par l'agrégateur (/payment-intents, CONCEPTION_MOBILE_MONEY.md).
    if payload.method != "wallet":
        raise HTTPException(status_code=400, detail={"code": "use_payment_intent"})
    return _money_call(
        lambda db: ledger.fund_mission(
            db,
            mission_id,
            method=payload.method,
            client_telegram_id=payload.client_telegram_id,
            provider_telegram_id=payload.provider_telegram_id,
            quote_ref=payload.quote_ref,
            amount=payload.amount,
            currency=payload.currency,
            urgent=payload.urgent,
            service=payload.service,
            commune=payload.commune,
            description=payload.description,
        )
    )


def _intent_to_dict(intent: PaymentIntent) -> dict:
    return {
        "id": intent.id,
        "mission_id": intent.mission_id,
        "status": intent.status,
        "operator": intent.operator,
        "amount": str(intent.amount),
        "currency": intent.currency,
        "gateway_reference": intent.gateway_reference,
        "failure_reason": intent.failure_reason,
    }


def _payout_to_dict(payout: Payout) -> dict:
    return {
        "id": payout.id,
        "status": payout.status,
        "requested_by_telegram_id": payout.requested_by_telegram_id,
        "amount": str(payout.amount),
        "fee": str(payout.fee),
        "net": str(payout.amount - payout.fee),
        "currency": payout.currency,
        "operator": payout.operator,
        "phone": payout.phone,
        "needs_review_reason": payout.needs_review_reason,
        "failure_reason": payout.failure_reason,
    }


def _intent_response(db, intent: PaymentIntent) -> dict:
    mission = db.get(BotMission, intent.mission_id)
    return {**_money_response(db, mission), "intent": _intent_to_dict(intent)}


@router.post("/api/bot/missions/{mission_id}/payment-intents")
def create_payment_intent(mission_id: int, payload: PaymentIntentPayload):
    funding_request = payload.model_dump(exclude={"method", "phone", "operator"})
    with SessionLocal() as db:
        try:
            intent = mobile_money.create_intent(
                db, mission_id, phone=payload.phone, operator=payload.operator, funding_request=funding_request
            )
        except ledger.MoneyError as error:
            raise _money_refusal(db, error) from error
        return _intent_response(db, intent)


@router.post("/api/bot/payment-intents/{intent_id}/refresh")
def refresh_payment_intent(intent_id: int):
    with SessionLocal() as db:
        try:
            intent = mobile_money.refresh_intent(db, intent_id)
        except ledger.MoneyError as error:
            raise _money_refusal(db, error) from error
        return _intent_response(db, intent)


def _payout_call(operation):
    with SessionLocal() as db:
        try:
            payout = operation(db)
        except ledger.MoneyError as error:
            db.rollback()
            raise HTTPException(status_code=error.http_status, detail={"code": error.code}) from error
        return {"status": "ok", "payout": _payout_to_dict(payout)}


@router.post("/api/bot/payouts")
def request_payout(payload: PayoutPayload):
    return _payout_call(
        lambda db: mobile_money.request_payout(
            db,
            telegram_id=payload.telegram_id,
            amount=payload.amount,
            currency=payload.currency,
            phone=payload.phone,
            operator=payload.operator,
        )
    )


@router.get("/api/bot/payouts")
def list_payouts(status: str = "awaiting_approval", limit: int = 20):
    with SessionLocal() as db:
        payouts = db.query(Payout).filter(Payout.status == status).order_by(Payout.id).limit(min(limit, 50)).all()
        return {"status": "ok", "payouts": [_payout_to_dict(payout) for payout in payouts]}


@router.post("/api/bot/payouts/{payout_id}/approve")
def approve_payout(payout_id: int, payload: PayoutDecisionPayload):
    return _payout_call(lambda db: mobile_money.approve_payout(db, payout_id, payload.admin_telegram_id))


@router.post("/api/bot/payouts/{payout_id}/reject")
def reject_payout(payout_id: int, payload: PayoutDecisionPayload):
    return _payout_call(lambda db: mobile_money.reject_payout(db, payout_id, payload.admin_telegram_id, payload.reason))


@app.post("/api/payments/webhook/{gateway_name}")
async def payment_webhook(gateway_name: str, request: Request):
    """Confirmation de l'agrégateur. Hors clé API (c'est l'agrégateur qui
    appelle) : signature vérifiée, puis statut toujours relu chez lui avant de
    bouger quoi que ce soit (`refresh_intent` / `refresh_payout`)."""
    gateway = payment_gateway.get_gateway()
    if gateway_name != gateway.name:
        raise HTTPException(status_code=404, detail={"code": "unknown_gateway"})
    try:
        reference = gateway.verify_webhook(request.headers, await request.body())
    except payment_gateway.InvalidWebhook as error:
        raise HTTPException(status_code=401, detail={"code": "invalid_signature"}) from error
    from backend.app.tasks import refresh_and_notify_intent, refresh_and_notify_payout

    with SessionLocal() as db:
        intent = db.query(PaymentIntent).filter_by(gateway=gateway.name, gateway_reference=reference).one_or_none()
        payout = db.query(Payout).filter_by(gateway=gateway.name, gateway_reference=reference).one_or_none()
        if intent is not None:
            refresh_and_notify_intent(db, intent.id)
        elif payout is not None:
            refresh_and_notify_payout(db, payout.id)
        else:
            return {"status": "ignored"}
    return {"status": "ok"}


@router.post("/api/bot/missions/{mission_id}/start")
def start_mission(mission_id: int, payload: ProviderActionPayload):
    return _money_call(lambda db: ledger.start_mission(db, mission_id, payload.provider_telegram_id))


@router.post("/api/bot/missions/{mission_id}/finish")
def finish_mission(mission_id: int, payload: ProviderActionPayload):
    return _money_call(lambda db: ledger.finish_mission(db, mission_id, payload.provider_telegram_id))


@router.post("/api/bot/missions/{mission_id}/confirm")
def confirm_mission(mission_id: int, payload: ClientActionPayload):
    return _money_call(lambda db: ledger.confirm_completion(db, mission_id, payload.client_telegram_id))


@router.post("/api/bot/missions/{mission_id}/dispute")
def open_dispute(mission_id: int, payload: DisputeOpenPayload):
    return _money_call(lambda db: ledger.open_dispute(db, mission_id, payload.client_telegram_id, payload.reason))


@router.post("/api/bot/missions/{mission_id}/dispute/resolve")
def resolve_dispute(mission_id: int, payload: DisputeResolvePayload):
    return _money_call(
        lambda db: ledger.resolve_dispute(
            db,
            mission_id,
            decision=payload.decision,
            admin_telegram_id=payload.admin_telegram_id,
            provider_percentage=payload.provider_percentage,
        )
    )


@router.get("/api/bot/missions/{mission_id}")
def get_mission(mission_id: int):
    with SessionLocal() as db:
        mission = db.get(BotMission, mission_id)
        if mission is None:
            raise HTTPException(status_code=404, detail={"code": "mission_not_found"})
        return _money_response(db, mission)


@router.get("/api/bot/wallets/{telegram_id}")
def get_wallets(telegram_id: int):
    with SessionLocal() as db:
        return {"status": "ok", "telegram_id": telegram_id, "wallet": _wallet_fields(db, telegram_id)}


@router.post("/api/bot/service-requests")
def create_service_request(payload: ServiceRequestPayload):
    with SessionLocal() as db:
        try:
            req = crud.create_service_request(
                db,
                provider_telegram_id=payload.provider_telegram_id,
                service_name=payload.service_name,
                description=payload.description,
            )
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {"status": "ok", "service_request": _service_request_to_dict(req)}


@router.get("/api/bot/service-requests/pending")
def get_pending_service_requests(limit: int = 10):
    with SessionLocal() as db:
        results = crud.get_pending_service_requests(db, limit=limit)
        serialized = [_service_request_to_dict(req, provider) for req, provider in results]
        return {"status": "ok", "service_requests": serialized}


@router.get("/api/bot/service-requests/{request_id}")
def get_service_request(request_id: int):
    with SessionLocal() as db:
        result = crud.get_service_request_by_id(db, request_id)
        if result is None:
            raise HTTPException(status_code=404, detail="service_request_not_found")
        req, provider = result
        return {"status": "ok", "service_request": _service_request_to_dict(req, provider)}


@router.patch("/api/bot/service-requests/{request_id}/status")
def update_service_request_status(request_id: int, payload: ServiceRequestStatusPayload):
    with SessionLocal() as db:
        try:
            req = crud.update_service_request_status(
                db,
                request_id=request_id,
                status=payload.status,
                admin_note=payload.admin_note,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if req is None:
            raise HTTPException(status_code=404, detail="service_request_not_found")
        return {"status": "ok", "service_request": _service_request_to_dict(req)}


@router.get("/api/profile/{telegram_id}")
def profile(telegram_id: int):
    with SessionLocal() as db:
        user = db.get(BotUser, telegram_id)
        provider = db.get(BotProvider, telegram_id)
        client_missions = [
            _mission_to_dict(mission)
            for mission in db.query(BotMission).filter(BotMission.telegram_id == telegram_id).all()
        ]
        provider_missions = []
        for mission in db.query(BotMission).filter(BotMission.provider_telegram_id == telegram_id).all():
            mission_data = _mission_to_dict(mission)
            client = db.get(BotUser, mission.telegram_id)
            # `get_provider_missions` dans db.py expose déjà ce champ grâce à
            # sa jointure avec users ; le conserver dans le contrat V5 évite
            # d'appauvrir l'affichage prestataire lors du basculement de lecture.
            mission_data["client_name"] = client.first_name if client else None
            provider_missions.append(mission_data)

        service_requests = []
        if provider:
            service_requests = [
                _service_request_to_dict(req)
                for req in crud.get_provider_service_requests(db, telegram_id)
            ]

        return {
            "telegram_id": telegram_id,
            "client": _user_to_dict(user, db) if user else None,
            "provider": _provider_to_dict(provider, db) if provider else None,
            "client_missions": client_missions,
            "provider_missions": provider_missions,
            "service_requests": service_requests,
            "profile_type": "client" if user else "provider" if provider else "guest",
        }


app.include_router(router)
