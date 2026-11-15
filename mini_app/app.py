from contextlib import asynccontextmanager
from pathlib import Path
import hashlib
import hmac
import json
import os
import re
import time
from urllib.parse import parse_qsl


import httpx
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field
from fastapi.responses import HTMLResponse, JSONResponse
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


class CommunesUpdate(BaseModel):
    communes: list[str]


class ServiceRequestCreate(BaseModel):
    service_name: str
    description: str


class ServiceAdditionCreate(BaseModel):
    service_key: str = Field(max_length=64)
    description: str = Field(default="", max_length=500)
    photo_ids: list[str] = Field(default_factory=list, max_length=10)


class StatusUpdate(BaseModel):
    status: str


class ProviderRegistrationCreate(BaseModel):
    phone_number: str
    full_name: str
    services: list[str]
    communes: list[str]
    language: str = "fr"


STATIC_DIR = BASE_DIR / "static"
_STATIC_LINK = re.compile(r'(?P<attr>(?:src|href)=")/static/(?P<name>[\w.-]+\.(?:css|js))"')


def _versioned(match: re.Match) -> str:
    """Lien vers un fichier de la page, suivi de l'empreinte de son contenu :
    un fichier changé a une nouvelle adresse, que Telegram ne peut pas
    servir depuis son cache."""
    path = STATIC_DIR / match["name"]
    if not path.is_file():
        return match[0]
    digest = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
    return f'{match["attr"]}/static/{match["name"]}?v={digest}"'


@app.get("/")
def index():
    """La page elle-même n'est jamais gardée en cache (la vue web de
    Telegram, surtout sur iPhone, garde sinon l'ancienne version) ; ses
    fichiers le sont, sous une adresse qui change avec leur contenu."""
    page = _STATIC_LINK.sub(_versioned, (STATIC_DIR / "index.html").read_text(encoding="utf-8"))
    return HTMLResponse(page, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})


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
        "net_provider": mission.get("net_provider"),
        "description": mission.get("description"),
        "urgent": bool(mission.get("urgent")),
        "release_after": mission.get("release_after"),
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
    "too_many_services": "Nombre maximum de services atteint",
    "service_not_for_providers": "Ce service ne peut pas etre choisi par un prestataire",
    "invalid_communes": "Commune invalide",
    "invalid_name": "Nom complet invalide",
    "invalid_phone": "Numero WhatsApp invalide",
    "provider_not_found": "Prestataire introuvable",
    "provider_not_verified": "Profil en attente de validation par Nexis",
    "provider_suspended": "Profil suspendu par Nexis",
    "service_needs_review": "Un nouveau service doit etre valide par l'equipe",
    "service_already_offered": "Tu proposes deja ce service",
    "service_addition_pending": "Une demande pour ce service attend deja l'equipe",
    "service_addition_not_found": "Demande introuvable",
    "already_decided": "L'equipe a deja repondu a cette demande",
    "invalid_photos": "Photos invalides",
    "invalid_description": "Description trop longue",
    "empty_file": "Photo vide",
    "file_too_large": "Photo trop lourde",
    "unsupported_file_type": "Ce fichier n'est pas une photo",
    "too_many_files": "Trop de photos envoyees aujourd'hui",
    "file_storage_unavailable": "Envoi de photos indisponible",
}


def refused(status_code: int, code: str, detail: str) -> HTTPException:
    """Refus que la page affiche dans la langue du compte : `detail` reste le
    texte français (lisible dans les journaux), l'en-tête X-Nexis-Code donne
    la clé de traduction."""
    return HTTPException(status_code=status_code, detail=detail, headers={"X-Nexis-Code": code})


# Statut HTTP de chaque refus (400 sinon), pour que la page distingue
# « introuvable », « interdit », « trop lourd »... du simple refus.
REFUSAL_STATUS = {
    "provider_not_found": 404,
    "service_addition_not_found": 404,
    "provider_not_verified": 403,
    "provider_suspended": 403,
    "file_too_large": 413,
    "unsupported_file_type": 415,
    "too_many_files": 429,
    "file_storage_unavailable": 503,
}


async def _backend(call):
    """Résultat d'une demande au backend, ou l'erreur HTTP que la page affiche
    (texte de `detail`)."""
    try:
        return await call
    except MoneyRefused as error:
        status = REFUSAL_STATUS.get(error.code, 400)
        code = error.code if error.code in PROFILE_REFUSALS else "refused"
        raise refused(status, code, PROFILE_REFUSALS.get(error.code, "Action refusee"))
    except BackendUnavailable:
        raise refused(503, "backend_unavailable", UNAVAILABLE)


PRIVATE_PROVIDER_FIELDS = ("id_document_file_id", "selfie_file_id", "portfolio_file_ids")
LANGUAGES = ("fr", "ln", "en")


def page_provider(provider: dict | None) -> dict | None:
    """Profil prestataire du backend, dans la forme que la page lit."""
    if provider is None:
        return None
    page = {key: value for key, value in provider.items() if key not in PRIVATE_PROVIDER_FIELDS}
    # Seulement « documents envoyés ou non » : les identifiants Telegram des
    # photos (pièce d'identité, selfie) ne quittent pas le serveur.
    page["has_documents"] = bool(provider.get("id_document_file_id") and provider.get("selfie_file_id"))
    page["rating"] = provider.get("average_rating") or 0
    return page


