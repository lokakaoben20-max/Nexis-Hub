import hmac
import os
import re
from contextlib import asynccontextmanager
from dataclasses import dataclass

from dotenv import load_dotenv
from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask

import nexis_config
import nexis_logs
from backend.app import (
    app_auth,
    app_sessions,
    crud,
    idempotency,
    ledger,
    mobile_money,
    payment_gateway,
    presence,
    profils,
    sante,
    service_keys,
)
from backend.app.database import SessionLocal
from backend.app.models import BotMission, BotQuote, BotReview, PaymentIntent, Payout, ProviderProfile, ProviderServiceRequest

load_dotenv()


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    # Hors développement, une configuration incomplète empêche le démarrage.
    nexis_config.verifier("backend")
    nexis_logs.configurer("backend")
    # Refus de démarrer avec des clés de service douteuses (ancienne clé
    # unique encore présente, clé Telegram absente, clés trop courtes ou
    # partagées entre deux canaux) : voir backend/app/service_keys.py.
    service_keys.check_configuration()
    check_route_policies()
    yield


# Le schéma est géré uniquement par Alembic (`alembic upgrade head` avant tout
# démarrage). Plus de `create_all` au démarrage : il créait des tables hors
# migrations, et la migration suivante échouait sur une table déjà là.
app = FastAPI(title="Nexis Hub V5 Backend", lifespan=_lifespan)


# --- Canaux autorisés par route ----------------------------------------------
# Une route n'est ouverte qu'au bot Telegram (et à la Mini App, même canal)
# tant qu'elle n'est pas explicitement ouverte à un autre canal par
# `@open_to(...)`. Une route nouvelle est donc fermée à WhatsApp par défaut.
# `@provider_action` marque une action de prestataire : jamais ouverte à
# WhatsApp, quoi qu'on écrive dans `open_to` (vérifié ici à l'import, et par
# backend/tests/test_whatsapp_channel.py qui énumère toutes les routes).

DEFAULT_CHANNELS = frozenset({ledger.TELEGRAM})
PROVIDER_CHANNELS = frozenset({ledger.TELEGRAM})
_CHANNELS_ATTR = "__nexis_channels__"
_PROVIDER_ATTR = "__nexis_provider_action__"


def open_to(*channels: str):
    """Ouvre une route à ces canaux (en plus de rien : la liste est complète)."""
    allowed = frozenset(channels)
    unknown = allowed - set(service_keys.KEY_VARIABLES)
    if unknown:
        raise RuntimeError(f"Canal inconnu : {sorted(unknown)}")

    def decorate(endpoint):
        if getattr(endpoint, _PROVIDER_ATTR, False) and not allowed <= PROVIDER_CHANNELS:
            raise RuntimeError(f"{endpoint.__name__} : une action de prestataire n'est jamais ouverte à WhatsApp")
        setattr(endpoint, _CHANNELS_ATTR, allowed)
        return endpoint

    return decorate


def provider_action(endpoint):
    """Action de prestataire : canaux des prestataires seulement (Telegram,
    Mini App, plus tard l'app). Refus explicite `provider_channel_forbidden`
    pour tout autre canal."""
    if not getattr(endpoint, _CHANNELS_ATTR, DEFAULT_CHANNELS) <= PROVIDER_CHANNELS:
        raise RuntimeError(f"{endpoint.__name__} : une action de prestataire n'est jamais ouverte à WhatsApp")
    setattr(endpoint, _PROVIDER_ATTR, True)
    return endpoint


def route_channels(endpoint) -> frozenset:
    return getattr(endpoint, _CHANNELS_ATTR, DEFAULT_CHANNELS)


def is_provider_action(endpoint) -> bool:
    return getattr(endpoint, _PROVIDER_ATTR, False)


_IDEMPOTENT_ATTR = "__nexis_idempotent__"
WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def idempotent(endpoint):
    """Écriture qui passe par `_run_idempotent` : la clé `Idempotency-Key` est
    enregistrée dans la transaction de l'action (backend/app/idempotency.py).
    Obligatoire sur toute écriture ouverte à un autre canal que Telegram."""
    setattr(endpoint, _IDEMPOTENT_ATTR, True)
    return endpoint


def is_idempotent(endpoint) -> bool:
    return getattr(endpoint, _IDEMPOTENT_ATTR, False)


def check_route_policies() -> None:
    """Refus de démarrer si une écriture est ouverte à WhatsApp sans
    idempotence : un message reçu deux fois agirait deux fois."""
    for route in router.routes:
        methods = set(getattr(route, "methods", ()) or ()) & WRITE_METHODS
        channels = route_channels(getattr(route, "endpoint", None))
        if methods and channels - {ledger.TELEGRAM} and not is_idempotent(route.endpoint):
            raise RuntimeError(f"{sorted(methods)} {route.path} : écriture ouverte à {sorted(channels)} sans @idempotent")


