from pathlib import Path
import hashlib
import hmac
import json
import os
import time
from urllib.parse import parse_qsl

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from db import (
    create_provider,
    create_service_request,
    get_active_services,
    get_provider_by_telegram_id,
    get_provider_missions,
    get_provider_service_requests,
    get_user_by_telegram_id,
    get_user_missions,
    finish_mission,
    start_mission,
    update_provider_services,
    update_provider_status,
)


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR.parent / ".env")
BOT_TOKEN = os.getenv("BOT_TOKEN")

app = FastAPI(title="Nexis Hub Mini App")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

FALLBACK_SERVICES = {
    "service_plomberie": "Plomberie",
    "service_electricite": "Electricite",
    "service_climatisation": "Climatisation",
    "service_informatique": "Informatique",
    "service_graphisme": "Graphisme",
    "service_coiffure": "Coiffure",
    "service_nettoyage": "Nettoyage",
    "service_jardinage": "Jardinage",
    "service_autre": "Autre service",
}


def active_services():
    try:
        services = get_active_services("fr", include_icon=False)
        return services or FALLBACK_SERVICES
    except Exception:
        return FALLBACK_SERVICES

COMMUNES = [
    "Gombe",
    "Kinshasa",
    "Limete",
    "Ngaliema",
    "Lemba",
    "Kalamu",
    "Barumbu",
    "Lingwala",
    "Autre commune",
]


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


def row_to_dict(row):
    if row is None:
        return None
    return dict(row)


def load_json_list(value):
    if not value:
        return []
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else []
    except json.JSONDecodeError:
        return []


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


def compact_mission(row):
    mission = row_to_dict(row)
    if not mission:
        return None
    return {
        "id": mission["id"],
        "service": mission["service"],
        "commune": mission["commune"],
        "status": mission["status"],
        "payment_status": mission["payment_status"],
        "currency": mission["currency"],
        "created_at": mission["created_at"],
        "provider_name": mission.get("provider_name"),
        "client_name": mission.get("client_name"),
    }


@app.get("/api/profile/{telegram_id}")
def profile(telegram_id: int, telegram_user: dict = Depends(verify_telegram_init_data)):
    require_same_telegram_user(telegram_id, telegram_user)
    user = row_to_dict(get_user_by_telegram_id(telegram_id))
    provider = row_to_dict(get_provider_by_telegram_id(telegram_id))
    user_missions = [compact_mission(row) for row in get_user_missions(telegram_id)]
    provider_missions = [compact_mission(row) for row in get_provider_missions(telegram_id)]
    service_requests = [row_to_dict(row) for row in get_provider_service_requests(telegram_id)]

    if provider:
        provider["services"] = load_json_list(provider.get("services"))
        provider["communes"] = load_json_list(provider.get("communes"))
        provider["languages_spoken"] = load_json_list(provider.get("languages_spoken"))

    return {
        "telegram_id": telegram_id,
        "client": user,
        "provider": provider,
        "client_missions": user_missions,
        "provider_missions": provider_missions,
        "service_requests": service_requests,
        "available_services": active_services(),
        "available_communes": COMMUNES,
    }


@app.post("/api/provider/{telegram_id}/register")
def register_provider(
    telegram_id: int,
    payload: ProviderRegistrationCreate,
    telegram_user: dict = Depends(verify_telegram_init_data),
):
    require_same_telegram_user(telegram_id, telegram_user)
    full_name = payload.full_name.strip()
    phone_number = payload.phone_number.strip()
    services = payload.services
    communes = payload.communes

    if len(full_name) < 3:
        raise HTTPException(status_code=400, detail="Nom complet trop court")
    if len(phone_number) < 8:
        raise HTTPException(status_code=400, detail="Numero WhatsApp invalide")
    if not services:
        raise HTTPException(status_code=400, detail="Choisis au moins un service")
    if not communes:
        raise HTTPException(status_code=400, detail="Choisis au moins une commune")
    available_services = active_services()
    if any(service not in available_services for service in services):
        raise HTTPException(status_code=400, detail="Service invalide")
    if any(commune not in COMMUNES for commune in communes):
        raise HTTPException(status_code=400, detail="Commune invalide")

    create_provider(
        telegram_id=telegram_id,
        phone_number=phone_number,
        full_name=full_name,
        services=services,
        communes=communes,
        language=payload.language,
    )
    # Vérification obligatoire à l'inscription (V5_MIGRATION_PLAN.md) : create_provider
    # remet toujours status="available" — la Mini App ne collecte pas encore les
    # documents d'identité (contrairement au bot Telegram, voir
    # telegram_bot/registration.py), mais un prestataire inscrit ici ne doit pas
    # pouvoir contourner la validation admin pour autant. Reste non-matchable comme
    # côté bot ; la collecte de documents via la Mini App est un chantier séparé.
    provider = row_to_dict(update_provider_status(telegram_id, "pending_verification"))
    provider["services"] = load_json_list(provider.get("services"))
    provider["communes"] = load_json_list(provider.get("communes"))
    provider["languages_spoken"] = load_json_list(provider.get("languages_spoken"))
    return {"status": "ok", "provider": provider}


