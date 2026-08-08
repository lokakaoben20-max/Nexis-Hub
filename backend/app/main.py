import hmac
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel

from backend.app import crud
from backend.app.database import SessionLocal, init_db
from backend.app.models import BotMission, BotProvider, BotQuote, BotReview, BotTransaction, BotUser

load_dotenv()
BACKEND_API_KEY = os.getenv("BACKEND_API_KEY", "")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Nexis Hub V5 Backend", lifespan=lifespan)


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


class MissionStatusPayload(BaseModel):
    mission_id: int
    status: str
    payment_status: str | None = None
    dispute_reason: str | None = None
    # Montant à rembourser au client (résolution de litige). Explicite plutôt
    # que dérivé de total_client/net_provider côté serveur : un partage à
    # l'amiable libère net_provider ET rembourse une partie du reste, deux
    # montants indépendants qu'aucun champ existant ne permet de reconstruire
    # de façon fiable après coup.
    refund_amount: float | None = None
    # Part réduite du prestataire pour un partage à l'amiable (sinon la
    # branche "releasing" créditerait le net_provider ORIGINAL, posé au
    # paiement escrow initial, pas la part réellement due après le partage —
    # bug trouvé par security-reviewer/backend-parity-auditor).
    net_provider: float | None = None


class PaymentPayload(BaseModel):
    quote_id: int
    payment_status: str
    mission_id: int | None = None
    # Champs optionnels : quand présents (paiement réellement effectué côté
    # bot), le backend reflète la transaction et débite le wallet client sans
    # rejouer sa propre validation — db.py reste la source de vérité. Absents,
    # le comportement retombe sur l'ancien (juste poser payment_status), pour
    # ne rien casser côté appelants qui n'envoient pas encore ces champs.
    amount: float | None = None
    currency: str | None = None
    commission_amount: float | None = None
    tola_fee: float = 0.0
    aggregator_fee: float = 0.0
    total_client: float | None = None
    net_provider: float | None = None
    mobile_money_ref: str | None = None
    operator: str | None = None
    via_wallet: bool = False


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


class MissionActionPayload(BaseModel):
    provider_telegram_id: int


class PaymentOperatorPayload(BaseModel):
    operator: str = "simulation"


class ReviewCreatePayload(BaseModel):
    mission_id: int
    client_telegram_id: int
    rating: int
    comment: str | None = None


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
        "average_rating": provider.average_rating,
        "total_reviews": provider.total_reviews,
        "is_verified": provider.is_verified,
        "is_active": provider.is_active,
        "is_suspended": provider.is_suspended,
        "consecutive_ignored": provider.consecutive_ignored,
        "wallet_balance_usd": provider.wallet_balance_usd,
        "wallet_balance_cdf": provider.wallet_balance_cdf,
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


@app.get("/health")
def health():
    return {"status": "ok", "service": "nexis-hub-v5"}


@router.post("/api/bot/users")
def create_bot_user(payload: BotUserPayload):
    with SessionLocal() as db:
        user = crud.upsert_user(db, payload.telegram_id, payload.first_name, payload.phone_number, payload.language)
        return {"status": "ok", "user": _user_to_dict(user)}


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
        return {"status": "ok", "provider": _provider_to_dict(provider)}


@router.patch("/api/bot/users/{telegram_id}/language")
def update_user_language(telegram_id: int, payload: LanguagePayload):
    with SessionLocal() as db:
        user = crud.update_user_language(db, telegram_id, payload.language)
        if user is None:
            raise HTTPException(status_code=404, detail="user_not_found")
        return {"status": "ok", "user": _user_to_dict(user)}


@router.patch("/api/bot/users/{telegram_id}/name")
def update_user_name(telegram_id: int, payload: NamePayload):
    with SessionLocal() as db:
        user = crud.update_user_name(db, telegram_id, payload.first_name)
        if user is None:
            raise HTTPException(status_code=404, detail="user_not_found")
        return {"status": "ok", "user": _user_to_dict(user)}