def verify_service_key(request: Request, x_api_key: str | None = Header(default=None)) -> str:
    """Authentifie le canal appelant sur toutes les routes /api/* et vérifie
    que la route lui est ouverte. Rend le canal, que `current_actor` exige
    identique à celui déclaré pour l'acteur.

    Ce backend n'authentifie pas l'utilisateur final : chaque canal (bot
    Telegram et Mini App, service WhatsApp) a sa propre clé, envoyée dans
    `X-API-Key`. Voir le skill `securite-backend` avant d'exposer ce service
    au-delà de 127.0.0.1."""
    try:
        service_keys.check_configuration()
    except service_keys.ConfigurationError as error:
        raise HTTPException(status_code=500, detail="Clés de service du backend mal configurées") from error
    channel = service_keys.channel_for_key(x_api_key)
    if channel is None:
        raise HTTPException(status_code=401, detail="Clé API invalide ou manquante")
    endpoint = request.scope.get("endpoint")
    if channel not in route_channels(endpoint):
        code = "provider_channel_forbidden" if is_provider_action(endpoint) else "channel_forbidden"
        raise HTTPException(status_code=403, detail={"code": code})
    return channel


# Toutes les routes /api/* passent par ce router protégé. /health reste sur
# `app` directement, sans authentification, pour rester utilisable par un
# outil de supervision externe.
router = APIRouter(dependencies=[Depends(verify_service_key)])


# Canaux dont le backend sait résoudre l'identité d'un acteur déclaré par
# en-têtes. Jamais `app` : l'acteur de l'application ne naît que d'une session
# vérifiée.
ACTOR_CHANNELS = (ledger.TELEGRAM, ledger.WHATSAPP)
# BSUID de Meta : code pays de 2 lettres, un point, jusqu'à 128 caractères
# alphanumériques. Tout autre format est refusé.
_WHATSAPP_ACTOR = re.compile(r"[A-Z]{2}\.[A-Za-z0-9]{1,128}")


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
    service_channel: str = Depends(verify_service_key),
    x_actor_channel: str | None = Header(default=None),
    x_actor_id: str | None = Header(default=None),
) -> Actor:
    """En-têtes `X-Actor-Channel` / `X-Actor-Id`, obligatoires sur toute
    action faite au nom d'une personne. Le canal déclaré doit être celui de
    la clé : un canal n'agit jamais au nom d'une personne d'un autre canal."""
    if not x_actor_channel or not x_actor_id:
        raise HTTPException(status_code=400, detail={"code": "actor_required"})
    if x_actor_channel not in ACTOR_CHANNELS:
        raise HTTPException(status_code=400, detail={"code": "unknown_channel"})
    if x_actor_channel != service_channel:
        raise HTTPException(status_code=403, detail={"code": "actor_channel_mismatch"})
    if x_actor_channel == ledger.TELEGRAM and not x_actor_id.isdigit():
        raise HTTPException(status_code=400, detail={"code": "invalid_actor"})
    if x_actor_channel == ledger.WHATSAPP and not _WHATSAPP_ACTOR.fullmatch(x_actor_id):
        raise HTTPException(status_code=400, detail={"code": "invalid_actor"})
    return Actor(channel=x_actor_channel, external_id=x_actor_id)


def _run_idempotent(
    request: Request,
    response: Response,
    actor: "Actor",
    key: str | None,
    body: dict,
    action,
) -> dict:
    """Exécute une écriture une seule fois pour (canal, clé) et valide la
    transaction (action + clé ensemble). Clé obligatoire pour WhatsApp,
    facultative pour Telegram. Une réponse rejouée porte
    `Idempotent-Replayed: true`. `action(db)` écrit sans valider et rend le
    corps de la réponse ; une `HTTPException` qu'elle lève annule tout."""
    try:
        key = idempotency.check_key(key, required=actor.channel != ledger.TELEGRAM)
    except idempotency.IdempotencyError as error:
        raise HTTPException(status_code=error.http_status, detail={"code": error.code}) from error
    with SessionLocal() as db:
        if key is None:
            result = action(db)
            db.commit()
            return result
        request_fingerprint = idempotency.fingerprint(
            route=f"{request.method} {request.scope['route'].path}",
            channel=actor.channel,
            actor_id=actor.external_id,
            path_params=dict(request.path_params),
            body=body,
        )
        try:
            outcome = idempotency.run(
                db, channel=actor.channel, key=key, request_fingerprint=request_fingerprint, action=lambda: action(db)
            )
        except idempotency.IdempotencyError as error:
            db.rollback()
            raise HTTPException(status_code=error.http_status, detail={"code": error.code}) from error
        except BaseException:
            db.rollback()
            raise
        if outcome.replayed:
            response.headers["Idempotent-Replayed"] = "true"
        return outcome.body


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


class DisputeDecidePayload(BaseModel):
    decision: str
    provider_percentage: float | None = None


