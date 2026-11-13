from contextlib import asynccontextmanager
from pathlib import Path
import hashlib
import hmac
import json
import os
import time
from urllib.parse import parse_qsl


import httpx
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import nexis_config
import nexis_logs
from telegram_bot import backend_client
from telegram_bot.backend_client import BackendUnavailable, MoneyRefused


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR.parent / ".env")
BOT_TOKEN = os.getenv("BOT_TOKEN")

@asynccontextmanager
async def _lifespan(_app: FastAPI):
    # Hors développement, une configuration incomplète empêche le démarrage.
    nexis_config.verifier("miniapp")
    nexis_logs.configurer("miniapp")
    # Sans la clé du canal Telegram, la Mini App ne pourrait rien demander au
    # backend : elle refuse de démarrer plutôt que de répondre « indisponible ».
    backend_client.check_backend_key()
    yield


app = FastAPI(title="Nexis Hub Mini App", lifespan=_lifespan)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

class ServicesUpdate(BaseModel):
    services: list[str]


class ServiceRequestCreate(BaseModel):
    service_name: str
    description: str


class StatusUpdate(BaseModel):
    status: str


class ProviderRegistrationCreate(BaseModel):
    phone_number: str
    full_name: str
    services: list[str]
    communes: list[str]
    language: str = "fr"


@app.get("/")
def index():
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.get("/health")
def health():
    return {"status": "ok", "app": "nexis-hub-mini-app"}


@app.get("/health/live")
def health_live():
    return {"status": "ok"}


@app.get("/health/ready")
async def health_ready():
    """Prête si le backend, dont dépend chaque écran, répond."""
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get(f"{backend_client.BACKEND_BASE_URL}/health/live")
        response.raise_for_status()
    except httpx.HTTPError:
        return JSONResponse({"status": "indisponible", "problemes": ["backend injoignable"]}, status_code=503)
    return {"status": "ok"}


def verify_telegram_init_data(
    init_data: str | None = Header(default=None, alias="X-Telegram-Init-Data"),
):
    if not BOT_TOKEN:
        raise HTTPException(status_code=500, detail="BOT_TOKEN manquant")
    if not init_data:
        raise HTTPException(status_code=401, detail="Authentification Telegram requise")

    try:
        parsed = dict(parse_qsl(init_data, strict_parsing=True))
    except ValueError:
        raise HTTPException(status_code=401, detail="Donnees Telegram invalides")

    received_hash = parsed.pop("hash", None)
    if not received_hash:
        raise HTTPException(status_code=401, detail="Signature Telegram manquante")

    try:
        auth_date = int(parsed.get("auth_date", "0") or "0")
    except ValueError:
        raise HTTPException(status_code=401, detail="Date Telegram invalide")
    if auth_date and time.time() - auth_date > 86400:
        raise HTTPException(status_code=401, detail="Session Telegram expiree")

    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(parsed.items()))
    secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(calculated_hash, received_hash):
        raise HTTPException(status_code=401, detail="Signature Telegram invalide")

    try:
        return json.loads(parsed.get("user", "{}"))
    except json.JSONDecodeError:
        raise HTTPException(status_code=401, detail="Utilisateur Telegram invalide")


def require_same_telegram_user(telegram_id: int, telegram_user: dict):
    if int(telegram_user.get("id", 0)) != telegram_id:
        raise HTTPException(status_code=403, detail="Acces refuse")


def compact_mission(mission: dict) -> dict:
    """Mission du backend (seule mémoire des missions), réduite à ce que la
    page affiche."""
    return {
        "id": mission["mission_id"],
        "service": mission["service"],
        "commune": mission["commune"],
        "status": mission["status"],
        "payment_status": mission["payment_status"],
        "currency": mission["currency"],
        "provider_name": mission.get("provider_name"),
        "client_name": mission.get("client_name"),
    }


async def my_missions(telegram_id: int, role: str) -> list[dict] | None:
    """None si le backend ne répond pas : la page affiche « indisponible »."""
    try:
        return [compact_mission(mission) for mission in await backend_client.list_my_missions(telegram_id, role)]
    except (BackendUnavailable, MoneyRefused):
        return None