@router.patch("/api/bot/providers/{telegram_id}/language")
def update_provider_language(telegram_id: int, payload: LanguagePayload):
    with SessionLocal() as db:
        provider = crud.update_provider_language(db, telegram_id, payload.language)
        if provider is None:
            raise HTTPException(status_code=404, detail="provider_not_found")
        return {"status": "ok", "provider": _provider_to_dict(provider)}


@router.patch("/api/bot/providers/{telegram_id}/services")
def update_provider_services(telegram_id: int, payload: ProviderServicesPayload):
    with SessionLocal() as db:
        provider = crud.update_provider_services(db, telegram_id, payload.services)
        if provider is None:
            raise HTTPException(status_code=404, detail="provider_not_found")
        return {"status": "ok", "provider": _provider_to_dict(provider)}


@router.patch("/api/bot/providers/{telegram_id}/status")
def update_provider_status(telegram_id: int, payload: ProviderStatusPayload):
    with SessionLocal() as db:
        provider = crud.update_provider_status(db, telegram_id, payload.status)
        if provider is None:
            raise HTTPException(status_code=404, detail="provider_not_found")
        return {"status": "ok", "provider": _provider_to_dict(provider)}


@router.post("/api/bot/providers/{telegram_id}/verify")
def verify_provider(telegram_id: int):
    with SessionLocal() as db:
        provider = crud.set_provider_verified(db, telegram_id, True)
        if provider is None:
            raise HTTPException(status_code=404, detail="provider_not_found")
        return {"status": "ok", "provider": _provider_to_dict(provider)}


@router.post("/api/bot/providers/{telegram_id}/suspend")
def suspend_provider(telegram_id: int):
    with SessionLocal() as db:
        provider = crud.set_provider_suspended(db, telegram_id, True)
        if provider is None:
            raise HTTPException(status_code=404, detail="provider_not_found")
        return {"status": "ok", "provider": _provider_to_dict(provider)}


@router.post("/api/bot/providers/{telegram_id}/unsuspend")
def unsuspend_provider(telegram_id: int):
    with SessionLocal() as db:
        provider = crud.set_provider_suspended(db, telegram_id, False)
        if provider is None:
            raise HTTPException(status_code=404, detail="provider_not_found")
        return {"status": "ok", "provider": _provider_to_dict(provider)}


@router.post("/api/bot/providers/{telegram_id}/ignored")
def increment_provider_ignored(telegram_id: int):
    with SessionLocal() as db:
        provider = crud.update_consecutive_ignored(db, telegram_id)
        if provider is None:
            raise HTTPException(status_code=404, detail="provider_not_found")
        return {"status": "ok", "provider": _provider_to_dict(provider)}


@router.post("/api/bot/providers/{telegram_id}/ignored/reset")
def reset_provider_ignored(telegram_id: int):
    with SessionLocal() as db:
        provider = crud.reset_consecutive_ignored(db, telegram_id)
        if provider is None:
            raise HTTPException(status_code=404, detail="provider_not_found")
        return {"status": "ok", "provider": _provider_to_dict(provider)}


@router.get("/api/bot/providers/matching")
def matching_providers(service: str, commune: str):
    with SessionLocal() as db:
        providers = crud.find_matching_providers(db, service, commune)
        return {"status": "ok", "providers": [_provider_to_dict(provider) for provider in providers]}


@router.post("/api/bot/quotes")
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


@router.post("/api/bot/quotes/{quote_id}/pay")
def pay_quote(quote_id: int, payload: PaymentOperatorPayload):
    with SessionLocal() as db:
        result = crud.mark_quote_paid(db, quote_id, payload.operator)
        if result is None:
            raise HTTPException(status_code=404, detail="quote_not_found")
        return {"status": "ok", **result}


