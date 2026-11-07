import hmac
import os
from dataclasses import dataclass

from dotenv import load_dotenv
from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field

from backend.app import app_auth, app_sessions, crud, ledger, mobile_money, payment_gateway
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


# Canaux dont le backend sait résoudre l'identité d'un acteur. WhatsApp s'y
# ajoutera avec sa propre clé de service (docs/ARCHITECTURE_WHATSAPP.md).
ACTOR_CHANNELS = (ledger.TELEGRAM,)


@dataclass(frozen=True)
class Actor:
    """La personne pour qui le canal appelle, telle que le canal la connaît.
    Le canal ne dit jamais « j'agis pour le compte n° X » : le backend résout
    lui-même le compte (`_actor_account`)."""

    channel: str
    external_id: str

    @property
    def telegram_id(self) -> int:
        if self.channel != ledger.TELEGRAM:
            raise HTTPException(status_code=403, detail={"code": "telegram_only"})
        return int(self.external_id)


def current_actor(
    x_actor_channel: str | None = Header(default=None),
    x_actor_id: str | None = Header(default=None),
) -> Actor:
    """En-têtes `X-Actor-Channel` / `X-Actor-Id`, obligatoires sur toute
    action faite au nom d'une personne."""
    if not x_actor_channel or not x_actor_id:
        raise HTTPException(status_code=400, detail={"code": "actor_required"})
    if x_actor_channel not in ACTOR_CHANNELS:
        raise HTTPException(status_code=400, detail={"code": "unknown_channel"})
    if x_actor_channel == ledger.TELEGRAM and not x_actor_id.isdigit():
        raise HTTPException(status_code=400, detail={"code": "invalid_actor"})
    return Actor(channel=x_actor_channel, external_id=x_actor_id)


def _actor_account(
    db, actor: Actor, *, create: bool = False, missing: str = "account_not_found", http_status: int = 404
) -> int:
    """Compte Nexis de l'acteur : le seul endroit où l'API traduit une identité
    de canal en compte. Les règles d'argent ne comparent ensuite que des
    comptes. `create` : le canal garantit l'identifiant de l'expéditeur (c'est
    lui qui écrit), son compte peut donc naître de sa première action."""
    account_id = ledger.account_id_for(db, actor.channel, actor.external_id, create=create)
    if account_id is None:
        raise ledger.MoneyError(missing, http_status)
    return account_id


class BotUserPayload(BaseModel):
    telegram_id: int
    first_name: str | None = None
    phone_number: str | None = None
    language: str = "fr"
    # Vrai seulement si le numéro vient du bouton « Partager mon numéro »
    # (contact de l'expéditeur, vérifié par le bot) : il est alors enregistré
    # comme numéro prouvé du compte.
    phone_verified: bool = False


class MissionMediaPayload(BaseModel):
    kind: str
    id: str = Field(min_length=1, max_length=255)


class MissionDestinationPayload(BaseModel):
    """Lieu exact : point et repère. Le texte brut peut être plus long que le
    repère gardé (espaces normalisés ensuite par crud.checked_destination)."""

    latitude: float
    longitude: float
    landmark: str = Field(max_length=crud.MAX_LANDMARK_LENGTH * 2)


class MissionCreatePayload(BaseModel):
    """Demande de création d'une mission. Le client est l'acteur (en-têtes),
    le numéro est attribué par le backend. `creation_key` : choisie par le
    canal, la même pour chaque nouvel essai de la même demande."""

    creation_key: str = Field(min_length=1, max_length=64)
    service: str = Field(min_length=1, max_length=255)
    commune: str = Field(min_length=1, max_length=255)
    currency: str = "USD"
    description: str = Field(default="", max_length=4000)
    urgent: bool = False
    media: list[MissionMediaPayload] = Field(default_factory=list, max_length=crud.MAX_MISSION_MEDIA)
    # Prestataires à prévenir (choisis par le canal Telegram, seul canal des
    # prestataires) ; le backend écarte le client lui-même.
    alert_provider_telegram_ids: list[int] = Field(default_factory=list, max_length=crud.MAX_ALERTED_PROVIDERS)
    # Lieu exact (obligatoire) : point partagé par le client et repère écrit.
    # Vérifié par crud.checked_destination (zone servie, repère non vide).
    destination: MissionDestinationPayload


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
    phone_verified: bool = False


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
    amount: float
    currency: str = "USD"
    delay_hours: int
    message: str = ""