class DisputeContestPayload(BaseModel):
    reason: str


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


def _wallet_fields(db, account_id: int | None) -> dict:
    # Calculés depuis le registre, seule source de vérité (backend/app/ledger.py).
    # Un seul wallet par personne, qu'elle soit cliente, prestataire ou les deux.
    balances = ledger.wallet_balances(db, account_id)
    return {
        "account_id": account_id,
        "wallet_balance_usd": float(balances["USD"]),
        "wallet_balance_cdf": float(balances["CDF"]),
    }


def _user_to_dict(db, account_id: int, client) -> dict:
    """Profil client dans la forme que le bot Telegram lit aujourd'hui."""
    telegram_id = ledger.telegram_id_of(db, account_id)
    return {
        "telegram_id": telegram_id,
        "account_id": account_id,
        "first_name": client.first_name,
        "phone_number": client.phone_number,
        "language": profils.language_of(db, account_id),
        **_wallet_fields(db, account_id),
        "total_missions": db.query(BotMission).filter(BotMission.client_account_id == account_id).count(),
    }


def _provider_to_dict(db, provider: ProviderProfile) -> dict:
    """Profil prestataire dans la forme que le bot Telegram lit aujourd'hui."""
    telegram_id = ledger.telegram_id_of(db, provider.account_id)
    return {
        "telegram_id": telegram_id,
        "account_id": provider.account_id,
        "full_name": provider.full_name,
        "phone_number": provider.phone_number,
        "services": profils.provider_services(db, provider.account_id),
        "communes": profils.provider_communes(db, provider.account_id),
        "language": profils.language_of(db, provider.account_id),
        "status": provider.status,
        "module": profils.provider_module(db, provider.account_id),
        "badge": provider.badge,
        "total_missions": provider.total_missions,
        "success_rate": provider.success_rate,
        "average_rating": provider.average_rating,
        "total_reviews": provider.total_reviews,
        "is_verified": profils.is_verified(provider),
        "is_suspended": provider.is_suspended,
        "consecutive_ignored": provider.consecutive_ignored,
        **_wallet_fields(db, provider.account_id),
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
        "release_after": mission.release_after.isoformat() if mission.release_after else None,
    }


def _quote_to_dict(quote: BotQuote, db=None) -> dict:
    provider = None
    if db is not None:
        provider_account_id = quote.provider_account_id or ledger.account_id_for(db, ledger.TELEGRAM, quote.provider_telegram_id)
        provider = profils.provider_profile(db, provider_account_id)
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