@router.post("/api/bot/quotes/{quote_id}/pay-wallet")
def pay_quote_with_wallet(quote_id: int, payload: PaymentOperatorPayload):
    with SessionLocal() as db:
        try:
            result = crud.mark_quote_paid_with_wallet(db, quote_id, payload.operator)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"status": "ok", **result}


@router.post("/api/bot/missions/{mission_id}/start")
def start_mission(mission_id: int, payload: MissionActionPayload):
    with SessionLocal() as db:
        try:
            mission = crud.start_mission(db, mission_id, payload.provider_telegram_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"status": "ok", "mission": _mission_to_dict(mission)}


@router.post("/api/bot/missions/{mission_id}/finish")
def finish_mission(mission_id: int, payload: MissionActionPayload):
    with SessionLocal() as db:
        try:
            mission = crud.finish_mission(db, mission_id, payload.provider_telegram_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"status": "ok", "mission": _mission_to_dict(mission)}


@router.post("/api/bot/missions/{mission_id}/release")
def release_payment(mission_id: int):
    with SessionLocal() as db:
        try:
            mission = crud.release_payment(db, mission_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"status": "ok", "mission": _mission_to_dict(mission)}


@router.post("/api/bot/missions/status")
def update_mission_status(payload: MissionStatusPayload):
    with SessionLocal() as db:
        mission = db.get(BotMission, payload.mission_id)
        if mission is None:
            return {"status": "not_found"}
        # Idempotence basée sur l'existence d'une transaction "release", pas
        # sur mission.payment_status : ce champ est réécrit sans condition
        # juste en dessous (compat arrière, cf. update_payment) et pourrait
        # déjà valoir "released" suite à un appel qui n'a jamais réellement
        # crédité le prestataire — s'appuyer dessus laisserait une vraie
        # libération se faire silencieusement ignorer. On vérifie aussi
        # qu'un paiement escrow a bien été enregistré avant de créditer.
        already_released = (
            db.query(BotTransaction)
            .filter(BotTransaction.mission_id == mission.mission_id, BotTransaction.type == "release")
            .first()
            is not None
        )
        already_refunded = (
            db.query(BotTransaction)
            .filter(BotTransaction.mission_id == mission.mission_id, BotTransaction.type == "refund")
            .first()
            is not None
        )
        was_paid = (
            db.query(BotTransaction)
            .filter(BotTransaction.mission_id == mission.mission_id, BotTransaction.type == "escrow_in")
            .first()
            is not None
        )
        releasing = payload.payment_status == "released" and was_paid and not already_released
        # Indépendant de `releasing` : un partage à l'amiable de litige libère
        # net_provider ET rembourse une partie au client dans le même appel.
        refunding = payload.refund_amount is not None and was_paid and not already_refunded
        mission.status = payload.status
        if payload.payment_status:
            mission.payment_status = payload.payment_status
        if payload.dispute_reason is not None:
            mission.dispute_reason = payload.dispute_reason
        if payload.net_provider is not None:
            # Partage à l'amiable : la part due au prestataire n'est plus le
            # net_provider posé au paiement escrow initial. Doit être appliqué
            # AVANT le crédit ci-dessous, qui lit mission.net_provider.
            mission.net_provider = payload.net_provider
        if releasing:
            db.add(
                BotTransaction(
                    mission_id=mission.mission_id,
                    quote_id=None,
                    type="release",
                    amount=mission.net_provider,
                    currency=mission.currency,
                    net_provider=mission.net_provider,
                    status="success",
                )
            )
            if mission.provider_telegram_id is not None:
                provider = db.get(BotProvider, mission.provider_telegram_id)
                if provider is not None:
                    if mission.currency == "USD":
                        provider.wallet_balance_usd += mission.net_provider
                    else:
                        provider.wallet_balance_cdf += mission.net_provider
        if refunding:
            db.add(
                BotTransaction(
                    mission_id=mission.mission_id,
                    quote_id=None,
                    type="refund",
                    amount=payload.refund_amount,
                    currency=mission.currency,
                    status="success",
                )
            )
            user = db.get(BotUser, mission.telegram_id)
            if user is not None:
                if mission.currency == "USD":
                    user.wallet_balance_usd += payload.refund_amount
                else:
                    user.wallet_balance_cdf += payload.refund_amount
        db.commit()
        db.refresh(mission)
        # crud._SUCCESS_STATUS/_FAILURE_STATUSES comptent completed/disputed/
        # cancelled dans le calcul de success_rate — recalculer sur ces trois
        # transitions, pas seulement "releasing", sinon un litige ouvert ou un
        # remboursement pur laisse le badge/success_rate du prestataire figé
        # sur une ancienne valeur (trouvaille backend-parity-auditor).
        if payload.status in ("completed", "disputed", "cancelled") and mission.provider_telegram_id is not None:
            crud._recompute_provider_stats(db, mission.provider_telegram_id)
            db.commit()
        return {"status": "ok", "mission": _mission_to_dict(mission)}