# Profils et catalogue : ceux du backend, lus et écrits au nom de la personne
# vérifiée par Telegram (signature initData). La Mini App ne garde rien.
UNAVAILABLE = "Service momentanément indisponible. Rien n'a changé, réessayez dans un instant."
PROFILE_REFUSALS = {
    "unknown_service": "Service invalide",
    "services_required": "Choisis au moins un service",
    "invalid_services": "Service invalide",
    "unknown_commune": "Commune invalide",
    "communes_required": "Choisis au moins une commune",
    "invalid_communes": "Commune invalide",
    "invalid_name": "Nom complet invalide",
    "invalid_phone": "Numero WhatsApp invalide",
    "provider_not_found": "Prestataire introuvable",
    "provider_not_verified": "Profil en attente de validation par Nexis",
    "provider_suspended": "Profil suspendu par Nexis",
}


async def _backend(call):
    """Résultat d'une demande au backend, ou l'erreur HTTP que la page affiche
    (texte de `detail`)."""
    try:
        return await call
    except MoneyRefused as error:
        status = 404 if error.code == "provider_not_found" else 403 if error.code in ("provider_not_verified", "provider_suspended") else 400
        raise HTTPException(status_code=status, detail=PROFILE_REFUSALS.get(error.code, "Action refusee"))
    except BackendUnavailable:
        raise HTTPException(status_code=503, detail=UNAVAILABLE)


def page_provider(provider: dict | None) -> dict | None:
    """Profil prestataire du backend, dans la forme que la page lit."""
    if provider is None:
        return None
    return {**provider, "rating": provider.get("average_rating") or 0}


@app.get("/api/profile/{telegram_id}")
async def profile(telegram_id: int, telegram_user: dict = Depends(verify_telegram_init_data)):
    require_same_telegram_user(telegram_id, telegram_user)
    me = await _backend(backend_client.fetch_me(telegram_id))
    catalogue = await _backend(backend_client.fetch_catalogue())
    service_requests = await _backend(backend_client.my_service_requests(telegram_id)) if me["provider"] else []
    # Soldes lus dans le registre du backend : backend injoignable = None, la
    # page affiche « indisponible », jamais un chiffre par défaut.
    wallets = await backend_client.fetch_wallets(telegram_id)
    wallet = wallets.get("wallet") if isinstance(wallets, dict) else None

    return {
        "telegram_id": telegram_id,
        "client": me["client"],
        "provider": page_provider(me["provider"]),
        "client_missions": await my_missions(telegram_id, "client"),
        "provider_missions": await my_missions(telegram_id, "provider"),
        "service_requests": service_requests,
        "wallet": wallet if isinstance(wallet, dict) else None,
        "available_services": {service["key"]: service["names"]["fr"] for service in catalogue["services"]},
        "available_communes": catalogue["communes"],
    }


@app.post("/api/provider/{telegram_id}/register")
async def register_provider(
    telegram_id: int,
    payload: ProviderRegistrationCreate,
    telegram_user: dict = Depends(verify_telegram_init_data),
):
    """Inscription prestataire depuis la Mini App. Le backend le met en
    attente de vérification, comme depuis le bot : il ne reçoit aucune mission
    tant que l'équipe ne l'a pas validé. La Mini App ne collecte pas encore
    les documents d'identité (chantier séparé) ; le numéro tapé n'est pas
    prouvé."""
    require_same_telegram_user(telegram_id, telegram_user)
    full_name = payload.full_name.strip()
    phone_number = payload.phone_number.strip()
    if len(full_name) < 3:
        raise HTTPException(status_code=400, detail="Nom complet trop court")
    if len(phone_number) < 8:
        raise HTTPException(status_code=400, detail="Numero WhatsApp invalide")
    if not payload.services:
        raise HTTPException(status_code=400, detail="Choisis au moins un service")
    if not payload.communes:
        raise HTTPException(status_code=400, detail="Choisis au moins une commune")

    me = await _backend(
        backend_client.save_provider_profile(
            telegram_id,
            {
                "full_name": full_name,
                "phone_number": phone_number,
                "services": payload.services,
                "communes": payload.communes,
                "language": payload.language,
            },
        )
    )
    return {"status": "ok", "provider": page_provider(me["provider"])}


