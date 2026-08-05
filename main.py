import asyncio
import html
import json
import os

import httpx
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    InputRichBlockDetails,
    InputRichBlockParagraph,
    InputRichBlockTable,
    InputRichMessage,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    RichBlockTableCell,
    WebAppInfo,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv
from aiogram.exceptions import TelegramBadRequest

from messages import get_message
from db import (
    accept_quote,
    create_mission,
    create_provider,
    create_quote,
    create_service_request,
    find_matching_providers,
    create_user,
    get_mission_by_id,
    get_admin_stats,
    get_all_providers,
    get_all_users,
    get_disputed_missions,
    get_active_services,
    get_provider_by_telegram_id,
    get_provider_missions,
    get_provider_service_requests,
    get_pending_service_requests,
    get_quote_by_id,
    get_service_request_by_id,
    get_recent_missions,
    get_user_by_telegram_id,
    get_user_missions,
    init_db,
    finish_mission,
    mark_quote_paid,
    mark_quote_paid_with_wallet,
    reject_quote,
    release_payment,
    reset_consecutive_ignored,
    set_provider_suspended,
    set_provider_verified,
    start_mission,
    update_consecutive_ignored,
    update_provider_language,
    update_provider_services,
    update_provider_status,
    update_service_request_status,
    update_user_language,
    update_user_name,
)


load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_TELEGRAM_ID = os.getenv("ADMIN_TELEGRAM_ID")
MINI_APP_URL = os.getenv("MINI_APP_URL")
BACKEND_BASE_URL = os.getenv("BACKEND_BASE_URL", "http://127.0.0.1:8000")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN manquant dans le fichier .env")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


_original_edit_text = Message.edit_text


async def _safe_edit_text(self, text, *args, **kwargs):
    try:
        return await _original_edit_text(self, text, *args, **kwargs)
    except TelegramBadRequest as exc:
        if "message is not modified" in str(exc).lower():
            return None
        raise


Message.edit_text = _safe_edit_text


def is_admin(telegram_id: int) -> bool:
    if not ADMIN_TELEGRAM_ID:
        return True
    return str(telegram_id) == ADMIN_TELEGRAM_ID


FALLBACK_SERVICES = {
    "service_plomberie": "🔧 Plomberie",
    "service_electricite": "⚡ Electricité",
    "service_climatisation": "❄️ Climatisation",
    "service_informatique": "💻 Informatique",
    "service_graphisme": "🎨 Graphisme",
    "service_coiffure": "✂️ Coiffure",
    "service_nettoyage": "🧹 Nettoyage",
    "service_jardinage": "🌿 Jardinage",
    "service_autre": "➕ Autre service",
}


def load_services():
    try:
        services = get_active_services("fr", include_icon=True)
        return services or FALLBACK_SERVICES
    except Exception:
        return FALLBACK_SERVICES


SERVICES = load_services()
SERVICE_CALLBACKS = list(SERVICES.keys())

COMMUNES = [
    ("Gombe", "commune_gombe"),
    ("Kinshasa", "commune_kinshasa"),
    ("Limete", "commune_limete"),
    ("Ngaliema", "commune_ngaliema"),
    ("Lemba", "commune_lemba"),
    ("Kalamu", "commune_kalamu"),
    ("Barumbu", "commune_barumbu"),
    ("Lingwala", "commune_lingwala"),
    ("Autre commune", "commune_autre"),
]

CURRENCIES = {
    "currency_usd": "USD",
    "currency_cdf": "CDF",
}
CURRENCY_CALLBACKS = list(CURRENCIES.keys())

STATUS_LABELS = {
    "pending": "En attente",
    "quoted": "Devis reçu",
    "confirmed": "Confirmée",
    "in_progress": "En cours",
    "awaiting_confirmation": "En attente confirmation client",
    "completed": "Terminée",
    "cancelled": "Annulée",
    "disputed": "Litige",
}

BADGE_LABELS = {
    "partner": "🏆 Partenaire",
    "expert": "🥇 Expert",
    "premium": "⭐ Premium",
    "verified": "✅ Vérifié",
}

PAYMENT_STATUS_LABELS = {
    "unpaid": "Non payé",
    "paid_escrow": "Sécurisé en escrow",
    "released": "Libéré",
    "refunded": "Remboursé",
}

BUTTON_LABELS = {
    "fr": {
        "client": "👤 Client",
        "provider": "🔧 Prestataire",
        "request_service": "🔍 Demander un service",
        "my_missions": "📋 Mes missions en cours",
        "history": "📜 Historique",
        "wallet": "👛 Mon Wallet",
        "profile": "👤 Mon profil",
        "help": "❓ Aide",
        "open_mini_app": "🚀 Ouvrir Nexis Hub",
        "dashboard": "📊 Mon tableau de bord",
        "provider_missions": "📋 Mes missions",
        "provider_wallet": "💰 Mon portefeuille",
        "availability": "⚙️ Disponibilité",
        "my_services": "🧰 Mes services",
        "missing_service": "➕ Service manquant",
        "support": "❓ Support",
        "urgent_yes": "🚨 Oui, c'est urgent",
        "urgent_no": "📅 Non, pas urgent",
        "back_services": "⬅️ Retour aux services",
        "back": "⬅️ Retour",
        "back_communes": "⬅️ Retour aux communes",
        "confirm_request": "✅ Confirmer la demande",
        "edit": "✏️ Modifier",
        "cancel": "❌ Annuler",
        "skip_photo": "➡️ Continuer sans photo",
        "finish_explanation": "✅ Terminer l'explication",
        "skip_rating": "➡️ Ne pas noter",
        "skip_comment": "➡️ Envoyer sans commentaire",
        "settings": "✏️ Modifier",
        "change_language": "🌐 Changer de langue",
        "change_name": "✏️ Modifier mon nom",
    },
    "ln": {
        "client": "👤 Client",
        "provider": "🔧 Mosali",
        "request_service": "🔍 Kosenga service",
        "my_missions": "📋 Misala na ngai",
        "history": "📜 Historique",
        "wallet": "👛 Wallet na ngai",
        "profile": "👤 Profil na ngai",
        "help": "❓ Lisungi",
        "open_mini_app": "🚀 Kofungola Nexis Hub",
        "dashboard": "📊 Tableau na ngai",
        "provider_missions": "📋 Misala na ngai",
        "provider_wallet": "💰 Portefeuille na ngai",
        "availability": "⚙️ Disponibilité",
        "my_services": "🧰 Services na ngai",
        "missing_service": "➕ Service ezangi",
        "support": "❓ Lisungi",
        "urgent_yes": "🚨 Ee, ezali urgent",
        "urgent_no": "📅 Te, urgent te",
        "back_services": "⬅️ Zonga na services",
        "back": "⬅️ Zonga",
        "back_communes": "⬅️ Zonga na communes",
        "confirm_request": "✅ Kondima demande",
        "edit": "✏️ Kobongisa",
        "cancel": "❌ Kolongola",
        "skip_photo": "➡️ Kokoba sans photo",
        "finish_explanation": "✅ Nasilisi kolimbola",
        "skip_rating": "➡️ Kopesa note te",
        "skip_comment": "➡️ Kotinda sans commentaire",
        "settings": "✏️ Kobongisa",
        "change_language": "🌐 Kobongola monoko",
        "change_name": "✏️ Kobongola kombo",
    },
    "en": {
        "client": "👤 Client",
        "provider": "🔧 Provider",
        "request_service": "🔍 Request a service",
        "my_missions": "📋 My active missions",
        "history": "📜 History",
        "wallet": "👛 My Wallet",
        "profile": "👤 My profile",
        "help": "❓ Help",
        "open_mini_app": "🚀 Open Nexis Hub",
        "dashboard": "📊 Dashboard",
        "provider_missions": "📋 My missions",
        "provider_wallet": "💰 My wallet",
        "availability": "⚙️ Availability",
        "my_services": "🧰 My services",
        "missing_service": "➕ Missing service",
        "support": "❓ Support",
        "urgent_yes": "🚨 Yes, urgent",
        "urgent_no": "📅 No, not urgent",
        "back_services": "⬅️ Back to services",
        "back": "⬅️ Back",
        "back_communes": "⬅️ Back to communes",
        "confirm_request": "✅ Confirm request",
        "edit": "✏️ Edit",
        "cancel": "❌ Cancel",
        "skip_photo": "➡️ Continue without photo",
        "finish_explanation": "✅ Finish explanation",
        "skip_rating": "➡️ Skip rating",
        "skip_comment": "➡️ Send without comment",
        "settings": "✏️ Edit",
        "change_language": "🌐 Change language",
        "change_name": "✏️ Edit my name",
    },
}


def button_label(key: str, lang: str = "fr") -> str:
    return BUTTON_LABELS.get(lang, BUTTON_LABELS["fr"]).get(key, BUTTON_LABELS["fr"][key])


def provider_trust_line(provider) -> str:
    if not provider["total_missions"]:
        return "🆕 Nouveau prestataire sur Nexis Hub"

    line = f"⭐ {provider['rating']:.1f}/5 ({provider['total_missions']} missions, {provider['success_rate']:.0f}% de réussite)"
    badge_label = BADGE_LABELS.get(provider["badge"])
    if badge_label:
        line += f" · {badge_label}"
    if provider["is_verified"]:
        line += " · ✅ Vérifié"
    return line


async def _safe_backend_call(coro):
    try:
        return await coro
    except Exception:
        return None


async def sync_user_to_backend(telegram_id: int, first_name: str | None = None, phone_number: str | None = None, language: str = "fr") -> dict:
    payload = {
        "telegram_id": telegram_id,
        "first_name": first_name or "Client",
        "phone_number": phone_number,
        "language": language,
    }
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.post(f"{BACKEND_BASE_URL}/api/bot/users", json=payload)
        response.raise_for_status()
        return response.json()


async def sync_mission_to_backend(telegram_id: int, mission_id: int, data: dict) -> dict:
    payload = {
        "telegram_id": telegram_id,
        "mission_id": mission_id,
        "service": data.get("service", "service_autre"),
        "commune": data.get("commune", "Autre commune"),
        "currency": data.get("currency", "USD"),
        "description": data.get("description", ""),
        "urgent": bool(data.get("urgent", False)),
    }
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.post(f"{BACKEND_BASE_URL}/api/bot/missions", json=payload)
        response.raise_for_status()
        return response.json()


async def sync_provider_to_backend(telegram_id: int, full_name: str, phone_number: str | None = None, services: list[str] | None = None, communes: list[str] | None = None, language: str = "fr") -> dict:
    payload = {
        "telegram_id": telegram_id,
        "full_name": full_name,
        "phone_number": phone_number,
        "services": services or [],
        "communes": communes or [],
        "language": language,
    }
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.post(f"{BACKEND_BASE_URL}/api/bot/providers", json=payload)
        response.raise_for_status()
        return response.json()


async def sync_quote_to_backend(mission_id: int, provider_telegram_id: int, amount: float, currency: str, delay_hours: int, message: str = "") -> dict:
    payload = {
        "mission_id": mission_id,
        "provider_telegram_id": provider_telegram_id,
        "amount": amount,
        "currency": currency,
        "delay_hours": delay_hours,
        "message": message,
    }
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.post(f"{BACKEND_BASE_URL}/api/bot/quotes", json=payload)
        response.raise_for_status()
        return response.json()


async def sync_review_to_backend(mission_id: int, client_telegram_id: int, rating: int, comment: str = "") -> dict:
    payload = {
        "mission_id": mission_id,
        "client_telegram_id": client_telegram_id,
        "rating": rating,
        "comment": comment,
    }
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.post(f"{BACKEND_BASE_URL}/api/bot/reviews", json=payload)
        response.raise_for_status()
        return response.json()


async def sync_quote_accept_to_backend(backend_quote_id: int) -> dict:
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.post(f"{BACKEND_BASE_URL}/api/bot/quotes/{backend_quote_id}/accept")
        response.raise_for_status()
        return response.json()


async def sync_quote_reject_to_backend(backend_quote_id: int) -> dict:
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.post(f"{BACKEND_BASE_URL}/api/bot/quotes/{backend_quote_id}/reject")
        response.raise_for_status()
        return response.json()


async def sync_provider_services_to_backend(telegram_id: int, services: list[str]) -> dict:
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.patch(f"{BACKEND_BASE_URL}/api/bot/providers/{telegram_id}/services", json={"services": services})
        response.raise_for_status()
        return response.json()


async def sync_provider_status_to_backend(telegram_id: int, status: str) -> dict:
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.patch(f"{BACKEND_BASE_URL}/api/bot/providers/{telegram_id}/status", json={"status": status})
        response.raise_for_status()
        return response.json()