class FundPayload(BaseModel):
    """Payer = « ce devis de cette mission ». Montant, devise et prestataire
    sont ceux du devis accepté enregistré par le backend."""

    method: str
    quote_id: int


class PaymentIntentPayload(BaseModel):
    quote_id: int
    phone: str
    operator: str


class PayoutPayload(BaseModel):
    amount: float
    currency: str
    phone: str
    operator: str


class PayoutDecisionPayload(BaseModel):
    reason: str = ""


class MismatchDecisionPayload(BaseModel):
    decision: str


class DisputeOpenPayload(BaseModel):
    reason: str


class DisputeResolvePayload(BaseModel):
    decision: str
    provider_percentage: float | None = None


class ReviewCreatePayload(BaseModel):
    mission_id: int
    rating: int
    comment: str | None = None


class ProviderRankPayload(BaseModel):
    telegram_ids: list[int] = Field(max_length=100)


class ServiceRequestPayload(BaseModel):
    service_name: str
    description: str = ""


class ServiceRequestStatusPayload(BaseModel):
    status: str
    admin_note: str = ""


def _wallet_fields(db, telegram_id: int) -> dict:
    # Calculés depuis le registre, seule source de vérité (backend/app/ledger.py).
    # Un seul wallet par personne, qu'elle soit cliente, prestataire ou les deux.
    account_id = ledger.account_id_for(db, ledger.TELEGRAM, telegram_id)
    balances = ledger.wallet_balances(db, account_id)
    return {
        "account_id": account_id,
        "wallet_balance_usd": float(balances["USD"]),
        "wallet_balance_cdf": float(balances["CDF"]),
    }


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
        "client_account_id": mission.client_account_id,
        "provider_account_id": mission.provider_account_id,
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


def _quote_to_dict(quote: BotQuote, db=None) -> dict:
    provider = db.get(BotProvider, quote.provider_telegram_id) if db is not None else None
    return {
        "provider_name": provider.full_name if provider is not None else None,
        "id": quote.id,
        "mission_id": quote.mission_id,
        "provider_telegram_id": quote.provider_telegram_id,
        "provider_account_id": quote.provider_account_id,
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
        "client_account_id": review.client_account_id,
        "provider_account_id": review.provider_account_id,
        "rating": review.rating,
        "comment": review.comment,
        "created_at": review.created_at.isoformat() if review.created_at else None,
    }