@app.post("/api/provider/{telegram_id}/services")
def save_provider_services(
    telegram_id: int,
    payload: ServicesUpdate,
    telegram_user: dict = Depends(verify_telegram_init_data),
):
    require_same_telegram_user(telegram_id, telegram_user)
    provider = get_provider_by_telegram_id(telegram_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="Prestataire introuvable")

    available_services = active_services()
    invalid_services = [service for service in payload.services if service not in available_services]
    if invalid_services:
        raise HTTPException(status_code=400, detail="Service invalide")
    if not payload.services:
        raise HTTPException(status_code=400, detail="Choisis au moins un service")

    updated_provider = row_to_dict(update_provider_services(telegram_id, payload.services))
    updated_provider["services"] = load_json_list(updated_provider.get("services"))
    updated_provider["communes"] = load_json_list(updated_provider.get("communes"))
    updated_provider["languages_spoken"] = load_json_list(updated_provider.get("languages_spoken"))
    return {"status": "ok", "provider": updated_provider}


@app.post("/api/provider/{telegram_id}/service-requests")
def request_missing_service(
    telegram_id: int,
    payload: ServiceRequestCreate,
    telegram_user: dict = Depends(verify_telegram_init_data),
):
    require_same_telegram_user(telegram_id, telegram_user)
    provider = get_provider_by_telegram_id(telegram_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="Prestataire introuvable")

    service_name = payload.service_name.strip()
    description = payload.description.strip()
    if len(service_name) < 3:
        raise HTTPException(status_code=400, detail="Nom du service trop court")
    if len(description) < 10:
        raise HTTPException(status_code=400, detail="Description trop courte")

    request_id = create_service_request(telegram_id, service_name, description)
    service_requests = [row_to_dict(row) for row in get_provider_service_requests(telegram_id)]
    return {"status": "ok", "request_id": request_id, "service_requests": service_requests}


@app.post("/api/provider/{telegram_id}/status")
def save_provider_status(
    telegram_id: int,
    payload: StatusUpdate,
    telegram_user: dict = Depends(verify_telegram_init_data),
):
    require_same_telegram_user(telegram_id, telegram_user)
    provider = get_provider_by_telegram_id(telegram_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="Prestataire introuvable")
    if payload.status not in {"available", "offline"}:
        raise HTTPException(status_code=400, detail="Statut invalide")

    updated_provider = row_to_dict(update_provider_status(telegram_id, payload.status))
    updated_provider["services"] = load_json_list(updated_provider.get("services"))
    updated_provider["communes"] = load_json_list(updated_provider.get("communes"))
    updated_provider["languages_spoken"] = load_json_list(updated_provider.get("languages_spoken"))
    return {"status": "ok", "provider": updated_provider}


@app.post("/api/provider/{telegram_id}/missions/{mission_id}/start")
def start_provider_mission(
    telegram_id: int,
    mission_id: int,
    telegram_user: dict = Depends(verify_telegram_init_data),
):
    require_same_telegram_user(telegram_id, telegram_user)
    try:
        mission = compact_mission(start_mission(mission_id, telegram_id))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    return {"status": "ok", "mission": mission}


@app.post("/api/provider/{telegram_id}/missions/{mission_id}/finish")
def finish_provider_mission(
    telegram_id: int,
    mission_id: int,
    telegram_user: dict = Depends(verify_telegram_init_data),
):
    require_same_telegram_user(telegram_id, telegram_user)
    try:
        mission = compact_mission(finish_mission(mission_id, telegram_id))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    return {"status": "ok", "mission": mission}