async def sync_user_language_to_backend(telegram_id: int, language: str) -> dict:
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.patch(f"{BACKEND_BASE_URL}/api/bot/users/{telegram_id}/language", json={"language": language})
        response.raise_for_status()
        return response.json()


async def sync_user_name_to_backend(telegram_id: int, first_name: str) -> dict:
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.patch(f"{BACKEND_BASE_URL}/api/bot/users/{telegram_id}/name", json={"first_name": first_name})
        response.raise_for_status()
        return response.json()


async def sync_provider_language_to_backend(telegram_id: int, language: str) -> dict:
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.patch(f"{BACKEND_BASE_URL}/api/bot/providers/{telegram_id}/language", json={"language": language})
        response.raise_for_status()
        return response.json()


async def sync_provider_ignored_increment_to_backend(telegram_id: int) -> dict:
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.post(f"{BACKEND_BASE_URL}/api/bot/providers/{telegram_id}/ignored")
        response.raise_for_status()
        return response.json()


async def sync_provider_ignored_reset_to_backend(telegram_id: int) -> dict:
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.post(f"{BACKEND_BASE_URL}/api/bot/providers/{telegram_id}/ignored/reset")
        response.raise_for_status()
        return response.json()


async def fetch_backend_profile(telegram_id: int) -> dict | None:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{BACKEND_BASE_URL}/api/profile/{telegram_id}")
            response.raise_for_status()
            return response.json()
    except Exception:
        return None


async def load_profile_from_backend(telegram_id: int, fallback_user: dict | None = None) -> dict:
    backend_profile = await fetch_backend_profile(telegram_id)
    if backend_profile:
        return backend_profile
    return {"client": fallback_user or {"telegram_id": telegram_id, "first_name": "Client"}, "provider": None, "client_missions": [], "provider_missions": []}


async def fetch_backend_missions(telegram_id: int) -> list[dict]:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{BACKEND_BASE_URL}/api/profile/{telegram_id}")
            response.raise_for_status()
            payload = response.json()
            return payload.get("client_missions", [])
    except Exception:
        return []


async def sync_mission_status_to_backend(mission_id: int, status: str, payment_status: str | None = None) -> dict:
    payload = {"mission_id": mission_id, "status": status}
    if payment_status:
        payload["payment_status"] = payment_status
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.post(f"{BACKEND_BASE_URL}/api/bot/missions/status", json=payload)
        response.raise_for_status()
        return response.json()


async def sync_payment_to_backend(quote_id: int, payment_status: str, mission_id: int | None = None) -> dict:
    payload = {"quote_id": quote_id, "payment_status": payment_status}
    if mission_id is not None:
        payload["mission_id"] = mission_id
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.post(f"{BACKEND_BASE_URL}/api/bot/payments", json=payload)
        response.raise_for_status()
        return response.json()


async def persist_client_registration(telegram_id: int, first_name: str | None = None, phone_number: str | None = None, language: str = "fr") -> dict:
    local_user = create_user(
        telegram_id=telegram_id,
        phone_number=phone_number,
        first_name=first_name or "",
        language=language,
    )
    backend_result = await _safe_backend_call(
        sync_user_to_backend(
            telegram_id=telegram_id,
            first_name=first_name,
            phone_number=phone_number,
            language=language,
        )
    )
    return {"local": local_user, "backend": backend_result}


async def persist_mission_creation(telegram_id: int, mission_id: int, data: dict) -> dict:
    local_mission = get_mission_by_id(mission_id)
    if local_mission is None:
        local_mission = {"id": mission_id, "status": "created"}
    backend_result = await _safe_backend_call(sync_mission_to_backend(telegram_id, mission_id, data))
    return {
        "local": local_mission,
        "backend": backend_result,
    }


class MissionRequest(StatesGroup):
    description = State()


class ClientRegistration(StatesGroup):
    phone = State()


class ProviderRegistration(StatesGroup):
    phone = State()
    full_name = State()
    services = State()
    communes = State()


class ProviderServiceRequest(StatesGroup):
    service_name = State()
    description = State()


class ProviderServicesEdit(StatesGroup):
    services = State()


class QuoteCreation(StatesGroup):
    amount = State()
    currency = State()
    delay = State()
    message = State()


class RatingFlow(StatesGroup):
    rating = State()
    comment = State()


class ClientSettings(StatesGroup):
    name = State()


def clavier_contact(lang: str = "fr"):
    text = {
        "fr": "📱 Partager mon numéro WhatsApp",
        "ln": "📱 Kotinda numéro WhatsApp",
        "en": "📱 Share my WhatsApp number",
    }.get(lang, "📱 Partager mon numéro WhatsApp")
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=text, request_contact=True)],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def clavier_langue():
    builder = InlineKeyboardBuilder()
    builder.button(text="🇫🇷 Français", callback_data="lang_fr")
    builder.button(text="🇨🇩 Lingala", callback_data="lang_ln")
    builder.button(text="🇬🇧 English", callback_data="lang_en")
    builder.adjust(1)
    return builder.as_markup()