@router.post("/api/bot/payments")
def update_payment(payload: PaymentPayload):
    with SessionLocal() as db:
        mission = db.get(BotMission, payload.mission_id) if payload.mission_id is not None else None
        if mission is not None:
            # Idempotence basée sur l'existence d'une transaction "escrow_in",
            # pas sur mission.payment_status : même raison que dans
            # update_mission_status ci-dessus — payment_status peut déjà
            # valoir "paid_escrow" suite à un appel sans `amount` (compat
            # arrière ci-dessous) sans qu'aucune transaction n'ait jamais été
            # créée, ce qui ferait ignorer silencieusement le vrai paiement.
            already_paid = (
                db.query(BotTransaction)
                .filter(BotTransaction.mission_id == mission.mission_id, BotTransaction.type == "escrow_in")
                .first()
                is not None
            )
            paying = (
                payload.payment_status == "paid_escrow"
                and not already_paid
                and payload.amount is not None
            )
            mission.payment_status = payload.payment_status
            if paying:
                total_client = payload.total_client if payload.total_client is not None else payload.amount
                currency = payload.currency or mission.currency
                mission.commission_amount = payload.commission_amount or 0.0
                mission.tola_fee = payload.tola_fee
                mission.aggregator_fee = payload.aggregator_fee
                mission.total_client = total_client
                mission.net_provider = payload.net_provider or 0.0
                db.add(
                    BotTransaction(
                        mission_id=mission.mission_id,
                        # Pas le quote_id backend (séquence Postgres indépendante
                        # de l'id local envoyé par le bot) : mission_id suffit à
                        # tracer cette transaction, mieux vaut None qu'un FK
                        # pointant vers le mauvais devis.
                        quote_id=None,
                        type="escrow_in",
                        amount=total_client,
                        currency=currency,
                        commission_amount=payload.commission_amount or 0.0,
                        tola_fee=payload.tola_fee,
                        aggregator_fee=payload.aggregator_fee,
                        net_provider=payload.net_provider or 0.0,
                        status="success",
                        mobile_money_ref=payload.mobile_money_ref,
                        operator=payload.operator,
                    )
                )
                if payload.via_wallet:
                    user = db.get(BotUser, mission.telegram_id)
                    if user is not None:
                        if currency == "USD":
                            user.wallet_balance_usd -= total_client
                        else:
                            user.wallet_balance_cdf -= total_client
            db.commit()
            db.refresh(mission)
        return {
            "status": "ok",
            "payment_status": payload.payment_status,
            "mission": _mission_to_dict(mission) if mission is not None else None,
        }


@router.get("/api/profile/{telegram_id}")
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
            "client": _user_to_dict(user) if user else None,
            "provider": _provider_to_dict(provider) if provider else None,
            "client_missions": missions,
            "provider_missions": missions,
            "service_requests": [],
            "profile_type": "client" if user else "provider" if provider else "guest",
        }


app.include_router(router)