@app.post("/api/provider/{telegram_id}/services")
async def save_provider_services(
    telegram_id: int,
    payload: ServicesUpdate,
    telegram_user: dict = Depends(verify_telegram_init_data),
):
    require_same_telegram_user(telegram_id, telegram_user)
    if not payload.services:
        raise HTTPException(status_code=400, detail="Choisis au moins un service")
    me = await _backend(backend_client.set_my_services(telegram_id, payload.services))
    return {"status": "ok", "provider": page_provider(me["provider"])}


@app.post("/api/provider/{telegram_id}/service-requests")
async def request_missing_service(
    telegram_id: int,
    payload: ServiceRequestCreate,
    telegram_user: dict = Depends(verify_telegram_init_data),
):
    require_same_telegram_user(telegram_id, telegram_user)
    service_name = payload.service_name.strip()
    description = payload.description.strip()
    if len(service_name) < 3:
        raise HTTPException(status_code=400, detail="Nom du service trop court")
    if len(description) < 10:
        raise HTTPException(status_code=400, detail="Description trop courte")

    request = await _backend(backend_client.propose_service(telegram_id, service_name, description))
    service_requests = await _backend(backend_client.my_service_requests(telegram_id))
    return {"status": "ok", "request_id": request["id"], "service_requests": service_requests}


@app.post("/api/provider/{telegram_id}/status")
async def save_provider_status(
    telegram_id: int,
    payload: StatusUpdate,
    telegram_user: dict = Depends(verify_telegram_init_data),
):
    """Disponible ou hors ligne : le backend décide (prestataire vérifié et
    non suspendu seulement). C'est ce statut qui compte pour les alertes de
    mission, que le changement vienne du bot ou de la Mini App."""
    require_same_telegram_user(telegram_id, telegram_user)
    if payload.status not in {"available", "offline"}:
        raise HTTPException(status_code=400, detail="Statut invalide")
    me = await _backend(backend_client.set_my_availability(telegram_id, payload.status))
    return {"status": "ok", "provider": page_provider(me["provider"])}


async def _mission_action(mission_id: int, action) -> dict:
    """Arrivée, code de présence et fin de mission conditionnent la libération
    des fonds : c'est le registre du backend qui décide (CONCEPTION_ARGENT.md),
    la Mini App affiche l'état renvoyé. Refus métier : 409 avec son code (et
    les essais restants d'un mauvais code) ; backend injoignable : 503, rien
    n'a changé."""
    try:
        result = await action
    except MoneyRefused as error:
        detail = {"code": error.code}
        if "attempts_left" in error.details:
            detail["attempts_left"] = error.details["attempts_left"]
        raise HTTPException(status_code=409, detail=detail)
    except BackendUnavailable:
        raise HTTPException(status_code=503, detail={"code": "backend_unavailable"})
    response = {"status": "ok", "mission": compact_mission(result["mission"])}
    if "presence" in result:
        # Jamais le code : le backend ne le donne qu'au client.
        response["presence"] = {"confirmed": result["presence"]["confirmed"], "client_asked": result.get("client_asked", False)}
    return response


class PresenceCodeInput(BaseModel):
    code: str = Field(max_length=20)


@app.post("/api/provider/{telegram_id}/missions/{mission_id}/arrived")
async def provider_arrived(
    telegram_id: int,
    mission_id: int,
    telegram_user: dict = Depends(verify_telegram_init_data),
):
    """« Je suis arrivé » : le client reçoit la question ; la mission démarre
    à sa réponse, ou au code de présence qu'il donne au prestataire."""
    require_same_telegram_user(telegram_id, telegram_user)
    return await _mission_action(mission_id, backend_client.declare_arrival(mission_id, telegram_id))


@app.post("/api/provider/{telegram_id}/missions/{mission_id}/presence-code")
async def provider_presence_code(
    telegram_id: int,
    mission_id: int,
    payload: PresenceCodeInput,
    telegram_user: dict = Depends(verify_telegram_init_data),
):
    require_same_telegram_user(telegram_id, telegram_user)
    return await _mission_action(mission_id, backend_client.confirm_presence_code(mission_id, telegram_id, payload.code))


@app.post("/api/provider/{telegram_id}/missions/{mission_id}/finish")
async def finish_provider_mission(
    telegram_id: int,
    mission_id: int,
    telegram_user: dict = Depends(verify_telegram_init_data),
):
    require_same_telegram_user(telegram_id, telegram_user)
    return await _mission_action(mission_id, backend_client.finish_mission(mission_id, telegram_id))