def clavier_admin_service_request(request_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Accepter", callback_data=f"admin_accept_service_{request_id}")
    builder.button(text="❌ Refuser", callback_data=f"admin_reject_service_{request_id}")
    builder.adjust(2)
    return builder.as_markup()


def clavier_admin_menu():
    builder = InlineKeyboardBuilder()
    builder.button(text="📊 Statistiques", callback_data="admin_stats")
    builder.button(text="🔧 Prestataires", callback_data="admin_providers")
    builder.button(text="📋 Missions", callback_data="admin_missions")
    builder.button(text="👥 Clients", callback_data="admin_clients")
    builder.button(text="⚠️ Litiges", callback_data="admin_disputes")
    builder.button(text="➕ Services proposés", callback_data="admin_service_requests")
    builder.adjust(2)
    return builder.as_markup()


def clavier_admin_provider(provider_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Vérifier", callback_data=f"admin_verify_provider_{provider_id}")
    builder.button(text="⛔ Suspendre", callback_data=f"admin_suspend_provider_{provider_id}")
    builder.button(text="♻️ Réactiver", callback_data=f"admin_unsuspend_provider_{provider_id}")
    builder.button(text="⬅️ Admin", callback_data="admin_home")
    builder.adjust(1)
    return builder.as_markup()


def clavier_profil(lang: str = "fr"):
    builder = InlineKeyboardBuilder()
    builder.button(text=button_label("client", lang), callback_data="profil_client")
    builder.button(text=button_label("provider", lang), callback_data="profil_prestataire")
    builder.adjust(2)
    return builder.as_markup()


def clavier_client(lang: str = "fr"):
    builder = InlineKeyboardBuilder()
    if MINI_APP_URL:
        builder.button(text=button_label("open_mini_app", lang), web_app=WebAppInfo(url=MINI_APP_URL))
    builder.button(text=button_label("request_service", lang), callback_data="client_demande")
    builder.button(text=button_label("my_missions", lang), callback_data="client_missions")
    builder.button(text=button_label("history", lang), callback_data="client_historique")
    builder.button(text=button_label("wallet", lang), callback_data="client_wallet")
    builder.button(text=button_label("profile", lang), callback_data="client_profil")
    builder.button(text=button_label("help", lang), callback_data="client_aide")
    builder.button(text=button_label("settings", lang), callback_data="client_parametres")
    builder.adjust(1)
    return builder.as_markup()


def clavier_parametres_client(lang: str = "fr"):
    builder = InlineKeyboardBuilder()
    builder.button(text=button_label("change_language", lang), callback_data="client_settings_language")
    builder.button(text=button_label("change_name", lang), callback_data="client_settings_name")
    builder.button(text=button_label("back", lang), callback_data="client_menu_from_settings")
    builder.adjust(1)
    return builder.as_markup()


def clavier_langue_parametres(lang: str = "fr"):
    builder = InlineKeyboardBuilder()
    builder.button(text="🇫🇷 Français", callback_data="settings_lang_fr")
    builder.button(text="🇨🇩 Lingala", callback_data="settings_lang_ln")
    builder.button(text="🇬🇧 English", callback_data="settings_lang_en")
    builder.button(text=button_label("back", lang), callback_data="client_parametres")
    builder.adjust(1)
    return builder.as_markup()


def clavier_prestataire(lang: str = "fr"):
    builder = InlineKeyboardBuilder()
    if MINI_APP_URL:
        builder.button(text=button_label("open_mini_app", lang), web_app=WebAppInfo(url=MINI_APP_URL))
    builder.button(text=button_label("dashboard", lang), callback_data="prest_dashboard")
    builder.button(text=button_label("provider_missions", lang), callback_data="prest_missions")
    builder.button(text=button_label("provider_wallet", lang), callback_data="prest_wallet")
    builder.button(text=button_label("profile", lang), callback_data="prest_profil")
    builder.button(text=button_label("my_services", lang), callback_data="prest_services")
    builder.button(text=button_label("missing_service", lang), callback_data="prest_missing_service")
    builder.button(text=button_label("availability", lang), callback_data="prest_dispo")
    builder.button(text=button_label("support", lang), callback_data="prest_support")
    builder.adjust(1)
    return builder.as_markup()


def clavier_disponibilite(status: str, lang: str = "fr"):
    builder = InlineKeyboardBuilder()
    if status == "available":
        builder.button(text=get_message("button_provider_unavailable", lang), callback_data="provider_status_offline")
    else:
        builder.button(text=get_message("button_provider_available", lang), callback_data="provider_status_available")
    builder.button(text=button_label("back", lang), callback_data="profil_prestataire")
    builder.adjust(1)
    return builder.as_markup()


def clavier_alerte_mission(mission_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Accepter", callback_data=f"provider_accept_{mission_id}")
    builder.button(text="❌ Passer", callback_data=f"provider_skip_{mission_id}")
    builder.adjust(2)
    return builder.as_markup()


def clavier_devis_client(quote_id: int, backend_quote_id: int | None = None):
    backend_suffix = backend_quote_id if backend_quote_id is not None else "-"
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Accepter ce devis", callback_data=f"client_accept_quote_{quote_id}:{backend_suffix}")
    builder.button(text="❌ Refuser", callback_data=f"client_reject_quote_{quote_id}:{backend_suffix}")
    builder.adjust(1)
    return builder.as_markup()


def _parse_quote_callback_ids(raw: str) -> tuple[int, int | None]:
    local_part, _, backend_part = raw.partition(":")
    backend_id = int(backend_part) if backend_part and backend_part != "-" else None
    return int(local_part), backend_id


def clavier_paiement(quote_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text="📱 Payer via Mobile Money", callback_data=f"pay_mobile_{quote_id}")
    builder.button(text="👛 Payer avec Wallet", callback_data=f"pay_wallet_{quote_id}")
    builder.button(text="⬅️ Plus tard", callback_data="profil_client")
    builder.adjust(1)
    return builder.as_markup()


def clavier_mission_prestataire(mission_id: int, action: str, lang: str = "fr"):
    builder = InlineKeyboardBuilder()
    if action == "start":
        builder.button(text=get_message("button_start_mission", lang), callback_data=f"mission_start_{mission_id}")
    elif action == "finish":
        builder.button(text=get_message("button_finish_mission", lang), callback_data=f"mission_finish_{mission_id}")
    builder.button(text=get_message("button_provider_menu", lang), callback_data="profil_prestataire")
    builder.adjust(1)
    return builder.as_markup()


def clavier_confirmation_client(mission_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Confirmer et libérer le paiement", callback_data=f"client_confirm_done_{mission_id}")
    builder.button(text="⚠️ Signaler un problème", callback_data=f"client_report_issue_{mission_id}")
    builder.adjust(1)
    return builder.as_markup()


def clavier_notation(mission_id: int, lang: str = "fr"):
    builder = InlineKeyboardBuilder()
    for i in range(1, 6):
        builder.button(text="⭐" * i, callback_data=f"rate_star_{mission_id}_{i}")
    builder.button(text=button_label("skip_rating", lang), callback_data=f"rate_skip_{mission_id}")
    builder.adjust(1)
    return builder.as_markup()


def clavier_notation_commentaire(mission_id: int, lang: str = "fr"):
    builder = InlineKeyboardBuilder()
    builder.button(text=button_label("skip_comment", lang), callback_data=f"rate_comment_skip_{mission_id}")
    builder.adjust(1)
    return builder.as_markup()


def clavier_services(lang: str = "fr"):
    builder = InlineKeyboardBuilder()
    for key, label in SERVICES.items():
        builder.button(text=label, callback_data=key)
    builder.button(text=button_label("back", lang), callback_data="profil_client")
    builder.adjust(2, 2, 2, 2, 1, 1)
    return builder.as_markup()


def clavier_services_prestataire(selected_services=None):
    selected_services = selected_services or []
    builder = InlineKeyboardBuilder()
    for key, label in SERVICES.items():
        prefix = "✅" if key in selected_services else "▫️"
        builder.button(text=f"{prefix} {label}", callback_data=f"provider_service_{key}")
    builder.button(text="➡️ Continuer", callback_data="provider_services_done")
    builder.adjust(1)
    return builder.as_markup()


def clavier_modifier_services(selected_services=None, lang: str = "fr"):
    selected_services = selected_services or []
    builder = InlineKeyboardBuilder()
    for key, label in SERVICES.items():
        prefix = "✅" if key in selected_services else "▫️"
        builder.button(text=f"{prefix} {label}", callback_data=f"edit_service_{key}")
    builder.button(text=get_message("button_save_services", lang), callback_data="edit_services_done")
    builder.button(text=get_message("button_propose_service", lang), callback_data="prest_missing_service")
    builder.button(text=button_label("back", lang), callback_data="profil_prestataire")
    builder.adjust(1)
    return builder.as_markup()


def clavier_services_actions(lang: str = "fr"):
    builder = InlineKeyboardBuilder()
    builder.button(text=get_message("button_edit_services", lang), callback_data="prest_edit_services")
    builder.button(text=get_message("button_propose_service", lang), callback_data="prest_missing_service")
    builder.button(text=button_label("back", lang), callback_data="profil_prestataire")
    builder.adjust(1)
    return builder.as_markup()


def clavier_communes_prestataire(selected_communes=None):
    selected_communes = selected_communes or []
    builder = InlineKeyboardBuilder()
    for label, callback_data in COMMUNES:
        prefix = "✅" if label in selected_communes else "▫️"
        builder.button(text=f"{prefix} {label}", callback_data=f"provider_{callback_data}")
    builder.button(text="✅ Terminer l'inscription", callback_data="provider_communes_done")
    builder.adjust(1)
    return builder.as_markup()


def clavier_urgence(lang: str = "fr"):
    builder = InlineKeyboardBuilder()
    builder.button(text=button_label("urgent_yes", lang), callback_data="urgent_oui")
    builder.button(text=button_label("urgent_no", lang), callback_data="urgent_non")
    builder.button(text=button_label("back_services", lang), callback_data="client_demande")
    builder.adjust(1)
    return builder.as_markup()


def clavier_communes(lang: str = "fr"):
    builder = InlineKeyboardBuilder()
    for label, callback_data in COMMUNES:
        builder.button(text=label, callback_data=callback_data)
    builder.button(text=button_label("back", lang), callback_data="client_demande")
    builder.adjust(2, 2, 2, 2, 1, 1)
    return builder.as_markup()


def clavier_devises(lang: str = "fr"):
    builder = InlineKeyboardBuilder()
    builder.button(text="💵 USD", callback_data="currency_usd")
    builder.button(text="🇨🇩 CDF", callback_data="currency_cdf")
    builder.button(text=button_label("back_communes", lang), callback_data="back_communes")
    builder.adjust(2, 1)
    return builder.as_markup()


def clavier_devises_devis():
    builder = InlineKeyboardBuilder()
    builder.button(text="💵 USD", callback_data="quote_currency_usd")
    builder.button(text="🇨🇩 CDF", callback_data="quote_currency_cdf")
    builder.adjust(2)
    return builder.as_markup()


def clavier_recapitulatif(lang: str = "fr"):
    builder = InlineKeyboardBuilder()
    builder.button(text=button_label("confirm_request", lang), callback_data="mission_confirmer")
    builder.button(text=button_label("edit", lang), callback_data="client_demande")
    builder.button(text=button_label("cancel", lang), callback_data="mission_annuler")
    builder.adjust(1)
    return builder.as_markup()


def clavier_photo_optionnelle(lang: str = "fr"):
    builder = InlineKeyboardBuilder()
    builder.button(text=button_label("skip_photo", lang), callback_data="mission_skip_photo")
    builder.adjust(1)
    return builder.as_markup()


def clavier_fin_explication(lang: str = "fr"):
    builder = InlineKeyboardBuilder()
    builder.button(text=button_label("finish_explanation", lang), callback_data="mission_media_done")
    builder.button(text=button_label("cancel", lang), callback_data="mission_annuler")
    builder.adjust(1)
    return builder.as_markup()


def clavier_mini_app(lang: str = "fr"):
    builder = InlineKeyboardBuilder()
    if MINI_APP_URL:
        builder.button(text=button_label("open_mini_app", lang), web_app=WebAppInfo(url=MINI_APP_URL))
    builder.adjust(1)
    return builder.as_markup()


def media_list(data: dict, key: str) -> list[str]:
    value = data.get(key)
    if not value:
        return []
    if isinstance(value, list):
        return value
    try:
        loaded = json.loads(value)
        return loaded if isinstance(loaded, list) else [value]
    except (TypeError, json.JSONDecodeError):
        return [value]


def format_recap(data: dict) -> str:
    lang = data.get("language", "fr")
    service = SERVICES.get(data.get("service"), "Service")
    yes_no = {"fr": ("Oui", "Non"), "ln": ("Iyo", "Te"), "en": ("Yes", "No")}
    yes_label, no_label = yes_no.get(lang, yes_no["fr"])
    urgence = yes_label if data.get("urgent") else no_label
    commune = data.get("commune", "Non précisée")
    currency = data.get("currency", "USD")
    description = html.escape(data.get("description", ""))
    photo_count = len(media_list(data, "photo_file_ids") or media_list(data, "photo_file_id"))
    voice_count = len(media_list(data, "voice_file_ids") or media_list(data, "voice_file_id"))
    photo = str(photo_count)
    voice = str(voice_count)

    base_summary = get_message(
        "mission_summary",
        lang,
        service=service,
        urgent=urgence,
        commune=commune,
        currency=currency,
        description=description,
    )
    if lang == "en":
        return base_summary.replace(
            f"Currency: <b>{currency}</b>\n",
            f"Currency: <b>{currency}</b>\nPhoto: <b>{photo}</b>\nVoice note: <b>{voice}</b>\n",
        )
    return base_summary.replace(
        f"Devise : <b>{currency}</b>\n",
        f"Devise : <b>{currency}</b>\nPhoto : <b>{photo}</b>\nNote vocale : <b>{voice}</b>\n",
    )


def format_mission_client(mission) -> str:
    service = SERVICES.get(mission["service"], mission["service"])
    status = STATUS_LABELS.get(mission["status"], mission["status"])
    payment_status = PAYMENT_STATUS_LABELS.get(mission["payment_status"], mission["payment_status"])
    provider = mission["provider_name"] or "Non attribué"
    return (
        f"NXH-{mission['id']:04d} | {service}\n"
        f"Commune : {mission['commune']} | Statut : {status}\n"
        f"Paiement : {payment_status} | Prestataire : {provider}"
    )


def format_mission_provider(mission) -> str:
    service = SERVICES.get(mission["service"], mission["service"])
    status = STATUS_LABELS.get(mission["status"], mission["status"])
    payment_status = PAYMENT_STATUS_LABELS.get(mission["payment_status"], mission["payment_status"])
    client = mission["client_name"] or "Client"
    return (
        f"NXH-{mission['id']:04d} | {service}\n"
        f"Client : {client} | Commune : {mission['commune']}\n"
        f"Statut : {status} | Paiement : {payment_status}"
    )


async def get_state_language(state: FSMContext) -> str:
    data = await state.get_data()
    return data.get("language", "fr")


async def get_user_language(telegram_id: int) -> str:
    backend_profile = await fetch_backend_profile(telegram_id)
    client_data = backend_profile.get("client") if backend_profile else None
    if client_data and client_data.get("language"):
        return client_data["language"]
    user = get_user_by_telegram_id(telegram_id)
    return user["language"] if user else "fr"


async def get_provider_language(telegram_id: int) -> str:
    backend_profile = await fetch_backend_profile(telegram_id)
    provider_data = backend_profile.get("provider") if backend_profile else None
    if provider_data and provider_data.get("language"):
        return provider_data["language"]
    provider = get_provider_by_telegram_id(telegram_id)
    if not provider:
        return "fr"
    try:
        languages = json.loads(provider["languages_spoken"] or '["fr"]')
    except json.JSONDecodeError:
        return "fr"
    return languages[0] if languages else "fr"


@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        get_message("welcome", "fr"),
        parse_mode="HTML",
        reply_markup=clavier_langue(),
    )


@dp.message(Command("app"))
async def cmd_app(message: Message):
    lang = await get_user_language(message.from_user.id)
    if not MINI_APP_URL:
        await message.answer(
            "La Mini App est prête côté code, mais il manque encore MINI_APP_URL dans le fichier .env."
        )
        return
    await message.answer(
        "Ouvre Nexis Hub ici :",
        reply_markup=clavier_mini_app(lang),
    )


@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("Accès admin refusé.")
        return

    stats = get_admin_stats()
    await message.answer(
        "🛠️ <b>Tableau admin NEXIS HUB</b>\n\n"
        f"👥 Clients : <b>{stats['users']}</b>\n"
        f"🔧 Prestataires : <b>{stats['providers']}</b>\n"
        f"📋 Missions : <b>{stats['missions']}</b>\n"
        f"➕ Services en attente : <b>{stats['pending_services']}</b>\n"
        f"⚠️ Litiges : <b>{stats['disputes']}</b>",
        parse_mode="HTML",
        reply_markup=clavier_admin_menu(),
    )


@dp.callback_query(F.data == "admin_home")
async def admin_home(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Accès admin refusé.", show_alert=True)
        return

    stats = get_admin_stats()
    await callback.message.edit_text(
        "🛠️ <b>Tableau admin NEXIS HUB</b>\n\n"
        f"👥 Clients : <b>{stats['users']}</b>\n"
        f"🔧 Prestataires : <b>{stats['providers']}</b>\n"
        f"📋 Missions : <b>{stats['missions']}</b>\n"
        f"➕ Services en attente : <b>{stats['pending_services']}</b>\n"
        f"⚠️ Litiges : <b>{stats['disputes']}</b>",
        parse_mode="HTML",
        reply_markup=clavier_admin_menu(),
    )
    await callback.answer()


@dp.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Accès admin refusé.", show_alert=True)
        return

    stats = get_admin_stats()
    await callback.message.edit_text(
        "📊 <b>Statistiques</b>\n\n"
        f"Clients : <b>{stats['users']}</b>\n"
        f"Prestataires : <b>{stats['providers']}</b>\n"
        f"Missions : <b>{stats['missions']}</b>\n"
        f"Services proposés en attente : <b>{stats['pending_services']}</b>\n"
        f"Litiges ouverts : <b>{stats['disputes']}</b>",
        parse_mode="HTML",
        reply_markup=clavier_admin_menu(),
    )
    await callback.answer()


@dp.callback_query(F.data == "admin_providers")
async def admin_providers(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Accès admin refusé.", show_alert=True)
        return

    providers = get_all_providers()
    if not providers:
        await callback.message.edit_text("Aucun prestataire enregistré.", reply_markup=clavier_admin_menu())
        await callback.answer()
        return

    await callback.message.edit_text("🔧 <b>Prestataires récents</b>", parse_mode="HTML", reply_markup=clavier_admin_menu())
    for provider in providers:
        await callback.message.answer(
            f"#{provider['id']} | <b>{html.escape(provider['full_name'])}</b>\n"
            f"Tél : {html.escape(provider['phone_number'])}\n"
            f"Badge : {provider['badge']} | Note : {provider['rating']}/5\n"
            f"Statut : {provider['status']} | Vérifié : {'Oui' if provider['is_verified'] else 'Non'}\n"
            f"Suspendu : {'Oui' if provider['is_suspended'] else 'Non'}",
            parse_mode="HTML",
            reply_markup=clavier_admin_provider(provider["id"]),
        )
    await callback.answer()


@dp.callback_query(F.data == "admin_missions")
async def admin_missions(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Accès admin refusé.", show_alert=True)
        return

    missions = get_recent_missions()
    if not missions:
        await callback.message.edit_text("Aucune mission enregistrée.", reply_markup=clavier_admin_menu())
        await callback.answer()
        return

    lines = []
    for mission in missions:
        lines.append(
            f"NXH-{mission['id']:04d} | {SERVICES.get(mission['service'], mission['service'])}\n"
            f"Client : {mission['client_name'] or 'Client'} | Prestataire : {mission['provider_name'] or 'Non attribué'}\n"
            f"Statut : {mission['status']} | Paiement : {mission['payment_status']}"
        )
    await callback.message.edit_text(
        "📋 <b>Missions récentes</b>\n\n" + "\n\n".join(html.escape(line) for line in lines),
        parse_mode="HTML",
        reply_markup=clavier_admin_menu(),
    )
    await callback.answer()


@dp.callback_query(F.data == "admin_clients")
async def admin_clients(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Accès admin refusé.", show_alert=True)
        return

    users = get_all_users()
    if not users:
        await callback.message.edit_text("Aucun client enregistré.", reply_markup=clavier_admin_menu())
        await callback.answer()
        return

    lines = [
        f"#{user['id']} | {user['first_name'] or 'Client'} | {user['phone_number']} | missions: {user['total_missions']}"
        for user in users
    ]
    await callback.message.edit_text(
        "👥 <b>Clients récents</b>\n\n" + "\n".join(html.escape(line) for line in lines),
        parse_mode="HTML",
        reply_markup=clavier_admin_menu(),
    )
    await callback.answer()


@dp.callback_query(F.data == "admin_disputes")
async def admin_disputes(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Accès admin refusé.", show_alert=True)
        return

    disputes = get_disputed_missions()
    if not disputes:
        await callback.message.edit_text("✅ Aucun litige ouvert.", reply_markup=clavier_admin_menu())
        await callback.answer()
        return

    lines = []
    for mission in disputes:
        lines.append(
            f"NXH-{mission['id']:04d} | {SERVICES.get(mission['service'], mission['service'])}\n"
            f"Client : {mission['client_name'] or 'Client'} | Prestataire : {mission['provider_name'] or 'Non attribué'}\n"
            f"Raison : {mission['dispute_reason'] or 'Non précisée'}"
        )
    await callback.message.edit_text(
        "⚠️ <b>Litiges</b>\n\n" + "\n\n".join(html.escape(line) for line in lines),
        parse_mode="HTML",
        reply_markup=clavier_admin_menu(),
    )
    await callback.answer()


@dp.callback_query(F.data == "admin_service_requests")
async def admin_service_requests(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Accès admin refusé.", show_alert=True)
        return

    requests = get_pending_service_requests()
    if not requests:
        await callback.message.edit_text("✅ Aucune proposition de service en attente.", reply_markup=clavier_admin_menu())
        await callback.answer()
        return

    await callback.message.edit_text(
        f"➕ <b>Services proposés</b>\n\n{len(requests)} proposition(s) en attente.",
        parse_mode="HTML",
        reply_markup=clavier_admin_menu(),
    )
    for request in requests:
        await callback.message.answer(
            "➕ <b>Service proposé</b>\n\n"
            f"Référence : <b>SRV-{request['id']:04d}</b>\n"
            f"Prestataire : <b>{html.escape(request['provider_name'])}</b>\n"
            f"Service : <b>{html.escape(request['service_name'])}</b>\n\n"
            f"{html.escape(request['description'])}",
            parse_mode="HTML",
            reply_markup=clavier_admin_service_request(request["id"]),
        )
    await callback.answer()


@dp.callback_query(F.data.startswith("admin_accept_service_"))
async def admin_accept_service(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Accès admin refusé.", show_alert=True)
        return

    request_id = int(callback.data.replace("admin_accept_service_", "", 1))
    request = get_service_request_by_id(request_id)
    if request is None:
        await callback.answer("Proposition introuvable.", show_alert=True)
        return

    update_service_request_status(request_id, "accepted", "Accepté par Nexis.")
    await callback.message.edit_text(
        "✅ <b>Service accepté</b>\n\n"
        f"Référence : <b>SRV-{request_id:04d}</b>\n"
        f"Service : <b>{html.escape(request['service_name'])}</b>",
        parse_mode="HTML",
    )
    await bot.send_message(
        request["provider_telegram_id"],
        "✅ <b>Votre proposition de service a été acceptée par Nexis.</b>\n\n"
        f"Service : <b>{html.escape(request['service_name'])}</b>\n\n"
        "Merci. Nexis pourra l'ajouter au catalogue des services proposés.",
        parse_mode="HTML",
    )
    await callback.answer("Service accepté")


@dp.callback_query(F.data.startswith("admin_verify_provider_"))
async def admin_verify_provider(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Accès admin refusé.", show_alert=True)
        return

    provider_id = int(callback.data.replace("admin_verify_provider_", "", 1))
    provider = set_provider_verified(provider_id, True)
    if provider is None:
        await callback.answer("Prestataire introuvable.", show_alert=True)
        return

    await callback.message.edit_text(
        f"✅ Prestataire vérifié : <b>{html.escape(provider['full_name'])}</b>",
        parse_mode="HTML",
        reply_markup=clavier_admin_menu(),
    )
    await bot.send_message(
        provider["telegram_id"],
        "✅ <b>Votre profil prestataire a été vérifié par Nexis.</b>\n\n"
        "Vous pouvez maintenant recevoir des demandes selon vos services et communes.",
        parse_mode="HTML",
    )
    await callback.answer("Prestataire vérifié")


@dp.callback_query(F.data.startswith("admin_suspend_provider_"))
async def admin_suspend_provider(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Accès admin refusé.", show_alert=True)
        return

    provider_id = int(callback.data.replace("admin_suspend_provider_", "", 1))
    provider = set_provider_suspended(provider_id, True)
    if provider is None:
        await callback.answer("Prestataire introuvable.", show_alert=True)
        return

    await callback.message.edit_text(
        f"⛔ Prestataire suspendu : <b>{html.escape(provider['full_name'])}</b>",
        parse_mode="HTML",
        reply_markup=clavier_admin_menu(),
    )
    await bot.send_message(
        provider["telegram_id"],
        "⛔ <b>Votre profil prestataire a été suspendu par Nexis.</b>\n\n"
        "Contactez le support si vous pensez qu'il s'agit d'une erreur.",
        parse_mode="HTML",
    )
    await callback.answer("Prestataire suspendu")


@dp.callback_query(F.data.startswith("admin_unsuspend_provider_"))
async def admin_unsuspend_provider(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Accès admin refusé.", show_alert=True)
        return

    provider_id = int(callback.data.replace("admin_unsuspend_provider_", "", 1))
    provider = set_provider_suspended(provider_id, False)
    if provider is None:
        await callback.answer("Prestataire introuvable.", show_alert=True)
        return

    await callback.message.edit_text(
        f"♻️ Prestataire réactivé : <b>{html.escape(provider['full_name'])}</b>",
        parse_mode="HTML",
        reply_markup=clavier_admin_menu(),
    )
    await bot.send_message(
        provider["telegram_id"],
        "♻️ <b>Votre profil prestataire a été réactivé par Nexis.</b>",
        parse_mode="HTML",
    )
    await callback.answer("Prestataire réactivé")


@dp.callback_query(F.data.startswith("admin_reject_service_"))
async def admin_reject_service(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Accès admin refusé.", show_alert=True)
        return

    request_id = int(callback.data.replace("admin_reject_service_", "", 1))
    request = get_service_request_by_id(request_id)
    if request is None:
        await callback.answer("Proposition introuvable.", show_alert=True)
        return

    update_service_request_status(request_id, "rejected", "Service non pris en charge pour le moment.")
    await callback.message.edit_text(
        "❌ <b>Service refusé</b>\n\n"
        f"Référence : <b>SRV-{request_id:04d}</b>\n"
        f"Service : <b>{html.escape(request['service_name'])}</b>",
        parse_mode="HTML",
    )
    await bot.send_message(
        request["provider_telegram_id"],
        "❌ <b>Votre proposition de service a été examinée.</b>\n\n"
        f"Service : <b>{html.escape(request['service_name'])}</b>\n\n"
        "Pour le moment, Nexis ne peut pas prendre en charge ce service.",
        parse_mode="HTML",
    )
    await callback.answer("Service refusé")


@dp.callback_query(F.data == "lang_fr")
async def langue_fr(callback: CallbackQuery, state: FSMContext):
    await state.update_data(language="fr")
    update_user_language(callback.from_user.id, "fr")
    update_provider_language(callback.from_user.id, "fr")
    await _safe_backend_call(sync_user_language_to_backend(callback.from_user.id, "fr"))
    await _safe_backend_call(sync_provider_language_to_backend(callback.from_user.id, "fr"))
    await callback.message.edit_text(
        f"🇫🇷 Vous avez choisi le <b>Français</b>.\n\n{get_message('choose_profile', 'fr')}",
        parse_mode="HTML",
        reply_markup=clavier_profil("fr"),
    )
    await callback.answer()


@dp.callback_query(F.data == "lang_ln")
async def langue_ln(callback: CallbackQuery, state: FSMContext):
    await state.update_data(language="ln")
    update_user_language(callback.from_user.id, "ln")
    update_provider_language(callback.from_user.id, "ln")
    await _safe_backend_call(sync_user_language_to_backend(callback.from_user.id, "ln"))
    await _safe_backend_call(sync_provider_language_to_backend(callback.from_user.id, "ln"))
    await callback.message.edit_text(
        f"🇨🇩 Oponi <b>Lingala</b>.\n\n{get_message('choose_profile', 'ln')}",
        parse_mode="HTML",
        reply_markup=clavier_profil("ln"),
    )
    await callback.answer()


@dp.callback_query(F.data == "lang_en")
async def langue_en(callback: CallbackQuery, state: FSMContext):
    await state.update_data(language="en")
    update_user_language(callback.from_user.id, "en")
    update_provider_language(callback.from_user.id, "en")
    await _safe_backend_call(sync_user_language_to_backend(callback.from_user.id, "en"))
    await _safe_backend_call(sync_provider_language_to_backend(callback.from_user.id, "en"))
    await callback.message.edit_text(
        f"🇬🇧 You chose <b>English</b>.\n\n{get_message('choose_profile', 'en')}",
        parse_mode="HTML",
        reply_markup=clavier_profil("en"),
    )
    await callback.answer()


@dp.callback_query(F.data == "profil_client")
async def profil_client(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user = get_user_by_telegram_id(callback.from_user.id)
    lang = data.get("language") or (user["language"] if user else "fr")
    if user is None:
        await state.set_state(ClientRegistration.phone)
        await state.update_data(language=lang)
        await callback.message.answer(
            get_message("ask_client_phone", lang),
            reply_markup=clavier_contact(lang),
        )
        await callback.answer()
        return

    await state.clear()
    prenom = html.escape(callback.from_user.first_name or "Client")
    await callback.message.edit_text(
        get_message("client_menu", lang, prenom=prenom),
        parse_mode="HTML",
        reply_markup=clavier_client(lang),
    )
    await callback.answer()


@dp.message(ClientRegistration.phone)
async def enregistrer_client(message: Message, state: FSMContext):
    phone_number = message.contact.phone_number if message.contact else (message.text or "").strip()
    lang = await get_state_language(state)
    if not phone_number:
        await message.answer(get_message("phone_required", lang))
        return

    data = await state.get_data()
    await persist_client_registration(
        telegram_id=message.from_user.id,
        first_name=message.from_user.first_name or "",
        phone_number=phone_number,
        language=data.get("language", "fr"),
    )
    await state.clear()
    prenom = html.escape(message.from_user.first_name or "Client")
    lang = data.get("language", "fr")
    await message.answer(
        get_message("client_registered", lang),
        reply_markup=ReplyKeyboardRemove(),
    )
    await message.answer(
        get_message("client_menu", lang, prenom=prenom),
        parse_mode="HTML",
        reply_markup=clavier_client(lang),
    )


@dp.callback_query(F.data == "profil_prestataire")
async def profil_prestataire(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    provider = get_provider_by_telegram_id(callback.from_user.id)
    lang = data.get("language") or await get_provider_language(callback.from_user.id)
    if provider is None:
        await state.set_state(ProviderRegistration.phone)
        await state.update_data(language=lang)
        await callback.message.answer(
            get_message("ask_provider_phone", lang),
            reply_markup=clavier_contact(lang),
        )
        await callback.answer()
        return

    await state.clear()
    prenom = html.escape(provider["full_name"] or callback.from_user.first_name or "Prestataire")
    statut = "🟢 Disponible" if provider["status"] == "available" else "🔴 Indisponible"
    await callback.message.edit_text(
        get_message(
            "provider_menu",
            lang,
            prenom=prenom,
            badge=provider["badge"],
            note=f"{provider['rating']:.1f}",
            missions=provider["total_missions"],
            statut=statut,
        ),
        parse_mode="HTML",
        reply_markup=clavier_prestataire(lang),
    )
    await callback.answer()


@dp.message(ProviderRegistration.phone)
async def enregistrer_tel_prestataire(message: Message, state: FSMContext):
    phone_number = message.contact.phone_number if message.contact else (message.text or "").strip()
    lang = await get_state_language(state)
    if not phone_number:
        await message.answer(get_message("phone_required", lang))
        return

    await state.update_data(provider_phone=phone_number)
    await state.set_state(ProviderRegistration.full_name)
    await message.answer(
        get_message("provider_phone_saved", lang),
        reply_markup=ReplyKeyboardRemove(),
    )


@dp.message(ProviderRegistration.full_name)
async def enregistrer_nom_prestataire(message: Message, state: FSMContext):
    full_name = (message.text or "").strip()
    if len(full_name) < 2:
        await message.answer("Veuillez envoyer un nom complet valide.")
        return

    await state.update_data(provider_full_name=full_name, provider_services=[])
    lang = await get_state_language(state)
    await state.set_state(ProviderRegistration.services)
    await message.answer(
        get_message("provider_choose_services", lang),
        reply_markup=clavier_services_prestataire(),
    )


@dp.callback_query(ProviderRegistration.services, F.data.startswith("provider_service_"))
async def choisir_service_prestataire(callback: CallbackQuery, state: FSMContext):
    service_key = callback.data.replace("provider_service_", "", 1)
    data = await state.get_data()
    selected = data.get("provider_services", [])

    if service_key in selected:
        selected.remove(service_key)
    else:
        selected.append(service_key)

    await state.update_data(provider_services=selected)
    await callback.message.edit_reply_markup(reply_markup=clavier_services_prestataire(selected))
    await callback.answer()


@dp.callback_query(ProviderRegistration.services, F.data == "provider_services_done")
async def terminer_services_prestataire(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data.get("provider_services"):
        await callback.answer(get_message("choose_one_service", data.get("language", "fr")), show_alert=True)
        return

    await state.update_data(provider_communes=[])
    await state.set_state(ProviderRegistration.communes)
    await callback.message.edit_text(
        get_message("provider_choose_communes", data.get("language", "fr")),
        reply_markup=clavier_communes_prestataire(),
    )
    await callback.answer()


@dp.callback_query(ProviderRegistration.communes, F.data.startswith("provider_commune_"))
async def choisir_commune_prestataire(callback: CallbackQuery, state: FSMContext):
    commune_callback = callback.data.replace("provider_", "", 1)
    commune = next((label for label, data in COMMUNES if data == commune_callback), "Autre commune")
    data = await state.get_data()
    selected = data.get("provider_communes", [])

    if commune in selected:
        selected.remove(commune)
    else:
        selected.append(commune)

    await state.update_data(provider_communes=selected)
    await callback.message.edit_reply_markup(reply_markup=clavier_communes_prestataire(selected))
    await callback.answer()


@dp.callback_query(ProviderRegistration.communes, F.data == "provider_communes_done")
async def terminer_inscription_prestataire(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data.get("provider_communes"):
        await callback.answer(get_message("choose_one_commune", data.get("language", "fr")), show_alert=True)
        return

    provider = create_provider(
        telegram_id=callback.from_user.id,
        phone_number=data["provider_phone"],
        full_name=data["provider_full_name"],
        services=data["provider_services"],
        communes=data["provider_communes"],
        language=data.get("language", "fr"),
    )
    await _safe_backend_call(
        sync_provider_to_backend(
            telegram_id=callback.from_user.id,
            full_name=data["provider_full_name"],
            phone_number=data["provider_phone"],
            services=data["provider_services"],
            communes=data["provider_communes"],
            language=data.get("language", "fr"),
        )
    )
    await state.clear()
    await callback.message.edit_text(
        get_message(
            "provider_registered",
            data.get("language", "fr"),
            status=provider["status"],
            badge=provider["badge"],
        ),
        parse_mode="HTML",
        reply_markup=clavier_prestataire(data.get("language", "fr")),
    )
    await callback.answer(get_message("toast_registration_complete", data.get("language", "fr")))


@dp.callback_query(F.data == "prest_dispo")
async def disponibilite_prestataire(callback: CallbackQuery):
    provider = get_provider_by_telegram_id(callback.from_user.id)
    lang = await get_provider_language(callback.from_user.id)
    if provider is None:
        await callback.answer(get_message("provider_profile_required", lang), show_alert=True)
        return

    status_label = get_message(
        "provider_status_available" if provider["status"] == "available" else "provider_status_offline",
        lang,
    )
    await callback.message.edit_text(
        get_message("provider_availability_title", lang, status=status_label),
        parse_mode="HTML",
        reply_markup=clavier_disponibilite(provider["status"], lang),
    )
    await callback.answer()


@dp.callback_query(F.data.in_(["provider_status_available", "provider_status_offline"]))
async def changer_disponibilite(callback: CallbackQuery):
    status = "available" if callback.data == "provider_status_available" else "offline"
    update_provider_status(callback.from_user.id, status)
    await _safe_backend_call(sync_provider_status_to_backend(callback.from_user.id, status))
    if status == "available":
        reset_consecutive_ignored(callback.from_user.id)
        await _safe_backend_call(sync_provider_ignored_reset_to_backend(callback.from_user.id))
    provider_lang = await get_provider_language(callback.from_user.id)
    status_label = get_message(
        "provider_status_available" if status == "available" else "provider_status_offline",
        provider_lang,
    )
    await callback.message.edit_text(
        get_message("provider_availability_updated", provider_lang, status=status_label),
        parse_mode="HTML",
        reply_markup=clavier_disponibilite(status, provider_lang),
    )
    await callback.answer(get_message("toast_status_updated", provider_lang))


@dp.callback_query(F.data == "prest_services")
async def afficher_services_prestataire(callback: CallbackQuery):
    provider = get_provider_by_telegram_id(callback.from_user.id)
    lang = await get_provider_language(callback.from_user.id)
    if provider is None:
        await callback.answer(get_message("provider_profile_required", lang), show_alert=True)
        return

    try:
        selected_services = json.loads(provider["services"] or "[]")
    except json.JSONDecodeError:
        selected_services = []

    service_labels = [SERVICES.get(service, service) for service in selected_services]
    requests = get_provider_service_requests(callback.from_user.id)
    request_lines = [
        f"SRV-{request['id']:04d} | {html.escape(request['service_name'])} | {request['status']}"
        for request in requests
    ]

    text = (
        get_message("provider_services_title", lang)
        + "\n\n"
        + get_message("provider_active_services", lang)
        + "\n"
        + ("\n".join(f"• {label}" for label in service_labels) if service_labels else get_message("provider_no_services", lang))
    )
    if request_lines:
        text += "\n\n" + get_message("provider_suggested_services", lang) + "\n" + "\n".join(request_lines)

    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=clavier_services_actions(lang),
    )
    await callback.answer()


@dp.callback_query(F.data == "prest_edit_services")
async def modifier_services_prestataire(callback: CallbackQuery, state: FSMContext):
    provider = get_provider_by_telegram_id(callback.from_user.id)
    lang = await get_provider_language(callback.from_user.id)
    if provider is None:
        await callback.answer(get_message("provider_profile_required", lang), show_alert=True)
        return

    try:
        selected_services = json.loads(provider["services"] or "[]")
    except json.JSONDecodeError:
        selected_services = []

    await state.set_state(ProviderServicesEdit.services)
    await state.update_data(provider_services_edit=selected_services)
    await callback.message.edit_text(
        get_message("provider_edit_services", lang),
        parse_mode="HTML",
        reply_markup=clavier_modifier_services(selected_services, lang),
    )
    await callback.answer()


@dp.callback_query(ProviderServicesEdit.services, F.data.startswith("edit_service_"))
async def choisir_service_modification(callback: CallbackQuery, state: FSMContext):
    service_key = callback.data.replace("edit_service_", "", 1)
    data = await state.get_data()
    selected = data.get("provider_services_edit", [])

    if service_key in selected:
        selected.remove(service_key)
    else:
        selected.append(service_key)

    await state.update_data(provider_services_edit=selected)
    lang = await get_provider_language(callback.from_user.id)
    await callback.message.edit_reply_markup(reply_markup=clavier_modifier_services(selected, lang))
    await callback.answer()


@dp.callback_query(ProviderServicesEdit.services, F.data == "edit_services_done")
async def enregistrer_services_modifies(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected = data.get("provider_services_edit", [])
    provider_lang = await get_provider_language(callback.from_user.id)
    if not selected:
        await callback.answer(get_message("provider_select_service", provider_lang), show_alert=True)
        return

    update_provider_services(callback.from_user.id, selected)
    await _safe_backend_call(sync_provider_services_to_backend(callback.from_user.id, selected))
    await state.clear()
    service_labels = [SERVICES.get(service, service) for service in selected]
    await callback.message.edit_text(
        get_message("provider_services_updated", provider_lang)
        + "\n\n"
        + "\n".join(f"• {label}" for label in service_labels),
        parse_mode="HTML",
        reply_markup=clavier_prestataire(provider_lang),
    )
    await callback.answer(get_message("toast_services_saved", provider_lang))


@dp.callback_query(F.data == "prest_missing_service")
async def proposer_service_manquant(callback: CallbackQuery, state: FSMContext):
    provider = get_provider_by_telegram_id(callback.from_user.id)
    lang = await get_provider_language(callback.from_user.id)
    if provider is None:
        await callback.answer(get_message("provider_profile_required", lang), show_alert=True)
        return

    await state.clear()
    await state.set_state(ProviderServiceRequest.service_name)
    await callback.message.edit_text(
        get_message("provider_missing_service_prompt", lang),
        parse_mode="HTML",
    )
    await callback.answer()


@dp.message(ProviderServiceRequest.service_name)
async def recevoir_nom_service_manquant(message: Message, state: FSMContext):
    service_name = (message.text or "").strip()
    lang = await get_provider_language(message.from_user.id)
    if len(service_name) < 3:
        await message.answer(get_message("provider_missing_service_name_invalid", lang))
        return

    await state.update_data(missing_service_name=service_name)
    await state.set_state(ProviderServiceRequest.description)
    await message.answer(
        get_message("provider_missing_service_description_prompt", lang)
    )


@dp.message(ProviderServiceRequest.description)
async def recevoir_description_service_manquant(message: Message, state: FSMContext):
    description = (message.text or "").strip()
    lang = await get_provider_language(message.from_user.id)
    if len(description) < 10:
        await message.answer(get_message("provider_missing_service_description_invalid", lang))
        return

    data = await state.get_data()
    request_id = create_service_request(
        telegram_id=message.from_user.id,
        service_name=data["missing_service_name"],
        description=description,
    )
    await state.clear()
    await message.answer(
        get_message(
            "provider_missing_service_created",
            lang,
            reference=f"SRV-{request_id:04d}",
            service=html.escape(data["missing_service_name"]),
        ),
        parse_mode="HTML",
        reply_markup=clavier_prestataire(lang),
    )


@dp.callback_query(F.data == "client_demande")
async def client_demande(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = data.get("language") or await get_user_language(callback.from_user.id)
    await state.clear()
    await state.update_data(language=lang)
    await callback.message.edit_text(
        get_message("choose_service", lang),
        parse_mode="HTML",
        reply_markup=clavier_services(lang),
    )
    await callback.answer()


@dp.callback_query(F.data.in_(SERVICE_CALLBACKS))
async def service_selectionne(callback: CallbackQuery, state: FSMContext):
    await state.update_data(service=callback.data)
    lang = await get_state_language(state)
    service_choisi = SERVICES.get(callback.data, "Service")
    await callback.message.edit_text(
        get_message("is_urgent", lang, service=service_choisi),
        parse_mode="HTML",
        reply_markup=clavier_urgence(lang),
    )
    await callback.answer()


@dp.callback_query(F.data.in_(["urgent_oui", "urgent_non"]))
async def urgence_selectionnee(callback: CallbackQuery, state: FSMContext):
    await state.update_data(urgent=callback.data == "urgent_oui")
    lang = await get_state_language(state)
    await callback.message.edit_text(
        get_message("choose_commune", lang),
        parse_mode="HTML",
        reply_markup=clavier_communes(lang),
    )
    await callback.answer()


@dp.callback_query(F.data == "back_communes")
async def retour_communes(callback: CallbackQuery):
    lang = await get_user_language(callback.from_user.id)
    await callback.message.edit_text(
        get_message("choose_commune", lang),
        parse_mode="HTML",
        reply_markup=clavier_communes(lang),
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("commune_"))
async def commune_selectionnee(callback: CallbackQuery, state: FSMContext):
    commune = next((label for label, data in COMMUNES if data == callback.data), "Autre commune")
    await state.update_data(commune=commune)
    lang = await get_state_language(state)
    await callback.message.edit_text(
        get_message("choose_currency", lang),
        parse_mode="HTML",
        reply_markup=clavier_devises(lang),
    )
    await callback.answer()


@dp.callback_query(F.data.in_(CURRENCY_CALLBACKS))
async def devise_selectionnee(callback: CallbackQuery, state: FSMContext):
    await state.update_data(currency=CURRENCIES[callback.data])
    lang = await get_state_language(state)
    await state.set_state(MissionRequest.description)
    await state.update_data(description_parts=[], photo_file_ids=[], voice_file_ids=[])
    await callback.message.edit_text(
        get_message("describe_problem", lang),
        parse_mode="HTML",
        reply_markup=clavier_fin_explication(lang),
    )
    await callback.answer()


@dp.message(MissionRequest.description)
async def description_recue(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("language", "fr")
    description_parts = data.get("description_parts", [])
    photo_file_ids = data.get("photo_file_ids", [])
    voice_file_ids = data.get("voice_file_ids", [])

    if message.voice:
        voice_file_ids.append(message.voice.file_id)
        feedback = get_message("media_voice_added", lang, count=len(voice_file_ids))
    elif message.photo:
        photo_file_ids.append(message.photo[-1].file_id)
        feedback = get_message("media_photo_added", lang, count=len(photo_file_ids))
    elif message.text:
        description_parts.append(message.text.strip())
        feedback = get_message("media_text_added", lang)
    else:
        await message.answer(
            get_message("media_invalid", lang),
            reply_markup=clavier_fin_explication(lang),
        )
        return

    await state.update_data(
        description_parts=description_parts,
        photo_file_ids=photo_file_ids,
        voice_file_ids=voice_file_ids,
        description="\n".join(description_parts) if description_parts else "Explication envoyée en média par le client.",
        photo_file_id=json.dumps(photo_file_ids) if photo_file_ids else None,
        voice_file_id=json.dumps(voice_file_ids) if voice_file_ids else None,
    )
    await message.answer(
        f"{feedback}\n\n{get_message('media_more_or_finish', lang)}",
        reply_markup=clavier_fin_explication(lang),
    )


@dp.callback_query(MissionRequest.description, F.data == "mission_media_done")
async def explication_terminee(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    description_parts = data.get("description_parts", [])
    photo_file_ids = data.get("photo_file_ids", [])
    voice_file_ids = data.get("voice_file_ids", [])

    if not description_parts and not photo_file_ids and not voice_file_ids:
        await callback.answer(
            get_message("media_required_alert", data.get("language", "fr")),
            show_alert=True,
        )
        return

    await state.update_data(
        description="\n".join(description_parts) if description_parts else "Explication envoyée en média par le client.",
        photo_file_id=json.dumps(photo_file_ids) if photo_file_ids else None,
        voice_file_id=json.dumps(voice_file_ids) if voice_file_ids else None,
    )
    data = await state.get_data()
    await state.clear()
    await state.update_data(**data)
    await callback.message.edit_text(
        format_recap(data),
        parse_mode="HTML",
        reply_markup=clavier_recapitulatif(data.get("language", "fr")),
    )
    await callback.answer()


@dp.callback_query(F.data == "mission_confirmer")
async def mission_confirmer(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    mission_id = create_mission(callback.from_user.id, data)
    await persist_mission_creation(callback.from_user.id, mission_id, data)
    matching_providers = find_matching_providers(data["service"], data["commune"])

    for provider in matching_providers[:3]:
        await bot.send_message(
            provider["telegram_id"],
            get_message(
                "new_mission_alert",
                "fr",
                mission_id=mission_id,
                service=SERVICES.get(data["service"], data["service"]),
                commune=html.escape(data["commune"]),
                urgent="Oui" if data.get("urgent") else "Non",
            )
            + f"\n\n{html.escape(data['description'])}",
            parse_mode="HTML",
            reply_markup=clavier_alerte_mission(mission_id),
        )
        for photo_file_id in media_list(data, "photo_file_ids") or media_list(data, "photo_file_id"):
            await bot.send_photo(
                provider["telegram_id"],
                photo_file_id,
                caption=f"📷 Photo liée à la mission NXH-{mission_id:04d}",
            )
        for voice_file_id in media_list(data, "voice_file_ids") or media_list(data, "voice_file_id"):
            await bot.send_voice(
                provider["telegram_id"],
                voice_file_id,
                caption=f"🎙️ Note vocale liée à la mission NXH-{mission_id:04d}",
            )

    await state.clear()
    client_lang = data.get("language", "fr")
    matching_text = (
        get_message("matching_providers_notified", client_lang, count=len(matching_providers[:3]))
        if matching_providers
        else get_message("matching_no_providers", client_lang)
    )
    await callback.message.edit_text(
        get_message(
            "mission_saved",
            client_lang,
            mission_id=mission_id,
            matching_text=matching_text,
        ),
        parse_mode="HTML",
        reply_markup=clavier_client(data.get("language", "fr")),
    )
    print("Nouvelle demande client:", data)
    await callback.answer(get_message("toast_request_confirmed", client_lang))


@dp.callback_query(F.data.startswith("provider_accept_"))
async def accepter_mission_prestataire(callback: CallbackQuery, state: FSMContext):
    mission_id = int(callback.data.replace("provider_accept_", "", 1))
    mission = get_mission_by_id(mission_id)
    provider_lang = await get_provider_language(callback.from_user.id)
    if mission is None:
        await callback.answer(get_message("provider_mission_not_found", provider_lang), show_alert=True)
        return

    await state.clear()
    await state.set_state(QuoteCreation.amount)
    await state.update_data(quote_mission_id=mission_id)
    await callback.message.edit_text(
        get_message("quote_amount_prompt", provider_lang, mission_id=mission_id),
        parse_mode="HTML",
    )
    await callback.answer(get_message("toast_mission_accepted", provider_lang))


@dp.message(QuoteCreation.amount)
async def devis_montant_recu(message: Message, state: FSMContext):
    lang = await get_provider_language(message.from_user.id)
    raw_amount = (message.text or "").replace(",", ".").strip()
    try:
        amount = float(raw_amount)
    except ValueError:
        await message.answer(get_message("quote_amount_invalid", lang))
        return

    if amount <= 0:
        await message.answer(get_message("quote_amount_positive", lang))
        return

    await state.update_data(quote_amount=amount)
    await state.set_state(QuoteCreation.currency)
    await message.answer(
        get_message("quote_currency_prompt", lang),
        reply_markup=clavier_devises_devis(),
    )


@dp.callback_query(QuoteCreation.currency, F.data.in_(["quote_currency_usd", "quote_currency_cdf"]))
async def devis_devise_recue(callback: CallbackQuery, state: FSMContext):
    lang = await get_provider_language(callback.from_user.id)
    currency = "USD" if callback.data == "quote_currency_usd" else "CDF"
    await state.update_data(quote_currency=currency)
    await state.set_state(QuoteCreation.delay)
    await callback.message.edit_text(
        get_message("quote_delay_prompt", lang),
        parse_mode="HTML",
    )
    await callback.answer()


@dp.message(QuoteCreation.delay)
async def devis_delai_recu(message: Message, state: FSMContext):
    lang = await get_provider_language(message.from_user.id)
    raw_delay = (message.text or "").strip()
    if not raw_delay.isdigit():
        await message.answer(get_message("quote_delay_invalid", lang))
        return

    delay_hours = int(raw_delay)
    if delay_hours <= 0:
        await message.answer(get_message("quote_delay_positive", lang))
        return

    await state.update_data(quote_delay_hours=delay_hours)
    await state.set_state(QuoteCreation.message)
    await message.answer(
        get_message("quote_message_prompt", lang),
        parse_mode="HTML",
    )


@dp.message(QuoteCreation.message)
async def devis_message_recu(message: Message, state: FSMContext):
    data = await state.get_data()
    provider = get_provider_by_telegram_id(message.from_user.id)
    mission = get_mission_by_id(data["quote_mission_id"])
    provider_lang = await get_provider_language(message.from_user.id)

    if provider is None or mission is None:
        await state.clear()
        await message.answer(get_message("quote_create_failed", provider_lang))
        return

    quote_message = (message.text or "").strip()
    if quote_message == "-":
        quote_message = ""

    quote_id = create_quote(
        mission_id=data["quote_mission_id"],
        provider_telegram_id=message.from_user.id,
        amount=data["quote_amount"],
        currency=data["quote_currency"],
        delay_hours=data["quote_delay_hours"],
        message=quote_message,
    )
    reset_consecutive_ignored(message.from_user.id)
    await _safe_backend_call(sync_provider_ignored_reset_to_backend(message.from_user.id))

    backend_quote = await _safe_backend_call(
        sync_quote_to_backend(
            mission_id=data["quote_mission_id"],
            provider_telegram_id=message.from_user.id,
            amount=data["quote_amount"],
            currency=data["quote_currency"],
            delay_hours=data["quote_delay_hours"],
            message=quote_message,
        )
    )
    backend_quote_id = backend_quote["quote"]["id"] if backend_quote else None

    client_lang = await get_user_language(mission["client_telegram_id"])
    no_message_by_lang = {"fr": "Aucun message", "ln": "Message te", "en": "No message"}
    await bot.send_message(
        mission["client_telegram_id"],
        get_message(
            "new_quote_received_client",
            client_lang,
            mission_id=data["quote_mission_id"],
            prestataire=html.escape(provider["full_name"]),
            trust_line=provider_trust_line(provider),
            amount=data["quote_amount"],
            currency=data["quote_currency"],
            delay=data["quote_delay_hours"],
            message=html.escape(quote_message) if quote_message else no_message_by_lang.get(client_lang, "Aucun message"),
        ),
        parse_mode="HTML",
        reply_markup=clavier_devis_client(quote_id, backend_quote_id),
    )

    await state.clear()
    await message.answer(
        get_message("quote_sent", provider_lang, reference=f"DV-{quote_id:04d}"),
        parse_mode="HTML",
        reply_markup=clavier_prestataire(provider_lang),
    )


@dp.callback_query(F.data.startswith("provider_skip_"))
async def passer_mission_prestataire(callback: CallbackQuery):
    mission_id = callback.data.replace("provider_skip_", "", 1)
    provider_lang = await get_provider_language(callback.from_user.id)
    await callback.message.edit_text(
        get_message("provider_mission_skipped", provider_lang, mission_id=int(mission_id)),
        parse_mode="HTML",
    )

    provider = update_consecutive_ignored(callback.from_user.id)
    await _safe_backend_call(sync_provider_ignored_increment_to_backend(callback.from_user.id))
    if provider is not None and provider["status"] == "paused" and provider["consecutive_ignored"] == 3:
        await bot.send_message(
            callback.from_user.id,
            get_message("provider_paused_message", provider_lang),
            parse_mode="HTML",
            reply_markup=clavier_disponibilite("paused", provider_lang),
        )

    await callback.answer(get_message("toast_mission_skipped", provider_lang))


@dp.callback_query(F.data.startswith("client_accept_quote_"))
async def client_accepte_devis(callback: CallbackQuery):
    quote_id, backend_quote_id = _parse_quote_callback_ids(callback.data.replace("client_accept_quote_", "", 1))
    quote = accept_quote(quote_id)
    if backend_quote_id is not None:
        await _safe_backend_call(sync_quote_accept_to_backend(backend_quote_id))
    total_client = quote["amount"]

    client_lang = await get_user_language(callback.from_user.id)
    client_user = get_user_by_telegram_id(callback.from_user.id)
    wallet_balance = 0.0
    if client_user is not None:
        wallet_balance = (
            client_user["wallet_balance_usd"] if quote["currency"] == "USD" else client_user["wallet_balance_cdf"]
        )

    try:
        await callback.message.edit_text(
            rich_message=build_quote_accept_rich_message(
                client_lang,
                mission_id=quote["mission_id"],
                prestataire=quote["provider_name"],
                devis=quote["amount"],
                total=total_client,
                currency=quote["currency"],
                wallet_balance=wallet_balance,
            ),
            reply_markup=clavier_paiement(quote_id),
        )
    except Exception:
        await callback.message.edit_text(
            get_message(
                "quote_accept_confirmation",
                client_lang,
                mission_id=quote["mission_id"],
                prestataire=html.escape(quote["provider_name"]),
                devis=quote["amount"],
                total=total_client,
                currency=quote["currency"],
                wallet_balance=wallet_balance,
            ),
            parse_mode="HTML",
            reply_markup=clavier_paiement(quote_id),
        )

    provider_lang = await get_provider_language(quote["provider_telegram_id"])
    await bot.send_message(
        quote["provider_telegram_id"],
        get_message(
            "quote_accept_provider_notify",
            provider_lang,
            mission_id=quote["mission_id"],
            amount=quote["amount"],
            currency=quote["currency"],
        ),
        parse_mode="HTML",
    )
    await callback.answer(get_message("toast_quote_accepted", client_lang))


@dp.callback_query(F.data.startswith("pay_mobile_"))
async def paiement_mobile_money(callback: CallbackQuery):
    quote_id = int(callback.data.replace("pay_mobile_", "", 1))
    payment = mark_quote_paid(quote_id, operator="mobile_money_simulation")
    quote = payment["quote"]

    await _safe_backend_call(sync_payment_to_backend(quote_id, "paid_escrow", mission_id=quote["mission_id"]))
    client_lang = await get_user_language(callback.from_user.id)
    await callback.message.edit_text(
        get_message(
            "payment_mobile_confirmed_client",
            client_lang,
            mission_id=quote["mission_id"],
            ref=payment["mobile_money_ref"],
            total=payment["total_client"],
            currency=quote["currency"],
        ),
        parse_mode="HTML",
        reply_markup=clavier_client(client_lang),
    )

    provider_lang = await get_provider_language(quote["provider_telegram_id"])
    await bot.send_message(
        quote["provider_telegram_id"],
        get_message(
            "payment_confirmed_provider_notify",
            provider_lang,
            mission_id=quote["mission_id"],
            brut=quote["amount"],
            commission=payment["commission_amount"],
            net=payment["net_provider"],
            currency=quote["currency"],
        ),
        parse_mode="HTML",
            reply_markup=clavier_mission_prestataire(quote["mission_id"], "start", provider_lang),
    )
    await callback.answer(get_message("toast_payment_confirmed", client_lang))


@dp.callback_query(F.data.startswith("mission_start_"))
async def prestataire_demarre_mission(callback: CallbackQuery):
    mission_id = int(callback.data.replace("mission_start_", "", 1))
    try:
        mission = start_mission(mission_id, callback.from_user.id)
    except ValueError as error:
        await callback.answer(str(error), show_alert=True)
        return

    provider_lang = await get_provider_language(callback.from_user.id)
    await _safe_backend_call(sync_mission_status_to_backend(mission_id, "in_progress"))
    await callback.message.edit_text(
        get_message("provider_mission_started", provider_lang, mission_id=mission_id),
        parse_mode="HTML",
        reply_markup=clavier_mission_prestataire(mission_id, "finish", provider_lang),
    )
    client_lang = await get_user_language(mission["client_telegram_id"])
    await bot.send_message(
        mission["client_telegram_id"],
        get_message("mission_started", client_lang, mission_id=mission_id),
        parse_mode="HTML",
    )
    await callback.answer(get_message("toast_mission_started", provider_lang))


@dp.callback_query(F.data.startswith("mission_finish_"))
async def prestataire_termine_mission(callback: CallbackQuery):
    mission_id = int(callback.data.replace("mission_finish_", "", 1))
    try:
        mission = finish_mission(mission_id, callback.from_user.id)
    except ValueError as error:
        await callback.answer(str(error), show_alert=True)
        return

    await _safe_backend_call(sync_mission_status_to_backend(mission_id, "awaiting_confirmation"))
    provider_lang = await get_provider_language(callback.from_user.id)
    await callback.message.edit_text(
        get_message("provider_mission_finished", provider_lang, mission_id=mission_id),
        parse_mode="HTML",
        reply_markup=clavier_prestataire(provider_lang),
    )
    client_lang = await get_user_language(mission["client_telegram_id"])
    await bot.send_message(
        mission["client_telegram_id"],
        get_message("mission_finished_client", client_lang, mission_id=mission_id),
        parse_mode="HTML",
        reply_markup=clavier_confirmation_client(mission_id),
    )
    await callback.answer(get_message("toast_client_notified", provider_lang))


@dp.callback_query(F.data.startswith("client_confirm_done_"))
async def client_confirme_mission_terminee(callback: CallbackQuery, state: FSMContext):
    mission_id = int(callback.data.replace("client_confirm_done_", "", 1))
    try:
        mission = release_payment(mission_id)
    except ValueError as error:
        await callback.answer(str(error), show_alert=True)
        return

    await _safe_backend_call(sync_mission_status_to_backend(mission_id, "completed", payment_status="released"))
    lang = await get_user_language(callback.from_user.id)
    await callback.message.edit_text(
        get_message("payment_released_client", lang, mission_id=mission_id),
        parse_mode="HTML",
        reply_markup=clavier_client(lang),
    )
    if mission["provider_telegram_id"]:
        provider_lang = await get_provider_language(mission["provider_telegram_id"])
        await bot.send_message(
            mission["provider_telegram_id"],
            get_message(
                "payment_released_provider",
                provider_lang,
                mission_id=mission_id,
                net=f"{mission['net_provider']:.2f}",
                currency=mission["currency"],
            ),
            parse_mode="HTML",
            reply_markup=clavier_prestataire(provider_lang),
        )

    provider = get_provider_by_telegram_id(mission["provider_telegram_id"]) if mission["provider_telegram_id"] else None
    if provider is not None:
        await state.set_state(RatingFlow.rating)
        await state.update_data(rating_mission_id=mission_id)
        await callback.message.answer(
            get_message("rate_provider", lang, mission_id=mission_id, prestataire=provider["full_name"]),
            parse_mode="HTML",
            reply_markup=clavier_notation(mission_id, lang),
        )
    await callback.answer(get_message("toast_payment_released", lang))


@dp.callback_query(RatingFlow.rating, F.data.startswith("rate_star_"))
async def notation_etoile_recue(callback: CallbackQuery, state: FSMContext):
    remainder = callback.data.removeprefix("rate_star_")
    mission_id_str, _, rating_str = remainder.rpartition("_")
    mission_id = int(mission_id_str)
    await state.update_data(rating_value=int(rating_str))
    await state.set_state(RatingFlow.comment)
    lang = await get_user_language(callback.from_user.id)
    await callback.message.edit_text(
        get_message("rate_comment_prompt", lang),
        parse_mode="HTML",
        reply_markup=clavier_notation_commentaire(mission_id, lang),
    )
    await callback.answer()


@dp.callback_query(RatingFlow.rating, F.data.startswith("rate_skip_"))
async def notation_ignoree(callback: CallbackQuery, state: FSMContext):
    lang = await get_user_language(callback.from_user.id)
    await state.clear()
    await callback.message.edit_text(get_message("rate_skipped", lang), parse_mode="HTML")
    await callback.answer()


async def _finalize_review(telegram_id: int, data: dict, comment: str | None, state: FSMContext) -> dict | None:
    result = await _safe_backend_call(
        sync_review_to_backend(
            mission_id=data["rating_mission_id"],
            client_telegram_id=telegram_id,
            rating=data["rating_value"],
            comment=comment or "",
        )
    )
    # Reviews exist only in the V5 backend. Unlike the legacy flows, there is
    # no local fallback to replay a failed write, so preserve the FSM state on
    # an outage and let the client retry instead of confirming a lost review.
    if result is not None:
        await state.clear()
    return result


@dp.message(RatingFlow.comment)
async def notation_commentaire_recu(message: Message, state: FSMContext):
    data = await state.get_data()
    comment = (message.text or "").strip()
    if comment == "-":
        comment = None
    lang = await get_user_language(message.from_user.id)
    result = await _finalize_review(message.from_user.id, data, comment, state)
    if result is None:
        await message.answer(get_message("rate_save_failed", lang), parse_mode="HTML")
        return
    await message.answer(get_message("rate_thanks", lang), parse_mode="HTML", reply_markup=clavier_client(lang))


@dp.callback_query(RatingFlow.comment, F.data.startswith("rate_comment_skip_"))
async def notation_commentaire_ignore(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = await get_user_language(callback.from_user.id)
    result = await _finalize_review(callback.from_user.id, data, None, state)
    if result is None:
        await callback.answer(get_message("rate_save_failed", lang), show_alert=True)
        return
    await callback.message.edit_text(get_message("rate_thanks", lang), parse_mode="HTML")
    await callback.answer()


@dp.callback_query(F.data.startswith("client_report_issue_"))
async def client_signale_probleme(callback: CallbackQuery):
    mission_id = int(callback.data.replace("client_report_issue_", "", 1))
    lang = await get_user_language(callback.from_user.id)
    await callback.message.edit_text(
        get_message("dispute_opened", lang, mission_id=mission_id),
        parse_mode="HTML",
        reply_markup=clavier_client(lang),
    )
    await callback.answer(get_message("toast_dispute_opened", lang))


@dp.callback_query(F.data.startswith("pay_wallet_"))
async def paiement_wallet(callback: CallbackQuery):
    quote_id = int(callback.data.replace("pay_wallet_", "", 1))
    try:
        payment = mark_quote_paid_with_wallet(quote_id, operator="wallet")
    except ValueError as error:
        await callback.answer(str(error), show_alert=True)
        return

    quote = payment["quote"]
    await _safe_backend_call(sync_payment_to_backend(quote_id, "paid_escrow", mission_id=quote["mission_id"]))
    client_lang = await get_user_language(callback.from_user.id)
    await callback.message.edit_text(
        get_message(
            "payment_wallet_confirmed_client",
            client_lang,
            mission_id=quote["mission_id"],
            ref=payment["mobile_money_ref"],
            total=payment["total_client"],
            currency=quote["currency"],
        ),
        parse_mode="HTML",
        reply_markup=clavier_client(client_lang),
    )

    provider_lang = await get_provider_language(quote["provider_telegram_id"])
    await bot.send_message(
        quote["provider_telegram_id"],
        get_message(
            "payment_wallet_confirmed_provider_notify",
            provider_lang,
            mission_id=quote["mission_id"],
            brut=quote["amount"],
            commission=payment["commission_amount"],
            net=payment["net_provider"],
            currency=quote["currency"],
        ),
        parse_mode="HTML",
        reply_markup=clavier_mission_prestataire(quote["mission_id"], "start", provider_lang),
    )
    await callback.answer(get_message("toast_wallet_payment_confirmed", client_lang))


@dp.callback_query(F.data.startswith("client_reject_quote_"))
async def client_refuse_devis(callback: CallbackQuery):
    quote_id, backend_quote_id = _parse_quote_callback_ids(callback.data.replace("client_reject_quote_", "", 1))
    quote = reject_quote(quote_id)
    if backend_quote_id is not None:
        await _safe_backend_call(sync_quote_reject_to_backend(backend_quote_id))
    client_lang = await get_user_language(callback.from_user.id)
    await callback.message.edit_text(
        get_message(
            "quote_rejected_client",
            client_lang,
            mission_id=quote["mission_id"],
            prestataire=html.escape(quote["provider_name"]),
        ),
        parse_mode="HTML",
    )
    provider_lang = await get_provider_language(quote["provider_telegram_id"])
    await bot.send_message(
        quote["provider_telegram_id"],
        get_message("quote_rejected_provider_notify", provider_lang, mission_id=quote["mission_id"]),
        parse_mode="HTML",
    )
    await callback.answer(get_message("toast_quote_rejected", client_lang))


@dp.callback_query(F.data == "mission_annuler")
async def mission_annuler(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    lang = await get_user_language(callback.from_user.id)
    await callback.message.edit_text(
        get_message("request_cancelled", lang),
        reply_markup=clavier_client(lang),
    )
    await callback.answer(get_message("toast_request_cancelled", lang))


@dp.callback_query(F.data == "client_missions")
async def afficher_missions_client(callback: CallbackQuery):
    lang = await get_user_language(callback.from_user.id)
    local_missions = get_user_missions(callback.from_user.id)
    backend_missions = await fetch_backend_missions(callback.from_user.id)
    missions = backend_missions or local_missions

    if not missions:
        await callback.message.edit_text(
            get_message("missions_empty", lang),
            parse_mode="HTML",
            reply_markup=clavier_client(lang),
        )
        await callback.answer()
        return

    text = get_message("missions_title", lang) + "\n\n" + "\n\n".join(
        html.escape(format_mission_client(mission)) if isinstance(mission, dict) and "service" in mission else html.escape(str(mission))
        for mission in missions
    )
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=clavier_client(lang),
    )
    await callback.answer()


@dp.callback_query(F.data == "client_wallet")
async def afficher_wallet_client(callback: CallbackQuery):
    user = get_user_by_telegram_id(callback.from_user.id)
    if user is None:
        await callback.answer("Client introuvable.", show_alert=True)
        return

    lang = await get_user_language(callback.from_user.id)
    await callback.message.edit_text(
        get_message(
            "wallet_title",
            lang,
            usd=user["wallet_balance_usd"],
            cdf=user["wallet_balance_cdf"],
        ),
        parse_mode="HTML",
        reply_markup=clavier_client(lang),
    )
    await callback.answer()


@dp.callback_query(F.data == "client_profil")
async def afficher_profil_client(callback: CallbackQuery):
    user = get_user_by_telegram_id(callback.from_user.id)
    profile_data = await load_profile_from_backend(callback.from_user.id, fallback_user=user)

    if user is None and not profile_data.get("client"):
        await callback.answer("Client introuvable.", show_alert=True)
        return

    client_profile = profile_data.get("client") or {}
    display_name = client_profile.get("first_name") or (user["first_name"] if user else "Client")
    display_phone = client_profile.get("phone_number") or (user["phone_number"] if user else "Non renseigné")
    total_missions = len(profile_data.get("client_missions", [])) if profile_data else (user["total_missions"] if user else 0)

    lang = await get_user_language(callback.from_user.id)
    lang_labels = {"fr": "Français", "ln": "Lingala", "en": "English"}
    lang_label = lang_labels.get(user["language"] if user else "fr", "Français")

    await callback.message.edit_text(
        get_message(
            "profile_title",
            lang,
            name=html.escape(display_name or "Client"),
            phone=html.escape(display_phone or "Non renseigné"),
            lang_label=lang_label,
            missions=total_missions,
        ),
        parse_mode="HTML",
        reply_markup=clavier_client(lang),
    )
    await callback.answer()


@dp.callback_query(F.data == "prest_missions")
async def afficher_missions_prestataire(callback: CallbackQuery):
    lang = await get_provider_language(callback.from_user.id)
    missions = get_provider_missions(callback.from_user.id)
    if not missions:
        await callback.message.edit_text(
            get_message("provider_missions_empty", lang),
            parse_mode="HTML",
            reply_markup=clavier_prestataire(lang),
        )
        await callback.answer()
        return

    text = get_message("provider_missions_title", lang) + "\n\n" + "\n\n".join(
        html.escape(format_mission_provider(mission)) for mission in missions
    )
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=clavier_prestataire(lang),
    )
    await callback.answer()


@dp.callback_query(F.data == "prest_wallet")
async def afficher_wallet_prestataire(callback: CallbackQuery):
    provider = get_provider_by_telegram_id(callback.from_user.id)
    lang = await get_provider_language(callback.from_user.id)
    if provider is None:
        await callback.answer(get_message("provider_not_found", lang), show_alert=True)
        return

    await callback.message.edit_text(
        get_message(
            "provider_wallet_title",
            lang,
            usd=provider["wallet_balance_usd"],
            cdf=provider["wallet_balance_cdf"],
        ),
        parse_mode="HTML",
        reply_markup=clavier_prestataire(lang),
    )
    await callback.answer()


@dp.callback_query(F.data == "prest_profil")
async def afficher_profil_prestataire(callback: CallbackQuery):
    provider = get_provider_by_telegram_id(callback.from_user.id)
    backend_profile = await fetch_backend_profile(callback.from_user.id)
    provider_data = (backend_profile or {}).get("provider") if backend_profile else None
    lang = await get_provider_language(callback.from_user.id)

    if provider is None and not provider_data:
        await callback.answer(get_message("provider_not_found", lang), show_alert=True)
        return

    display_name = provider_data.get("full_name") if provider_data else provider.get("full_name") if provider else get_message("provider_default_name", lang)
    display_phone = provider_data.get("phone_number") if provider_data else provider.get("phone_number") if provider else get_message("not_provided", lang)
    display_status = provider_data.get("status") if provider_data else provider.get("status") if provider else "available"
    display_services = ", ".join(provider_data.get("services", [])) if provider_data else ""
    status_labels = {
        "available": get_message("provider_status_available", lang),
        "offline": get_message("provider_status_offline", lang),
        "paused": get_message("provider_status_paused", lang),
    }
    status_label = status_labels.get(display_status, display_status)

    text = get_message(
        "provider_profile_title",
        lang,
        name=html.escape(display_name or get_message("provider_default_name", lang)),
        phone=html.escape(display_phone or get_message("not_provided", lang)),
        status=html.escape(status_label),
    )
    if display_services:
        text += "\n" + get_message("provider_profile_services", lang, services=html.escape(display_services))

    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=clavier_prestataire(lang),
    )
    await callback.answer()


@dp.callback_query(F.data == "client_historique")
async def afficher_historique_client(callback: CallbackQuery):
    lang = await get_user_language(callback.from_user.id)
    local_missions = get_user_missions(callback.from_user.id)
    backend_missions = await fetch_backend_missions(callback.from_user.id)
    missions = backend_missions or local_missions
    terminal_statuses = {"completed", "cancelled", "disputed"}
    history = [
        mission
        for mission in missions
        if isinstance(mission, dict) and mission.get("status") in terminal_statuses
    ]

    if not history:
        await callback.message.edit_text(
            get_message("mission_history_empty", lang),
            parse_mode="HTML",
            reply_markup=clavier_client(lang),
        )
        await callback.answer()
        return

    text = get_message("mission_history_title", lang) + "\n\n" + "\n\n".join(
        html.escape(format_mission_client(mission)) for mission in history
    )
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=clavier_client(lang),
    )
    await callback.answer()


def _rich_cell(text: str, header: bool = False) -> RichBlockTableCell:
    return RichBlockTableCell(text=text, is_header=header, align="left", valign="middle")


def build_help_rich_message(lang: str = "fr") -> InputRichMessage:
    faq_items = [
        ("help_faq_1_q", "help_faq_1_a"),
        ("help_faq_2_q", "help_faq_2_a"),
        ("help_faq_3_q", "help_faq_3_a"),
    ]
    blocks = [InputRichBlockParagraph(text=get_message("help_title", lang))]
    for index, (question_key, answer_key) in enumerate(faq_items):
        blocks.append(
            InputRichBlockDetails(
                summary=get_message(question_key, lang),
                blocks=[InputRichBlockParagraph(text=get_message(answer_key, lang))],
                is_open=(index == 0),
            )
        )
    blocks.append(InputRichBlockParagraph(text=get_message("help_contact", lang)))
    return InputRichMessage(blocks=blocks)


def build_quote_accept_rich_message(
    lang: str,
    mission_id: int,
    prestataire: str,
    devis: float,
    total: float,
    currency: str,
    wallet_balance: float,
) -> InputRichMessage:
    rows = [
        (get_message("table_row_provider", lang), prestataire),
        (get_message("table_row_quote", lang), f"{devis:.2f} {currency}"),
        (get_message("table_row_total", lang), f"{total:.2f} {currency}"),
        (get_message("table_row_wallet", lang), f"{wallet_balance:.2f} {currency}"),
    ]
    table = InputRichBlockTable(
        cells=[
            [
                _rich_cell(get_message("table_col_detail", lang), header=True),
                _rich_cell(get_message("table_col_amount", lang), header=True),
            ],
            *[[_rich_cell(label), _rich_cell(value)] for label, value in rows],
        ],
        is_bordered=True,
        is_striped=True,
    )
    return InputRichMessage(
        blocks=[
            InputRichBlockParagraph(text=get_message("quote_accept_title", lang, mission_id=mission_id)),
            table,
            InputRichBlockParagraph(text=get_message("quote_accept_choose_payment", lang)),
        ]
    )


def build_history_rich_message(lang: str, missions: list) -> InputRichMessage:
    header = [
        _rich_cell(get_message("table_col_mission", lang), header=True),
        _rich_cell(get_message("table_col_service", lang), header=True),
        _rich_cell(get_message("table_col_status", lang), header=True),
        _rich_cell(get_message("table_col_payment", lang), header=True),
    ]
    rows = []
    for mission in missions:
        rows.append(
            [
                _rich_cell(f"NXH-{mission['id']:04d}"),
                _rich_cell(SERVICES.get(mission["service"], mission["service"])),
                _rich_cell(STATUS_LABELS.get(mission["status"], mission["status"] or "")),
                _rich_cell(PAYMENT_STATUS_LABELS.get(mission["payment_status"], mission["payment_status"] or "")),
            ]
        )
    table = InputRichBlockTable(cells=[header, *rows], is_bordered=True, is_striped=True)
    return InputRichMessage(
        blocks=[
            InputRichBlockParagraph(text=get_message("mission_history_title", lang)),
            table,
        ]
    )


@dp.callback_query(F.data == "client_aide")
async def afficher_aide_client(callback: CallbackQuery):
    lang = await get_user_language(callback.from_user.id)
    try:
        await callback.message.edit_text(
            rich_message=build_help_rich_message(lang),
            reply_markup=clavier_client(lang),
        )
    except Exception:
        await callback.message.edit_text(
            get_message("help_content", lang),
            parse_mode="HTML",
            reply_markup=clavier_client(lang),
        )
    await callback.answer()


@dp.callback_query(F.data == "client_parametres")
async def afficher_parametres_client(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    lang = await get_user_language(callback.from_user.id)
    await callback.message.edit_text(
        get_message("settings_title", lang),
        parse_mode="HTML",
        reply_markup=clavier_parametres_client(lang),
    )
    await callback.answer()


@dp.callback_query(F.data == "client_menu_from_settings")
async def retour_menu_client(callback: CallbackQuery):
    lang = await get_user_language(callback.from_user.id)
    prenom = html.escape(callback.from_user.first_name or "Client")
    await callback.message.edit_text(
        get_message("client_menu", lang, prenom=prenom),
        parse_mode="HTML",
        reply_markup=clavier_client(lang),
    )
    await callback.answer()


@dp.callback_query(F.data == "client_settings_language")
async def demander_nouvelle_langue(callback: CallbackQuery):
    lang = await get_user_language(callback.from_user.id)
    await callback.message.edit_text(
        get_message("settings_language_prompt", lang),
        parse_mode="HTML",
        reply_markup=clavier_langue_parametres(lang),
    )
    await callback.answer()


async def _appliquer_nouvelle_langue(callback: CallbackQuery, new_lang: str):
    update_user_language(callback.from_user.id, new_lang)
    await _safe_backend_call(sync_user_language_to_backend(callback.from_user.id, new_lang))
    prenom = html.escape(callback.from_user.first_name or "Client")
    await callback.message.edit_text(
        f"{get_message('settings_language_updated', new_lang)}\n\n"
        f"{get_message('client_menu', new_lang, prenom=prenom)}",
        parse_mode="HTML",
        reply_markup=clavier_client(new_lang),
    )
    await callback.answer()


@dp.callback_query(F.data == "settings_lang_fr")
async def modifier_langue_fr(callback: CallbackQuery):
    await _appliquer_nouvelle_langue(callback, "fr")


@dp.callback_query(F.data == "settings_lang_ln")
async def modifier_langue_ln(callback: CallbackQuery):
    await _appliquer_nouvelle_langue(callback, "ln")


@dp.callback_query(F.data == "settings_lang_en")
async def modifier_langue_en(callback: CallbackQuery):
    await _appliquer_nouvelle_langue(callback, "en")


@dp.callback_query(F.data == "client_settings_name")
async def demander_nouveau_nom(callback: CallbackQuery, state: FSMContext):
    lang = await get_user_language(callback.from_user.id)
    await state.set_state(ClientSettings.name)
    await callback.message.edit_text(
        get_message("settings_name_prompt", lang),
        parse_mode="HTML",
    )
    await callback.answer()


@dp.message(ClientSettings.name)
async def nouveau_nom_recu(message: Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id)
    new_name = (message.text or "").strip()
    if not new_name:
        await message.answer(get_message("settings_name_prompt", lang), parse_mode="HTML")
        return

    await state.clear()
    update_user_name(message.from_user.id, new_name)
    await _safe_backend_call(sync_user_name_to_backend(message.from_user.id, new_name))
    await message.answer(
        get_message("settings_name_updated", lang, name=html.escape(new_name)),
        parse_mode="HTML",
        reply_markup=clavier_client(lang),
    )


@dp.callback_query(
    F.data.in_(
        [
            "prest_dashboard",
            "prest_support",
        ]
    )
)
async def fonctionnalite_a_venir(callback: CallbackQuery):
    await callback.answer("Module prévu dans la suite du développement.", show_alert=True)


async def main():
    init_db()
    print("✅ NEXIS HUB Bot démarré.")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