@app.get("/api/profile/{telegram_id}")
async def profile(telegram_id: int, telegram_user: dict = Depends(verify_telegram_init_data)):
    require_same_telegram_user(telegram_id, telegram_user)
    me = await _backend(backend_client.fetch_me(telegram_id))
    catalogue = await _backend(backend_client.fetch_catalogue())
    service_requests = await _backend(backend_client.my_service_requests(telegram_id)) if me["provider"] else []
    service_additions = await _backend(backend_client.my_service_additions(telegram_id)) if me["provider"] else []
    # Soldes lus dans le registre du backend : backend injoignable = None, la
    # page affiche « indisponible », jamais un chiffre par défaut.
    wallets = await backend_client.fetch_wallets(telegram_id)
    try:
        wallet_history = await backend_client.wallet_history(telegram_id)
    except (BackendUnavailable, MoneyRefused):
        wallet_history = None  # la page dit « indisponible », jamais une liste vide inventée
    wallet = wallets.get("wallet") if isinstance(wallets, dict) else None

    # Personne encore inconnue (ni cliente ni prestataire) : pas de langue
    # choisie, la page prend celle de Telegram.
    language = me.get("language") if me.get("profile_type") != "guest" else None
    return {
        "telegram_id": telegram_id,
        "language": language if language in LANGUAGES else None,
        "client": me["client"],
        "provider": page_provider(me["provider"]),
        "client_missions": await my_missions(telegram_id, "client"),
        "provider_missions": await my_missions(telegram_id, "provider"),
        "service_requests": service_requests,
        "service_additions": service_additions,
        "wallet": wallet if isinstance(wallet, dict) else None,
        "wallet_history": wallet_history,
        "available_services": {service["key"]: service["names"]["fr"] for service in catalogue["services"]},
        "service_names": {service["key"]: service["names"] for service in catalogue["services"]},
        "available_communes": catalogue["communes"],
        "max_services": catalogue.get("provider_max_services"),
        "provider_excluded_services": catalogue.get("provider_excluded_services", []),
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
        raise refused(400, "name_too_short", "Nom complet trop court")
    if len(phone_number) < 8:
        raise refused(400, "invalid_phone", "Numero WhatsApp invalide")
    if not payload.services:
        raise refused(400, "services_required", "Choisis au moins un service")
    if not payload.communes:
        raise refused(400, "communes_required", "Choisis au moins une commune")

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
        raise refused(400, "services_required", "Choisis au moins un service")
    me = await _backend(backend_client.set_my_services(telegram_id, payload.services))
    return {"status": "ok", "provider": page_provider(me["provider"])}


@app.post("/api/provider/{telegram_id}/communes")
async def save_provider_communes(
    telegram_id: int,
    payload: CommunesUpdate,
    telegram_user: dict = Depends(verify_telegram_init_data),
):
    """Communes où le prestataire travaille : le backend vérifie qu'elles
    existent au catalogue."""
    require_same_telegram_user(telegram_id, telegram_user)
    if not payload.communes:
        raise refused(400, "communes_required", "Choisis au moins une commune")
    me = await _backend(backend_client.set_my_communes(telegram_id, payload.communes))
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
        raise refused(400, "service_name_too_short", "Nom du service trop court")
    if len(description) < 10:
        raise refused(400, "description_too_short", "Description trop courte")

    request = await _backend(backend_client.propose_service(telegram_id, service_name, description))
    service_requests = await _backend(backend_client.my_service_requests(telegram_id))
    return {"status": "ok", "request_id": request["id"], "service_requests": service_requests}


# Photo envoyée depuis le téléphone (déjà réduite par la page) : au plus la
# limite du backend, jamais gardée ici, transmise telle quelle.
MAX_PHOTO_BYTES = 5 * 1024 * 1024


async def _bounded_body(request: Request, limit: int) -> bytes:
    declared = request.headers.get("content-length")
    if declared is not None and declared.isdigit() and int(declared) > limit:
        raise refused(413, "file_too_large", PROFILE_REFUSALS["file_too_large"])
    chunks, size = [], 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > limit:
            raise refused(413, "file_too_large", PROFILE_REFUSALS["file_too_large"])
        chunks.append(chunk)
    return b"".join(chunks)


@app.post("/api/provider/{telegram_id}/photos")
async def upload_photo(telegram_id: int, request: Request, telegram_user: dict = Depends(verify_telegram_init_data)):
    """Une photo de réalisation pour une demande d'ajout de service : le
    backend vérifie son type réel et la garde chiffrée."""
    require_same_telegram_user(telegram_id, telegram_user)
    data = await _bounded_body(request, MAX_PHOTO_BYTES)
    stored = await _backend(backend_client.upload_service_photo(telegram_id, data))
    return {"status": "ok", "photo_id": stored["id"]}


@app.post("/api/provider/{telegram_id}/service-additions")
async def request_service_addition(
    telegram_id: int, payload: ServiceAdditionCreate, telegram_user: dict = Depends(verify_telegram_init_data)
):
    """Demande d'un nouveau service, examinée par l'équipe avant d'être active."""
    require_same_telegram_user(telegram_id, telegram_user)
    await _backend(
        backend_client.request_service_addition(telegram_id, payload.service_key, payload.description.strip(), payload.photo_ids)
    )
    me = await _backend(backend_client.fetch_me(telegram_id))
    additions = await _backend(backend_client.my_service_additions(telegram_id))
    return {"status": "ok", "provider": page_provider(me["provider"]), "service_additions": additions}


@app.post("/api/provider/{telegram_id}/service-additions/{addition_id}/cancel")
async def cancel_service_addition(
    telegram_id: int, addition_id: int, telegram_user: dict = Depends(verify_telegram_init_data)
):
    require_same_telegram_user(telegram_id, telegram_user)
    await _backend(backend_client.cancel_service_addition(telegram_id, addition_id))
    me = await _backend(backend_client.fetch_me(telegram_id))
    additions = await _backend(backend_client.my_service_additions(telegram_id))
    return {"status": "ok", "provider": page_provider(me["provider"]), "service_additions": additions}


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
        raise refused(400, "invalid_status", "Statut invalide")
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