def _service_request_to_dict(req: BotServiceRequest, provider: BotProvider | None = None) -> dict:
    data = {
        "id": req.id,
        "provider_telegram_id": req.provider_telegram_id,
        "provider_account_id": req.provider_account_id,
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
        user = crud.upsert_user(
            db, payload.telegram_id, payload.first_name, payload.phone_number, payload.language, payload.phone_verified
        )
        return {"status": "ok", "user": _user_to_dict(user, db)}


class AppLoginTelegramContactPayload(BaseModel):
    start_token: str = Field(min_length=1, max_length=64)
    phone: str = Field(min_length=1, max_length=32)


@router.post("/api/bot/app-login/telegram-contact")
def app_login_telegram_contact(payload: AppLoginTelegramContactPayload, actor: Actor = Depends(current_actor)):
    """Connexion à l'application par Telegram : la personne a ouvert le bot
    par le lien de l'app et partagé son propre contact (vérifié par le bot).
    Rend le code que le bot lui affiche. Voir `app_auth`."""
    with SessionLocal() as db:
        try:
            issued = app_auth.issue_code_for_telegram_contact(
                db, start_token=payload.start_token, telegram_id=actor.telegram_id, contact_phone=payload.phone
            )
        except app_auth.AuthError as error:
            db.rollback()
            raise HTTPException(status_code=error.http_status, detail={"code": error.code})
        return {"status": "ok", "code": issued.code, "expires_at": issued.expires_at.isoformat()}


@router.post("/api/bot/missions")
def create_bot_mission(payload: MissionCreatePayload, actor: Actor = Depends(current_actor)):
    with SessionLocal() as db:
        try:
            mission, created = crud.create_mission(
                db,
                channel=actor.channel,
                client_external_id=actor.external_id,
                creation_key=payload.creation_key,
                service=payload.service,
                commune=payload.commune,
                currency=payload.currency,
                description=payload.description,
                urgent=payload.urgent,
                media=[(item.kind, item.id) for item in payload.media],
                alert_provider_telegram_ids=payload.alert_provider_telegram_ids,
                destination_latitude=payload.destination.latitude,
                destination_longitude=payload.destination.longitude,
                destination_landmark=payload.destination.landmark,
            )
        except crud.MissionRefused as refusal:
            db.rollback()
            raise HTTPException(status_code=refusal.http_status, detail={"code": refusal.code}) from refusal
        return {"status": "ok", "created": created, **_mission_view(db, mission, "client")}


def _mission_view(db, mission: BotMission, role: str) -> dict:
    """Mission telle qu'une personne autorisée la lit : état, argent, médias
    et, pour le client, les prestataires prévenus."""
    view = {
        "mission": {
            **_mission_to_dict(mission),
            "media": [
                {"channel": item.channel, "kind": item.kind, "id": item.external_id}
                for item in crud.mission_media(db, mission.mission_id)
            ],
        },
        "money": ledger.mission_money_state(db, mission.mission_id),
        "viewer_role": role,
    }
    if role in ("client", "admin"):
        view["alerted_provider_telegram_ids"] = [
            ledger.telegram_id_of(db, account_id) for account_id in crud.alerted_provider_account_ids(db, mission.mission_id)
        ]
    return view


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
            phone_verified=payload.phone_verified,
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
def create_quote(payload: QuoteCreatePayload, actor: Actor = Depends(current_actor)):
    with SessionLocal() as db:
        try:
            quote = crud.create_quote(
                db,
                mission_id=payload.mission_id,
                provider_telegram_id=actor.telegram_id,
                amount=payload.amount,
                currency=payload.currency,
                delay_hours=payload.delay_hours,
                message=payload.message,
            )
        except crud.MissionRefused as refusal:
            raise HTTPException(status_code=refusal.http_status, detail={"code": refusal.code}) from refusal
        except ValueError as exc:
            raise HTTPException(status_code=409, detail={"code": str(exc)}) from exc
        if quote is None:
            raise HTTPException(status_code=404, detail="mission_not_found")
        return {"status": "ok", "quote": _quote_to_dict(quote, db), "mission": _mission_to_dict(db.get(BotMission, quote.mission_id))}


@router.post("/api/bot/reviews")
def create_review(payload: ReviewCreatePayload, actor: Actor = Depends(current_actor)):
    with SessionLocal() as db:
        try:
            review = crud.create_review(
                db,
                mission_id=payload.mission_id,
                client_telegram_id=actor.telegram_id,
                rating=payload.rating,
                comment=payload.comment,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"status": "ok", "review": _review_to_dict(review)}


def _quote_decision(quote_id: int, actor: Actor, decide) -> dict:
    with SessionLocal() as db:
        client_account_id = ledger.account_id_for(db, actor.channel, actor.external_id)
        if client_account_id is None:
            raise HTTPException(status_code=403, detail={"code": "not_mission_client"})
        try:
            quote = decide(db, quote_id, client_account_id)
        except ValueError as exc:
            status = 403 if str(exc) == "not_mission_client" else 409
            raise HTTPException(status_code=status, detail={"code": str(exc)}) from exc
        if quote is None:
            raise HTTPException(status_code=404, detail="quote_not_found")
        return {"status": "ok", "quote": _quote_to_dict(quote, db), "mission": _mission_to_dict(db.get(BotMission, quote.mission_id))}


@router.get("/api/bot/quotes/{quote_id}")
def get_quote(quote_id: int, actor: Actor = Depends(current_actor)):
    """Lisible par le client de la mission et par l'auteur du devis (et
    l'admin) ; pour tout autre, le devis n'existe pas."""
    with SessionLocal() as db:
        quote = db.get(BotQuote, quote_id)
        if quote is not None and not _is_admin(actor):
            account_id = ledger.account_id_for(db, actor.channel, actor.external_id)
            mission = db.get(BotMission, quote.mission_id)
            if account_id is None or account_id not in (mission.client_account_id, quote.provider_account_id):
                quote = None
        if quote is None:
            raise HTTPException(status_code=404, detail={"code": "quote_not_found"})
        return {"status": "ok", "quote": _quote_to_dict(quote, db), "mission": _mission_to_dict(db.get(BotMission, quote.mission_id))}


@router.post("/api/bot/quotes/{quote_id}/accept")
def accept_quote(quote_id: int, actor: Actor = Depends(current_actor)):
    return _quote_decision(quote_id, actor, crud.accept_quote)


@router.post("/api/bot/quotes/{quote_id}/reject")
def reject_quote(quote_id: int, actor: Actor = Depends(current_actor)):
    return _quote_decision(quote_id, actor, crud.reject_quote)


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
def fund_mission(mission_id: int, payload: FundPayload, actor: Actor = Depends(current_actor)):
    # Seul le wallet paie directement : un paiement Mobile Money n'existe que
    # confirmé par l'agrégateur (/payment-intents, CONCEPTION_MOBILE_MONEY.md).
    if payload.method != "wallet":
        raise HTTPException(status_code=400, detail={"code": "use_payment_intent"})
    return _money_call(
        lambda db: ledger.fund_mission(
            db,
            mission_id,
            method=payload.method,
            client_account_id=_actor_account(db, actor, missing="mission_not_found"),
            quote_id=payload.quote_id,
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
        "received_amount": str(intent.received_amount) if intent.received_amount is not None else None,
        "received_currency": intent.received_currency,
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
def create_payment_intent(mission_id: int, payload: PaymentIntentPayload, actor: Actor = Depends(current_actor)):
    with SessionLocal() as db:
        try:
            intent = mobile_money.create_intent(
                db,
                mission_id,
                phone=payload.phone,
                operator=payload.operator,
                client_account_id=_actor_account(db, actor, missing="mission_not_found"),
                quote_id=payload.quote_id,
            )
        except ledger.MoneyError as error:
            raise _money_refusal(db, error) from error
        return _intent_response(db, intent)


@router.post("/api/bot/payment-intents/{intent_id}/refresh")
def refresh_payment_intent(intent_id: int):
    with SessionLocal() as db:
        from backend.app.tasks import refresh_and_notify_intent

        try:
            # Même chemin que le webhook et la vérification de secours : celui
            # qui fait changer le statut prévient client et prestataire.
            refresh_and_notify_intent(db, intent_id)
        except ledger.MoneyError as error:
            raise _money_refusal(db, error) from error
        return _intent_response(db, db.get(PaymentIntent, intent_id))


def _payout_call(operation):
    with SessionLocal() as db:
        try:
            payout = operation(db)
        except ledger.MoneyError as error:
            db.rollback()
            raise HTTPException(status_code=error.http_status, detail={"code": error.code}) from error
        return {"status": "ok", "payout": _payout_to_dict(payout)}


@router.post("/api/bot/payouts")
def request_payout(payload: PayoutPayload, actor: Actor = Depends(current_actor)):
    return _payout_call(
        lambda db: mobile_money.request_payout(
            db,
            # Sans compte, il n'y a pas de solde à retirer.
            account_id=_actor_account(db, actor, missing="insufficient_balance", http_status=409),
            amount=payload.amount,
            currency=payload.currency,
            phone=payload.phone,
            operator=payload.operator,
        )
    )


@router.get("/api/bot/payouts")
def list_payouts(status: str = "awaiting_approval", limit: int = 20, actor: Actor = Depends(current_actor)):
    # Téléphones des prestataires : réservé à l'admin.
    _require_admin(actor)
    with SessionLocal() as db:
        payouts = db.query(Payout).filter(Payout.status == status).order_by(Payout.id).limit(min(limit, 50)).all()
        return {"status": "ok", "payouts": [_payout_to_dict(payout) for payout in payouts]}


def _require_admin(actor: Actor) -> int:
    """Décisions d'argent réservées à l'admin configuré, qui agit depuis
    Telegram. Le bot le vérifie déjà ; le backend le revérifie pour qu'une
    erreur côté bot ne suffise jamais à valider un retrait ou trancher un
    litige. Sans ADMIN_TELEGRAM_ID, personne n'est admin (même règle que le
    bot). Renvoie l'identifiant Telegram de l'admin, pour l'audit."""
    if not _is_admin(actor):
        raise HTTPException(status_code=403, detail={"code": "not_admin"})
    return actor.telegram_id


def _is_admin(actor: Actor) -> bool:
    configured = os.getenv("ADMIN_TELEGRAM_ID", "").strip()
    return actor.channel == ledger.TELEGRAM and bool(configured) and hmac.compare_digest(configured, actor.external_id)


class AppDevicesRevokePayload(BaseModel):
    telegram_id: int


@router.post("/api/bot/admin/app-devices/revoke")
def admin_revoke_app_devices(payload: AppDevicesRevokePayload, actor: Actor = Depends(current_actor)):
    """L'admin coupe tous les téléphones de l'application d'une personne,
    désignée par son identifiant Telegram (téléphone volé, compte suspect).
    Elle devra se reconnecter par code ; son argent ne bouge pas."""
    _require_admin(actor)
    with SessionLocal() as db:
        account_id = ledger.account_id_for(db, ledger.TELEGRAM, payload.telegram_id)
        if account_id is None:
            raise HTTPException(status_code=404, detail={"code": "account_not_found"})
        revoked = app_sessions.revoke_all_devices(db, account_id)
        return {"status": "ok", "revoked": revoked}


@router.post("/api/bot/payouts/{payout_id}/approve")
def approve_payout(payout_id: int, payload: PayoutDecisionPayload, actor: Actor = Depends(current_actor)):
    admin_telegram_id = _require_admin(actor)
    return _payout_call(lambda db: mobile_money.approve_payout(db, payout_id, admin_telegram_id))


@router.post("/api/bot/payouts/{payout_id}/reject")
def reject_payout(payout_id: int, payload: PayoutDecisionPayload, actor: Actor = Depends(current_actor)):
    admin_telegram_id = _require_admin(actor)
    return _payout_call(lambda db: mobile_money.reject_payout(db, payout_id, admin_telegram_id, payload.reason))


@router.get("/api/bot/payment-intents/mismatches")
def list_payment_mismatches(limit: int = 20, actor: Actor = Depends(current_actor)):
    # Téléphone et identifiant du client : réservé à l'admin.
    _require_admin(actor)
    with SessionLocal() as db:
        intents = mobile_money.list_mismatches(db, limit)
        return {
            "status": "ok",
            "intents": [
                {
                    **_intent_to_dict(intent),
                    "phone": intent.phone,
                    "client_account_id": intent.account_id,
                    "client_telegram_id": ledger.telegram_id_of(db, intent.account_id),
                }
                for intent in intents
            ],
        }


def _notify_mismatch_resolved(intent_id: int) -> None:
    from backend.app.tasks import notify_mismatch_resolved

    with SessionLocal() as db:
        notify_mismatch_resolved(db, db.get(PaymentIntent, intent_id))


@router.post("/api/bot/payment-intents/{intent_id}/resolve-mismatch")
def resolve_payment_mismatch(
    intent_id: int, payload: MismatchDecisionPayload, background_tasks: BackgroundTasks, actor: Actor = Depends(current_actor)
):
    admin_telegram_id = _require_admin(actor)
    with SessionLocal() as db:
        try:
            intent, resolved_now = mobile_money.resolve_mismatch(db, intent_id, admin_telegram_id, payload.decision)
        except ledger.MoneyError as error:
            raise HTTPException(status_code=error.http_status, detail={"code": error.code}) from error
        if resolved_now:
            # Après la réponse : l'admin voit le résultat sans attendre Telegram.
            background_tasks.add_task(_notify_mismatch_resolved, intent.id)
        return _intent_response(db, intent)


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
def start_mission(mission_id: int, actor: Actor = Depends(current_actor)):
    return _money_call(
        lambda db: ledger.start_mission(db, mission_id, _actor_account(db, actor, missing="not_mission_provider", http_status=403))
    )


@router.post("/api/bot/missions/{mission_id}/finish")
def finish_mission(mission_id: int, actor: Actor = Depends(current_actor)):
    return _money_call(
        lambda db: ledger.finish_mission(db, mission_id, _actor_account(db, actor, missing="not_mission_provider", http_status=403))
    )


@router.post("/api/bot/missions/{mission_id}/confirm")
def confirm_mission(mission_id: int, actor: Actor = Depends(current_actor)):
    return _money_call(
        lambda db: ledger.confirm_completion(db, mission_id, _actor_account(db, actor, missing="not_mission_client", http_status=403))
    )


@router.post("/api/bot/missions/{mission_id}/dispute")
def open_dispute(mission_id: int, payload: DisputeOpenPayload, actor: Actor = Depends(current_actor)):
    return _money_call(
        lambda db: ledger.open_dispute(
            db, mission_id, _actor_account(db, actor, missing="not_mission_client", http_status=403), payload.reason
        )
    )


@router.post("/api/bot/missions/{mission_id}/dispute/resolve")
def resolve_dispute(mission_id: int, payload: DisputeResolvePayload, actor: Actor = Depends(current_actor)):
    admin_telegram_id = _require_admin(actor)
    return _money_call(
        lambda db: ledger.resolve_dispute(
            db,
            mission_id,
            decision=payload.decision,
            admin_telegram_id=admin_telegram_id,
            provider_percentage=payload.provider_percentage,
        )
    )


@router.get("/api/bot/missions/{mission_id}")
def get_mission(mission_id: int, actor: Actor = Depends(current_actor)):
    """Lisible par le client, le prestataire concerné, un prestataire prévenu
    et l'admin. Pour tout autre, la mission n'existe pas (même réponse qu'un
    numéro inconnu : on ne confirme pas son existence)."""
    with SessionLocal() as db:
        mission = db.get(BotMission, mission_id)
        role = None
        if mission is not None:
            if _is_admin(actor):
                role = "admin"
            else:
                account_id = ledger.account_id_for(db, actor.channel, actor.external_id)
                role = crud.mission_viewer_role(db, mission, account_id)
        if role is None:
            raise HTTPException(status_code=404, detail={"code": "mission_not_found"})
        return {"status": "ok", **_mission_view(db, mission, role)}


@router.get("/api/bot/missions/{mission_id}/destination")
def get_mission_destination(mission_id: int, actor: Actor = Depends(current_actor)):
    """Lieu exact de la mission, à part du reste de la mission : le client et
    l'admin le lisent toujours, le prestataire choisi seulement une fois la
    mission payée et tant qu'il doit s'y rendre ou y travailler
    (`crud.destination_access`). Pour qui ne lit pas la mission : 404, comme
    un numéro inconnu ; pour qui la lit sans avoir encore droit au lieu :
    `destination_not_available` (403)."""
    with SessionLocal() as db:
        mission = db.get(BotMission, mission_id)
        access = "hidden"
        if mission is not None:
            account_id = None if _is_admin(actor) else ledger.account_id_for(db, actor.channel, actor.external_id)
            access = crud.destination_access(db, mission, account_id, is_admin=_is_admin(actor))
        if access == "hidden":
            raise HTTPException(status_code=404, detail={"code": "mission_not_found"})
        if access != "granted":
            raise HTTPException(status_code=403, detail={"code": "destination_not_available"})
        if mission.destination_latitude is None:
            # Mission créée avant le lieu exact : seule la commune est connue.
            raise HTTPException(status_code=404, detail={"code": "destination_unknown"})
        return {
            "status": "ok",
            "mission_id": mission.mission_id,
            "destination": {
                "latitude": mission.destination_latitude,
                "longitude": mission.destination_longitude,
                "landmark": mission.destination_landmark,
            },
        }


@router.get("/api/me/missions")
def my_missions(role: str = "client", limit: int = 20, actor: Actor = Depends(current_actor)):
    """Missions de l'acteur : celles qu'il a commandées (`client`) ou qui lui
    sont confiées (`provider`)."""
    if role not in ("client", "provider"):
        raise HTTPException(status_code=400, detail={"code": "invalid_role"})
    limit = max(1, min(limit, 50))
    with SessionLocal() as db:
        account_id = ledger.account_id_for(db, actor.channel, actor.external_id)
        if account_id is None:
            return {"status": "ok", "missions": []}
        missions = (crud.client_missions if role == "client" else crud.provider_missions)(db, account_id, limit)
        return {"status": "ok", "missions": [_listed_mission(db, mission) for mission in missions]}


def _listed_mission(db, mission: BotMission) -> dict:
    """Mission d'une liste, avec les noms affichés par les canaux."""
    client = db.get(BotUser, mission.telegram_id)
    provider = db.get(BotProvider, mission.provider_telegram_id) if mission.provider_telegram_id else None
    return {
        **_mission_to_dict(mission),
        "client_name": client.first_name if client is not None else None,
        "provider_name": provider.full_name if provider is not None else None,
    }


@router.get("/api/admin/missions")
def admin_list_missions(status: str | None = None, limit: int = 10, actor: Actor = Depends(current_actor)):
    _require_admin(actor)
    with SessionLocal() as db:
        missions = crud.admin_missions(db, status=status, limit=max(1, min(limit, 50)))
        return {"status": "ok", "missions": [_listed_mission(db, mission) for mission in missions]}


@router.get("/api/admin/stats")
def admin_stats(actor: Actor = Depends(current_actor)):
    _require_admin(actor)
    with SessionLocal() as db:
        return {"status": "ok", "stats": crud.mission_stats(db)}


@router.get("/api/me/wallet")
def get_my_wallet(actor: Actor = Depends(current_actor)):
    """Wallet de l'acteur, et de lui seul : un canal ne lit jamais le solde
    d'une autre personne par cette route."""
    with SessionLocal() as db:
        account_id = ledger.account_id_for(db, actor.channel, actor.external_id)
        balances = ledger.wallet_balances(db, account_id)
        return {
            "status": "ok",
            "wallet": {
                "account_id": account_id,
                "wallet_balance_usd": float(balances["USD"]),
                "wallet_balance_cdf": float(balances["CDF"]),
            },
        }


@router.post("/api/bot/service-requests")
def create_service_request(payload: ServiceRequestPayload, actor: Actor = Depends(current_actor)):
    with SessionLocal() as db:
        try:
            req = crud.create_service_request(
                db,
                provider_telegram_id=actor.telegram_id,
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
            # Nom du client, affiché au prestataire.
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