def _service_request_to_dict(db, req: ProviderServiceRequest, provider: ProviderProfile | None = None) -> dict:
    data = {
        "id": req.id,
        "provider_telegram_id": ledger.telegram_id_of(db, req.provider_account_id),
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


@app.get("/health/live")
def health_live():
    return {"status": "ok"}


@app.get("/health/ready")
def health_ready():
    with SessionLocal() as db:
        problemes = sante.problemes_base(db)
    if problemes:
        return JSONResponse({"status": "indisponible", "problemes": problemes}, status_code=503)
    return {"status": "ok"}


# --- Profils : routes du bot Telegram d'aujourd'hui ---------------------------
# Le bot les appelle avec l'identifiant Telegram dans l'adresse et la clé de
# service. Elles appliquent les règles de `profils` (statuts, catalogue) sur
# les profils rangés par compte Nexis, et rendent la réponse que le bot lit.
# Chantier « profils au backend » : remplacées par des routes au nom de
# l'acteur (étape 2), supprimées à la bascule du bot et de la Mini App
# (étape 3).


def _profile_refused(db, refusal: profils.ProfileRefused) -> HTTPException:
    db.rollback()
    return HTTPException(status_code=refusal.http_status, detail={"code": refusal.code})


def _telegram_account(db, telegram_id: int, *, create: bool = False) -> int | None:
    return ledger.account_id_for(db, ledger.TELEGRAM, telegram_id, create=create)


def _existing_provider(db, telegram_id: int) -> ProviderProfile:
    provider = profils.provider_profile(db, _telegram_account(db, telegram_id))
    if provider is None:
        raise HTTPException(status_code=404, detail="provider_not_found")
    return provider


@router.post("/api/bot/users")
def create_bot_user(payload: BotUserPayload):
    with SessionLocal() as db:
        try:
            account_id = _telegram_account(db, payload.telegram_id, create=True)
            client, _ = profils.save_client_profile(
                db, account_id, first_name=payload.first_name or "Client", phone_number=payload.phone_number
            )
            profils.set_language(db, account_id, payload.language)
            if payload.phone_verified:
                profils.record_proven_phone(db, account_id, payload.phone_number)
            db.commit()
        except profils.ProfileRefused as refusal:
            raise _profile_refused(db, refusal) from refusal
        return {"status": "ok", "user": _user_to_dict(db, account_id, client)}


class WhatsAppClientPayload(BaseModel):
    """Inscription d'un client WhatsApp. L'identité est l'acteur (BSUID, en
    en-têtes). `phone` : le numéro que Meta joint au message (`wa_id`), à
    omettre quand Meta ne le donne pas."""

    display_name: str = Field(min_length=1, max_length=crud.MAX_DISPLAY_NAME_LENGTH)
    language: str = Field(min_length=2, max_length=5)
    phone: str | None = Field(default=None, max_length=32)


@router.post("/api/whatsapp/client")
@open_to(ledger.WHATSAPP)
@idempotent
def register_whatsapp_client(
    payload: WhatsAppClientPayload,
    request: Request,
    response: Response,
    actor: Actor = Depends(current_actor),
    idempotency_key: str | None = Header(default=None, alias=idempotency.HEADER),
):
    """Inscrit ou met à jour le client qui écrit depuis WhatsApp. Jamais de
    rôle prestataire. Un numéro déjà prouvé sur un autre compte est refusé
    (`phone_owned_by_account`) : aucun compte n'est rattaché par le numéro
    seul. Voir `crud.register_whatsapp_client`. Le même message rejoué rend
    la même réponse sans rien refaire."""

    def action(db) -> dict:
        try:
            account, created = crud.register_whatsapp_client(
                db,
                bsuid=actor.external_id,
                display_name=payload.display_name,
                language=payload.language,
                phone=payload.phone,
            )
        except crud.ClientRefused as refusal:
            raise HTTPException(status_code=refusal.http_status, detail={"code": refusal.code}) from refusal
        return {
            "status": "ok",
            "created": created,
            "account": {
                "account_id": account.id,
                "display_name": profils.client_profile(db, account.id).first_name,
                "language": account.language,
                "roles": list(account.roles or []),
                # Jamais le numéro lui-même : seulement s'il est prouvé.
                "phone_proven": account.phone_verified_at is not None,
            },
        }

    return _run_idempotent(request, response, actor, idempotency_key, payload.model_dump(mode="json"), action)


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


def _alert_admin_not_me(device_id: int, account_id: int) -> None:
    from backend.app.tasks import alert_admin_not_me

    alert_admin_not_me(device_id, account_id)


@router.post("/api/bot/app-devices/{device_id}/not-me")
def app_device_not_me(device_id: int, background_tasks: BackgroundTasks, actor: Actor = Depends(current_actor)):
    """« Ce n'est pas moi », appuyé sous l'alerte « Nouvel appareil » : le
    téléphone est coupé tout de suite, avec toutes ses sessions, et l'admin
    est prévenu. Seul le compte du téléphone peut le faire ; un second appui
    ne change rien. Voir `app_sessions.report_not_me`."""
    with SessionLocal() as db:
        account_id = ledger.account_id_for(db, actor.channel, actor.external_id)
        if account_id is None:
            raise HTTPException(status_code=404, detail={"code": "device_not_found"})
        try:
            device, revoked_now = app_sessions.report_not_me(db, account_id=account_id, device_id=device_id)
        except app_auth.AuthError as error:
            db.rollback()
            raise HTTPException(status_code=error.http_status, detail={"code": error.code})
        if revoked_now:
            background_tasks.add_task(_alert_admin_not_me, device.id, account_id)
        return {"status": "ok", "revoked": True, "already": not revoked_now}


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
@provider_action
def create_bot_provider(payload: BotProviderPayload):
    with SessionLocal() as db:
        try:
            account_id = _telegram_account(db, payload.telegram_id, create=True)
            provider, _ = profils.register_provider(
                db,
                account_id,
                full_name=payload.full_name,
                phone_number=payload.phone_number,
                services=payload.services or [],
                communes=payload.communes or [],
                id_document_file_id=payload.id_document_file_id,
                selfie_file_id=payload.selfie_file_id,
                portfolio_file_ids=payload.portfolio_file_ids,
            )
            profils.set_language(db, account_id, payload.language)
            if payload.phone_verified:
                profils.record_proven_phone(db, account_id, payload.phone_number)
            db.commit()
        except profils.ProfileRefused as refusal:
            raise _profile_refused(db, refusal) from refusal
        return {"status": "ok", "provider": _provider_to_dict(db, provider)}


@router.patch("/api/bot/users/{telegram_id}/language")
def update_user_language(telegram_id: int, payload: LanguagePayload):
    with SessionLocal() as db:
        account_id = _telegram_account(db, telegram_id)
        client = profils.client_profile(db, account_id)
        if client is None:
            raise HTTPException(status_code=404, detail="user_not_found")
        try:
            profils.set_language(db, account_id, payload.language)
            db.commit()
        except profils.ProfileRefused as refusal:
            raise _profile_refused(db, refusal) from refusal
        return {"status": "ok", "user": _user_to_dict(db, account_id, client)}


@router.patch("/api/bot/users/{telegram_id}/name")
def update_user_name(telegram_id: int, payload: NamePayload):
    with SessionLocal() as db:
        account_id = _telegram_account(db, telegram_id)
        if profils.client_profile(db, account_id) is None:
            raise HTTPException(status_code=404, detail="user_not_found")
        try:
            client = profils.rename_client(db, account_id, payload.first_name)
            db.commit()
        except profils.ProfileRefused as refusal:
            raise _profile_refused(db, refusal) from refusal
        return {"status": "ok", "user": _user_to_dict(db, account_id, client)}


@router.patch("/api/bot/providers/{telegram_id}/language")
@provider_action
def update_provider_language(telegram_id: int, payload: LanguagePayload):
    with SessionLocal() as db:
        provider = _existing_provider(db, telegram_id)
        try:
            profils.set_language(db, provider.account_id, payload.language)
            db.commit()
        except profils.ProfileRefused as refusal:
            raise _profile_refused(db, refusal) from refusal
        return {"status": "ok", "provider": _provider_to_dict(db, provider)}


@router.patch("/api/bot/providers/{telegram_id}/services")
@provider_action
def update_provider_services(telegram_id: int, payload: ProviderServicesPayload):
    with SessionLocal() as db:
        provider = _existing_provider(db, telegram_id)
        try:
            provider = profils.set_provider_services(db, provider.account_id, payload.services)
            db.commit()
        except profils.ProfileRefused as refusal:
            raise _profile_refused(db, refusal) from refusal
        return {"status": "ok", "provider": _provider_to_dict(db, provider)}


@router.patch("/api/bot/providers/{telegram_id}/status")
@provider_action
def update_provider_status(telegram_id: int, payload: ProviderStatusPayload):
    """Le bot demande un statut ; la règle de `profils` décide :
    `available` / `offline` = le prestataire vérifié lui-même ; `rejected` =
    refus de l'admin ; `pending_verification` = seulement s'il y est déjà
    (une réinscription ne remet jamais un prestataire vérifié en attente)."""
    with SessionLocal() as db:
        provider = _existing_provider(db, telegram_id)
        try:
            if payload.status in profils.SELF_STATUSES:
                provider = profils.set_own_availability(db, provider.account_id, payload.status)
            elif payload.status == "rejected":
                provider = profils.reject_provider(db, provider.account_id)
            elif payload.status != "pending_verification" or provider.status != "pending_verification":
                raise profils.ProfileRefused("status_not_allowed")
            db.commit()
        except profils.ProfileRefused as refusal:
            raise _profile_refused(db, refusal) from refusal
        return {"status": "ok", "provider": _provider_to_dict(db, provider)}


@router.post("/api/bot/providers/{telegram_id}/verify")
def verify_provider(telegram_id: int):
    with SessionLocal() as db:
        provider = _existing_provider(db, telegram_id)
        try:
            provider = profils.verify_provider(db, provider.account_id)
            db.commit()
        except profils.ProfileRefused as refusal:
            raise _profile_refused(db, refusal) from refusal
        return {"status": "ok", "provider": _provider_to_dict(db, provider)}


def _set_suspended(telegram_id: int, suspended: bool) -> dict:
    with SessionLocal() as db:
        provider = _existing_provider(db, telegram_id)
        provider = profils.set_suspended(db, provider.account_id, suspended)
        db.commit()
        return {"status": "ok", "provider": _provider_to_dict(db, provider)}


@router.post("/api/bot/providers/{telegram_id}/suspend")
def suspend_provider(telegram_id: int):
    return _set_suspended(telegram_id, True)


@router.post("/api/bot/providers/{telegram_id}/unsuspend")
def unsuspend_provider(telegram_id: int):
    return _set_suspended(telegram_id, False)


@router.post("/api/bot/providers/{telegram_id}/ignored")
def increment_provider_ignored(telegram_id: int):
    with SessionLocal() as db:
        provider = _existing_provider(db, telegram_id)
        provider = profils.record_declined_alert(db, provider.account_id)
        db.commit()
        return {"status": "ok", "provider": _provider_to_dict(db, provider)}


@router.post("/api/bot/providers/{telegram_id}/ignored/reset")
def reset_provider_ignored(telegram_id: int):
    with SessionLocal() as db:
        provider = _existing_provider(db, telegram_id)
        provider = profils.reset_declined_alerts(db, provider.account_id)
        db.commit()
        return {"status": "ok", "provider": _provider_to_dict(db, provider)}


@router.get("/api/bot/providers/matching")
def matching_providers(service: str, commune: str):
    with SessionLocal() as db:
        providers = profils.eligible_providers(db, service, commune)[:3]
        return {"status": "ok", "providers": [_provider_to_dict(db, provider) for provider in providers]}


@router.post("/api/bot/providers/rank")
def rank_providers(payload: ProviderRankPayload):
    # Ne renvoie que l'ordre (pas de téléphone ni de pièce d'identité) : le bot
    # a déjà la liste des prestataires disponibles, il lui manque le score.
    with SessionLocal() as db:
        telegram_of_account = {}
        for telegram_id in payload.telegram_ids:
            account_id = _telegram_account(db, telegram_id)
            if account_id is not None and account_id not in telegram_of_account:
                telegram_of_account[account_id] = telegram_id
        ranked = profils.rank(db, list(telegram_of_account))
        return {"status": "ok", "telegram_ids": [telegram_of_account[account_id] for account_id in ranked]}


@router.post("/api/bot/quotes")
@provider_action
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

        if db.get(PaymentIntent, intent_id) is None:
            raise HTTPException(status_code=404, detail={"code": "intent_not_found"})

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


# --- Arrivée confirmée (backend.app.presence) ---------------------------------
# Plus de route « démarrer » : une mission démarre quand l'arrivée du
# prestataire est confirmée par le client ou par le code de présence.


class PresenceCodePayload(BaseModel):
    code: str = Field(max_length=20)


def _presence_after_commit(mission_id: int, events: list[str], *, actor_role: str, client_asked: bool) -> None:
    """Messages de l'arrivée, après validation et après la réponse : celui qui
    vient d'agir voit la réponse dans son canal, l'autre partie est prévenue
    ici."""
    with SessionLocal() as db:
        if client_asked:
            presence.notify_client_question(db, mission_id)
        if "confirmed" in events:
            presence.notify_confirmed(db, mission_id, tell_client=actor_role != "client", tell_provider=actor_role != "provider")
        if "not_yet" in events:
            presence.notify_not_yet(db, mission_id)
        if "wrong_person" in events:
            presence.notify_wrong_person(db, mission_id)


def _code_locked_after_commit(mission_id: int) -> None:
    with SessionLocal() as db:
        presence.notify_code_locked(db, mission_id)


def _presence_call(operation, background_tasks: BackgroundTasks, actor_role: str):
    with SessionLocal() as db:
        try:
            result = operation(db)
        except presence.PresenceCodeRefused as error:
            refusal = _money_refusal(db, error)
            refusal.detail["attempts_left"] = error.attempts_left
            if not error.just_locked:
                raise refusal from error
            # Un refus levé abandonne les tâches d'après réponse : la réponse
            # est construite ici pour que l'admin et le client soient prévenus.
            return JSONResponse(
                status_code=refusal.status_code,
                content=jsonable_encoder({"detail": refusal.detail}),
                background=BackgroundTask(_code_locked_after_commit, error.mission.mission_id),
            )
        except ledger.MoneyError as error:
            raise _money_refusal(db, error) from error
        if result.events or result.client_asked:
            background_tasks.add_task(
                _presence_after_commit, result.mission.mission_id, result.events, actor_role=actor_role, client_asked=result.client_asked
            )
        mission = db.get(BotMission, result.mission.mission_id)
        return {
            **_money_response(db, mission),
            "presence": presence.presence_state(db, mission, actor_role),
            "client_asked": result.client_asked,
        }


def _provider_account(db, actor: Actor) -> int:
    return _actor_account(db, actor, missing="not_mission_provider", http_status=403)


def _client_account(db, actor: Actor) -> int:
    return _actor_account(db, actor, missing="not_mission_client", http_status=403)


@router.post("/api/bot/missions/{mission_id}/presence/arrived")
@provider_action
def declare_arrival(mission_id: int, background_tasks: BackgroundTasks, actor: Actor = Depends(current_actor)):
    return _presence_call(lambda db: presence.declare_arrival(db, mission_id, _provider_account(db, actor)), background_tasks, "provider")


@router.post("/api/bot/missions/{mission_id}/presence/code")
@provider_action
def confirm_presence_by_code(
    mission_id: int, payload: PresenceCodePayload, background_tasks: BackgroundTasks, actor: Actor = Depends(current_actor)
):
    return _presence_call(
        lambda db: presence.confirm_by_code(db, mission_id, _provider_account(db, actor), payload.code), background_tasks, "provider"
    )


@router.post("/api/bot/missions/{mission_id}/presence/confirm")
def confirm_presence_by_client(mission_id: int, background_tasks: BackgroundTasks, actor: Actor = Depends(current_actor)):
    return _presence_call(lambda db: presence.confirm_by_client(db, mission_id, _client_account(db, actor)), background_tasks, "client")


@router.post("/api/bot/missions/{mission_id}/presence/not-yet")
def presence_not_yet(mission_id: int, background_tasks: BackgroundTasks, actor: Actor = Depends(current_actor)):
    return _presence_call(lambda db: presence.answer_not_yet(db, mission_id, _client_account(db, actor)), background_tasks, "client")


@router.post("/api/bot/missions/{mission_id}/presence/wrong-person")
def presence_wrong_person(mission_id: int, background_tasks: BackgroundTasks, actor: Actor = Depends(current_actor)):
    return _presence_call(lambda db: presence.report_wrong_person(db, mission_id, _client_account(db, actor)), background_tasks, "client")


@router.get("/api/bot/missions/{mission_id}/presence")
def get_presence(mission_id: int, actor: Actor = Depends(current_actor)):
    """État de l'arrivée. Le code de présence n'est donné qu'au client de la
    mission ; pour qui n'est ni client, ni prestataire choisi, ni admin : 404,
    comme un numéro inconnu."""
    with SessionLocal() as db:
        mission = db.get(BotMission, mission_id)
        role = None
        if mission is not None:
            account_id = ledger.account_id_for(db, actor.channel, actor.external_id)
            role = presence.viewer_role(db, mission, account_id, _is_admin(actor))
        if role is None:
            raise HTTPException(status_code=404, detail={"code": "mission_not_found"})
        try:
            state = presence.presence_state(db, mission, role)
        except ledger.MoneyError as error:
            raise HTTPException(status_code=error.http_status, detail={"code": error.code}) from error
        return {"status": "ok", "mission_id": mission_id, "presence": state}


@router.post("/api/bot/missions/{mission_id}/finish")
@provider_action
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


@router.post("/api/bot/missions/{mission_id}/dispute/decide")
def decide_dispute(
    mission_id: int, payload: DisputeDecidePayload, background_tasks: BackgroundTasks, actor: Actor = Depends(current_actor)
):
    """Décision de Nexis Hub : la première est exécutée 3 jours plus tard sauf
    contestation ; la révision d'une décision contestée, prise par une autre
    personne, est exécutée tout de suite (ledger.decide_dispute). Le client et
    le prestataire sont prévenus une fois, après la réponse."""
    admin_telegram_id = _require_admin(actor)
    recorded = {}

    def decide(db):
        before = len(ledger.dispute_decisions(db, mission_id))
        mission = ledger.decide_dispute(
            db,
            mission_id,
            decision=payload.decision,
            # Le compte de la personne qui décide : c'est lui que la révision compare.
            admin_account_id=_actor_account(db, actor, create=True),
            admin_telegram_id=admin_telegram_id,
            provider_percentage=payload.provider_percentage,
        )
        recorded["new"] = len(ledger.dispute_decisions(db, mission_id)) > before
        return mission

    response = _money_call(decide)
    if recorded.get("new"):
        background_tasks.add_task(_notify_dispute, mission_id, "decided")
    return response


@router.post("/api/bot/missions/{mission_id}/dispute/contest")
def contest_dispute(
    mission_id: int, payload: DisputeContestPayload, background_tasks: BackgroundTasks, actor: Actor = Depends(current_actor)
):
    """Le client ou le prestataire conteste la première décision, avant son
    exécution. L'autre partie et l'admin sont prévenus une fois."""
    recorded = {}

    def contest(db):
        first = next((row for row in ledger.dispute_decisions(db, mission_id) if row.round == ledger.FIRST_DECISION), None)
        already = first is not None and first.contested_at is not None
        mission = ledger.contest_dispute_decision(
            db, mission_id, _actor_account(db, actor, missing="not_mission_party", http_status=403), payload.reason
        )
        recorded["new"] = not already
        return mission

    response = _money_call(contest)
    if recorded.get("new"):
        background_tasks.add_task(_notify_dispute, mission_id, "contested")
    return response


def _notify_dispute(mission_id: int, event: str) -> None:
    from backend.app import tasks

    with SessionLocal() as db:
        mission = db.get(BotMission, mission_id)
        if event == "contested":
            tasks.notify_dispute_contested(db, mission)
        elif mission.status == "disputed":
            tasks.notify_dispute_decided(db, mission)
        else:
            # Révision : exécutée tout de suite.
            tasks.notify_dispute_settled(db, mission)


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
@open_to(ledger.TELEGRAM, ledger.WHATSAPP)
def my_missions(role: str = "client", limit: int = 20, actor: Actor = Depends(current_actor)):
    """Missions de l'acteur : celles qu'il a commandées (`client`) ou qui lui
    sont confiées (`provider`)."""
    if role not in ("client", "provider"):
        raise HTTPException(status_code=400, detail={"code": "invalid_role"})
    if role == "provider" and actor.channel not in PROVIDER_CHANNELS:
        raise HTTPException(status_code=403, detail={"code": "provider_channel_forbidden"})
    limit = max(1, min(limit, 50))
    with SessionLocal() as db:
        account_id = ledger.account_id_for(db, actor.channel, actor.external_id)
        if account_id is None:
            return {"status": "ok", "missions": []}
        missions = (crud.client_missions if role == "client" else crud.provider_missions)(db, account_id, limit)
        return {"status": "ok", "missions": [_listed_mission(db, mission) for mission in missions]}


def _listed_mission(db, mission: BotMission, admin: bool = False) -> dict:
    """Mission d'une liste, avec les noms affichés par les canaux et ses
    décisions de litige (détail interne à Nexis Hub seulement pour l'admin)."""
    client = profils.client_profile(db, mission.client_account_id or _telegram_account(db, mission.telegram_id))
    provider_account_id = mission.provider_account_id
    if provider_account_id is None and mission.provider_telegram_id is not None:
        provider_account_id = _telegram_account(db, mission.provider_telegram_id)
    provider = profils.provider_profile(db, provider_account_id)
    return {
        **_mission_to_dict(mission),
        "client_name": client.first_name if client is not None else None,
        "provider_name": provider.full_name if provider is not None else None,
        "dispute_decisions": [
            _admin_decision(decision) if admin else ledger.dispute_decision_view(decision)
            for decision in ledger.dispute_decisions(db, mission.mission_id)
        ],
    }


def _admin_decision(decision) -> dict:
    """Décision de litige vue par l'admin : avec qui l'a prise (la révision
    doit venir d'une autre personne) et la raison de la contestation."""
    return {
        **ledger.dispute_decision_view(decision),
        "decided_by_telegram_id": decision.decided_by_telegram_id,
        "contest_reason": decision.contest_reason,
    }


@router.get("/api/admin/missions")
def admin_list_missions(status: str | None = None, limit: int = 10, actor: Actor = Depends(current_actor)):
    _require_admin(actor)
    with SessionLocal() as db:
        missions = crud.admin_missions(db, status=status, limit=max(1, min(limit, 50)))
        return {"status": "ok", "missions": [_listed_mission(db, mission, admin=True) for mission in missions]}


@router.get("/api/admin/stats")
def admin_stats(actor: Actor = Depends(current_actor)):
    _require_admin(actor)
    with SessionLocal() as db:
        return {"status": "ok", "stats": crud.mission_stats(db)}


@router.get("/api/me/wallet")
@open_to(ledger.TELEGRAM, ledger.WHATSAPP)
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
@provider_action
def create_service_request(payload: ServiceRequestPayload, actor: Actor = Depends(current_actor)):
    with SessionLocal() as db:
        try:
            req = crud.create_service_request(
                db,
                provider_account_id=ledger.account_id_for(db, actor.channel, actor.external_id),
                service_name=payload.service_name,
                description=payload.description,
            )
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {"status": "ok", "service_request": _service_request_to_dict(db, req)}


@router.get("/api/bot/service-requests/pending")
def get_pending_service_requests(limit: int = 10):
    with SessionLocal() as db:
        results = crud.get_pending_service_requests(db, limit=limit)
        serialized = [_service_request_to_dict(db, req, provider) for req, provider in results]
        return {"status": "ok", "service_requests": serialized}


@router.get("/api/bot/service-requests/{request_id}")
def get_service_request(request_id: int):
    with SessionLocal() as db:
        result = crud.get_service_request_by_id(db, request_id)
        if result is None:
            raise HTTPException(status_code=404, detail="service_request_not_found")
        req, provider = result
        return {"status": "ok", "service_request": _service_request_to_dict(db, req, provider)}


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
        return {"status": "ok", "service_request": _service_request_to_dict(db, req)}


@router.get("/api/profile/{telegram_id}")
def profile(telegram_id: int):
    with SessionLocal() as db:
        account_id = _telegram_account(db, telegram_id)
        client = profils.client_profile(db, account_id)
        provider = profils.provider_profile(db, account_id)
        client_missions = []
        provider_missions = []
        if account_id is not None:
            client_missions = [
                _mission_to_dict(mission)
                for mission in db.query(BotMission)
                .filter((BotMission.client_account_id == account_id) | (BotMission.telegram_id == telegram_id))
                .order_by(BotMission.mission_id)
                .all()
            ]
            for mission in (
                db.query(BotMission)
                .filter((BotMission.provider_account_id == account_id) | (BotMission.provider_telegram_id == telegram_id))
                .order_by(BotMission.mission_id)
                .all()
            ):
                mission_data = _mission_to_dict(mission)
                # Nom du client, affiché au prestataire.
                mission_client = profils.client_profile(
                    db, mission.client_account_id or _telegram_account(db, mission.telegram_id)
                )
                mission_data["client_name"] = mission_client.first_name if mission_client else None
                provider_missions.append(mission_data)

        service_requests = []
        if provider:
            service_requests = [
                _service_request_to_dict(db, req) for req in crud.get_provider_service_requests(db, account_id)
            ]

        return {
            "telegram_id": telegram_id,
            "client": _user_to_dict(db, account_id, client) if client else None,
            "provider": _provider_to_dict(db, provider) if provider else None,
            "client_missions": client_missions,
            "provider_missions": provider_missions,
            "service_requests": service_requests,
            "profile_type": "client" if client else "provider" if provider else "guest",
        }


app.include_router(router)
