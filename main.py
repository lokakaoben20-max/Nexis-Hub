import asyncio
import html
import json
import os

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, KeyboardButton, Message, ReplyKeyboardMarkup, ReplyKeyboardRemove, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv

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
    reject_quote,
    release_payment,
    set_provider_suspended,
    set_provider_verified,
    start_mission,
    update_provider_language,
    update_provider_services,
    update_provider_status,
    update_service_request_status,
    update_user_language,
)


load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_TELEGRAM_ID = os.getenv("ADMIN_TELEGRAM_ID")
MINI_APP_URL = os.getenv("MINI_APP_URL")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN manquant dans le fichier .env")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


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
    },
}


def button_label(key: str, lang: str = "fr") -> str:
    return BUTTON_LABELS.get(lang, BUTTON_LABELS["fr"]).get(key, BUTTON_LABELS["fr"][key])


class MissionRequest(StatesGroup):
    description = State()
    photo = State()


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


def clavier_disponibilite(status: str):
    builder = InlineKeyboardBuilder()
    if status == "available":
        builder.button(text="⏸️ Me rendre indisponible", callback_data="provider_status_offline")
    else:
        builder.button(text="✅ Me rendre disponible", callback_data="provider_status_available")
    builder.button(text="⬅️ Retour", callback_data="profil_prestataire")
    builder.adjust(1)
    return builder.as_markup()


def clavier_alerte_mission(mission_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Accepter", callback_data=f"provider_accept_{mission_id}")
    builder.button(text="❌ Passer", callback_data=f"provider_skip_{mission_id}")
    builder.adjust(2)
    return builder.as_markup()


def clavier_devis_client(quote_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Accepter ce devis", callback_data=f"client_accept_quote_{quote_id}")
    builder.button(text="❌ Refuser", callback_data=f"client_reject_quote_{quote_id}")
    builder.adjust(1)
    return builder.as_markup()


def clavier_paiement(quote_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text="📱 Payer via Mobile Money", callback_data=f"pay_mobile_{quote_id}")
    builder.button(text="👛 Payer avec Wallet", callback_data=f"pay_wallet_{quote_id}")
    builder.button(text="⬅️ Plus tard", callback_data="profil_client")
    builder.adjust(1)
    return builder.as_markup()


def clavier_mission_prestataire(mission_id: int, action: str):
    builder = InlineKeyboardBuilder()
    if action == "start":
        builder.button(text="▶️ Démarrer la mission", callback_data=f"mission_start_{mission_id}")
    elif action == "finish":
        builder.button(text="✅ Mission terminée", callback_data=f"mission_finish_{mission_id}")
    builder.button(text="🏠 Menu prestataire", callback_data="profil_prestataire")
    builder.adjust(1)
    return builder.as_markup()


def clavier_confirmation_client(mission_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Confirmer et libérer le paiement", callback_data=f"client_confirm_done_{mission_id}")
    builder.button(text="⚠️ Signaler un problème", callback_data=f"client_report_issue_{mission_id}")
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


def clavier_modifier_services(selected_services=None):
    selected_services = selected_services or []
    builder = InlineKeyboardBuilder()
    for key, label in SERVICES.items():
        prefix = "✅" if key in selected_services else "▫️"
        builder.button(text=f"{prefix} {label}", callback_data=f"edit_service_{key}")
    builder.button(text="✅ Enregistrer mes services", callback_data="edit_services_done")
    builder.button(text="➕ Proposer un service manquant", callback_data="prest_missing_service")
    builder.button(text="⬅️ Retour", callback_data="profil_prestataire")
    builder.adjust(1)
    return builder.as_markup()


def clavier_services_actions():
    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ Modifier mes services", callback_data="prest_edit_services")
    builder.button(text="➕ Proposer un service manquant", callback_data="prest_missing_service")
    builder.button(text="⬅️ Retour", callback_data="profil_prestataire")
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
    urgence = "Oui" if data.get("urgent") else "Non"
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


def get_user_language(telegram_id: int) -> str:
    user = get_user_by_telegram_id(telegram_id)
    return user["language"] if user else "fr"


def get_provider_language(telegram_id: int) -> str:
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
    lang = get_user_language(message.from_user.id)
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
    create_user(
        telegram_id=message.from_user.id,
        phone_number=phone_number,
        first_name=message.from_user.first_name or "",
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
    lang = data.get("language") or get_provider_language(callback.from_user.id)
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
    await callback.answer("Inscription terminée")


@dp.callback_query(F.data == "prest_dispo")
async def disponibilite_prestataire(callback: CallbackQuery):
    provider = get_provider_by_telegram_id(callback.from_user.id)
    if provider is None:
        await callback.answer("Créez d'abord votre profil prestataire.", show_alert=True)
        return

    status_label = "Disponible" if provider["status"] == "available" else "Indisponible"
    await callback.message.edit_text(
        "⚙️ <b>Disponibilité</b>\n\n"
        f"Statut actuel : <b>{status_label}</b>",
        parse_mode="HTML",
        reply_markup=clavier_disponibilite(provider["status"]),
    )
    await callback.answer()


@dp.callback_query(F.data.in_(["provider_status_available", "provider_status_offline"]))
async def changer_disponibilite(callback: CallbackQuery):
    status = "available" if callback.data == "provider_status_available" else "offline"
    update_provider_status(callback.from_user.id, status)
    status_label = "Disponible" if status == "available" else "Indisponible"
    await callback.message.edit_text(
        "⚙️ <b>Disponibilité mise à jour</b>\n\n"
        f"Statut actuel : <b>{status_label}</b>",
        parse_mode="HTML",
        reply_markup=clavier_disponibilite(status),
    )
    await callback.answer("Statut mis à jour")


@dp.callback_query(F.data == "prest_services")
async def afficher_services_prestataire(callback: CallbackQuery):
    provider = get_provider_by_telegram_id(callback.from_user.id)
    if provider is None:
        await callback.answer("Créez d'abord votre profil prestataire.", show_alert=True)
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
        "🧰 <b>Mes services</b>\n\n"
        "<b>Services actifs :</b>\n"
        + ("\n".join(f"• {label}" for label in service_labels) if service_labels else "Aucun service sélectionné")
    )
    if request_lines:
        text += "\n\n<b>Services proposés à Nexis :</b>\n" + "\n".join(request_lines)

    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=clavier_services_actions(),
    )
    await callback.answer()


@dp.callback_query(F.data == "prest_edit_services")
async def modifier_services_prestataire(callback: CallbackQuery, state: FSMContext):
    provider = get_provider_by_telegram_id(callback.from_user.id)
    if provider is None:
        await callback.answer("Créez d'abord votre profil prestataire.", show_alert=True)
        return

    try:
        selected_services = json.loads(provider["services"] or "[]")
    except json.JSONDecodeError:
        selected_services = []

    await state.set_state(ProviderServicesEdit.services)
    await state.update_data(provider_services_edit=selected_services)
    await callback.message.edit_text(
        "🧰 <b>Modifier mes services</b>\n\n"
        "Cochez ou décochez les services que vous proposez, puis enregistrez.",
        parse_mode="HTML",
        reply_markup=clavier_modifier_services(selected_services),
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
    await callback.message.edit_reply_markup(reply_markup=clavier_modifier_services(selected))
    await callback.answer()


@dp.callback_query(ProviderServicesEdit.services, F.data == "edit_services_done")
async def enregistrer_services_modifies(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected = data.get("provider_services_edit", [])
    if not selected:
        await callback.answer("Choisissez au moins un service.", show_alert=True)
        return

    update_provider_services(callback.from_user.id, selected)
    await state.clear()
    service_labels = [SERVICES.get(service, service) for service in selected]
    await callback.message.edit_text(
        "✅ <b>Services mis à jour.</b>\n\n"
        + "\n".join(f"• {label}" for label in service_labels),
        parse_mode="HTML",
        reply_markup=clavier_prestataire(get_provider_language(callback.from_user.id)),
    )
    await callback.answer("Services enregistrés")


@dp.callback_query(F.data == "prest_missing_service")
async def proposer_service_manquant(callback: CallbackQuery, state: FSMContext):
    provider = get_provider_by_telegram_id(callback.from_user.id)
    if provider is None:
        await callback.answer("Créez d'abord votre profil prestataire.", show_alert=True)
        return

    await state.clear()
    await state.set_state(ProviderServiceRequest.service_name)
    await callback.message.edit_text(
        "➕ <b>Service manquant</b>\n\n"
        "Quel service souhaitez-vous proposer à Nexis ?\n\n"
        "Exemple : Réparation panneaux solaires",
        parse_mode="HTML",
    )
    await callback.answer()


@dp.message(ProviderServiceRequest.service_name)
async def recevoir_nom_service_manquant(message: Message, state: FSMContext):
    service_name = (message.text or "").strip()
    if len(service_name) < 3:
        await message.answer("Veuillez envoyer un nom de service plus précis.")
        return

    await state.update_data(missing_service_name=service_name)
    await state.set_state(ProviderServiceRequest.description)
    await message.answer(
        "📝 Décrivez ce service pour aider Nexis à l'évaluer.\n\n"
        "Précisez ce que vous faites, le type de client concerné, et si un déplacement est nécessaire."
    )


@dp.message(ProviderServiceRequest.description)
async def recevoir_description_service_manquant(message: Message, state: FSMContext):
    description = (message.text or "").strip()
    if len(description) < 10:
        await message.answer("Ajoutez un peu plus de détails pour que Nexis comprenne bien le service.")
        return

    data = await state.get_data()
    request_id = create_service_request(
        telegram_id=message.from_user.id,
        service_name=data["missing_service_name"],
        description=description,
    )
    await state.clear()
    await message.answer(
        "✅ <b>Votre proposition de service a été enregistrée.</b>\n\n"
        f"Référence : <b>SRV-{request_id:04d}</b>\n"
        f"Service proposé : <b>{html.escape(data['missing_service_name'])}</b>\n\n"
        "Nexis va l'examiner. Si le service est accepté, il pourra être ajouté au catalogue. "
        "Si ce n'est pas possible, vous recevrez une réponse indiquant que Nexis ne peut pas encore le prendre en charge.",
        parse_mode="HTML",
        reply_markup=clavier_prestataire(get_provider_language(message.from_user.id)),
    )


@dp.callback_query(F.data == "client_demande")
async def client_demande(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = data.get("language") or get_user_language(callback.from_user.id)
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
    lang = get_user_language(callback.from_user.id)
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
        feedback = f"🎙️ Note vocale ajoutée ({len(voice_file_ids)})."
    elif message.photo:
        photo_file_ids.append(message.photo[-1].file_id)
        feedback = f"📷 Photo ajoutée ({len(photo_file_ids)})."
    elif message.text:
        description_parts.append(message.text.strip())
        feedback = "✏️ Texte ajouté."
    else:
        await message.answer(
            "Veuillez envoyer un texte, une photo ou une note vocale.",
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
        f"{feedback}\n\n"
        "Vous pouvez encore envoyer un autre texte, une autre photo ou une autre note vocale. "
        "Quand c'est complet, appuyez sur Terminer.",
        reply_markup=clavier_fin_explication(lang),
    )


@dp.callback_query(MissionRequest.description, F.data == "mission_media_done")
async def explication_terminee(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    description_parts = data.get("description_parts", [])
    photo_file_ids = data.get("photo_file_ids", [])
    voice_file_ids = data.get("voice_file_ids", [])

    if not description_parts and not photo_file_ids and not voice_file_ids:
        await callback.answer("Envoyez au moins un texte, une photo ou une note vocale.", show_alert=True)
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


@dp.callback_query(MissionRequest.photo, F.data == "mission_skip_photo")
async def photo_ignoree(callback: CallbackQuery, state: FSMContext):
    await state.update_data(photo_file_id=None)
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
    matching_text = (
        f"{len(matching_providers[:3])} prestataire(s) notifié(s)."
        if matching_providers
        else "Aucun prestataire disponible trouvé pour l'instant."
    )
    await callback.message.edit_text(
        get_message(
            "mission_saved",
            data.get("language", "fr"),
            mission_id=mission_id,
            matching_text=matching_text,
        ),
        parse_mode="HTML",
        reply_markup=clavier_client(data.get("language", "fr")),
    )
    print("Nouvelle demande client:", data)
    await callback.answer("Demande confirmée")


@dp.callback_query(F.data.startswith("provider_accept_"))
async def accepter_mission_prestataire(callback: CallbackQuery, state: FSMContext):
    mission_id = int(callback.data.replace("provider_accept_", "", 1))
    mission = get_mission_by_id(mission_id)
    if mission is None:
        await callback.answer("Mission introuvable.", show_alert=True)
        return

    await state.clear()
    await state.set_state(QuoteCreation.amount)
    await state.update_data(quote_mission_id=mission_id)
    await callback.message.edit_text(
        f"✅ Mission <b>NXH-{mission_id:04d}</b> acceptée.\n\n"
        "Envoyez le montant de votre devis.\n\n"
        "Exemple : <b>35</b>",
        parse_mode="HTML",
    )
    await callback.answer("Mission acceptée")


@dp.message(QuoteCreation.amount)
async def devis_montant_recu(message: Message, state: FSMContext):
    raw_amount = (message.text or "").replace(",", ".").strip()
    try:
        amount = float(raw_amount)
    except ValueError:
        await message.answer("Veuillez envoyer un montant valide. Exemple : 35")
        return

    if amount <= 0:
        await message.answer("Le montant doit être supérieur à zéro.")
        return

    await state.update_data(quote_amount=amount)
    await state.set_state(QuoteCreation.currency)
    await message.answer(
        "💱 Dans quelle devise est ce devis ?",
        reply_markup=clavier_devises_devis(),
    )


@dp.callback_query(QuoteCreation.currency, F.data.in_(["quote_currency_usd", "quote_currency_cdf"]))
async def devis_devise_recue(callback: CallbackQuery, state: FSMContext):
    currency = "USD" if callback.data == "quote_currency_usd" else "CDF"
    await state.update_data(quote_currency=currency)
    await state.set_state(QuoteCreation.delay)
    await callback.message.edit_text(
        "⏱️ En combien d'heures pouvez-vous réaliser ou commencer la mission ?\n\n"
        "Exemple : <b>2</b>",
        parse_mode="HTML",
    )
    await callback.answer()


@dp.message(QuoteCreation.delay)
async def devis_delai_recu(message: Message, state: FSMContext):
    raw_delay = (message.text or "").strip()
    if not raw_delay.isdigit():
        await message.answer("Veuillez envoyer un nombre d'heures. Exemple : 2")
        return

    delay_hours = int(raw_delay)
    if delay_hours <= 0:
        await message.answer("Le délai doit être supérieur à zéro.")
        return

    await state.update_data(quote_delay_hours=delay_hours)
    await state.set_state(QuoteCreation.message)
    await message.answer(
        "💬 Ajoutez un court message pour le client.\n\n"
        "Exemple : Je peux passer aujourd'hui avec le matériel nécessaire.\n\n"
        "Envoyez <b>-</b> si vous ne voulez pas ajouter de message.",
        parse_mode="HTML",
    )


@dp.message(QuoteCreation.message)
async def devis_message_recu(message: Message, state: FSMContext):
    data = await state.get_data()
    provider = get_provider_by_telegram_id(message.from_user.id)
    mission = get_mission_by_id(data["quote_mission_id"])

    if provider is None or mission is None:
        await state.clear()
        await message.answer("Impossible de créer le devis : mission ou prestataire introuvable.")
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

    await bot.send_message(
        mission["client_telegram_id"],
        "💬 <b>Nouveau devis reçu</b>\n\n"
        f"Mission : <b>NXH-{data['quote_mission_id']:04d}</b>\n"
        f"Prestataire : <b>{html.escape(provider['full_name'])}</b>\n"
        f"Montant : <b>{data['quote_amount']:.2f} {data['quote_currency']}</b>\n"
        f"Délai : <b>{data['quote_delay_hours']} h</b>\n"
        f"Message : {html.escape(quote_message) if quote_message else 'Aucun message'}",
        parse_mode="HTML",
        reply_markup=clavier_devis_client(quote_id),
    )

    await state.clear()
    await message.answer(
        "✅ Devis envoyé au client.\n\n"
        f"Référence devis : <b>DV-{quote_id:04d}</b>",
        parse_mode="HTML",
        reply_markup=clavier_prestataire(get_provider_language(message.from_user.id)),
    )


@dp.callback_query(F.data.startswith("provider_skip_"))
async def passer_mission_prestataire(callback: CallbackQuery):
    mission_id = callback.data.replace("provider_skip_", "", 1)
    await callback.message.edit_text(
        f"❌ Vous avez passé la mission <b>NXH-{int(mission_id):04d}</b>.",
        parse_mode="HTML",
    )
    await callback.answer("Mission ignorée")


@dp.callback_query(F.data.startswith("client_accept_quote_"))
async def client_accepte_devis(callback: CallbackQuery):
    quote_id = int(callback.data.replace("client_accept_quote_", "", 1))
    quote = accept_quote(quote_id)
    tola_fee = 1.50 if quote["currency"] == "USD" else 4000.00
    total_client = quote["amount"] + tola_fee

    await callback.message.edit_text(
        "✅ <b>Devis accepté.</b>\n\n"
        f"Mission : <b>NXH-{quote['mission_id']:04d}</b>\n"
        f"Prestataire : <b>{html.escape(quote['provider_name'])}</b>\n"
        f"Devis : <b>{quote['amount']:.2f} {quote['currency']}</b>\n"
        f"Frais Tola / techniques : <b>{tola_fee:.2f} {quote['currency']}</b>\n"
        f"Total à payer : <b>{total_client:.2f} {quote['currency']}</b>\n\n"
        "Choisissez un mode de paiement pour sécuriser la mission.",
        parse_mode="HTML",
        reply_markup=clavier_paiement(quote_id),
    )

    await bot.send_message(
        quote["provider_telegram_id"],
        "✅ <b>Votre devis a été accepté</b>\n\n"
        f"Mission : <b>NXH-{quote['mission_id']:04d}</b>\n"
        f"Montant : <b>{quote['amount']:.2f} {quote['currency']}</b>\n\n"
        "En attente du paiement escrow du client.",
        parse_mode="HTML",
    )
    await callback.answer("Devis accepté")


@dp.callback_query(F.data.startswith("pay_mobile_"))
async def paiement_mobile_money(callback: CallbackQuery):
    quote_id = int(callback.data.replace("pay_mobile_", "", 1))
    payment = mark_quote_paid(quote_id, operator="mobile_money_simulation")
    quote = payment["quote"]

    await callback.message.edit_text(
        "✅ <b>Paiement escrow confirmé</b>\n\n"
        f"Mission : <b>NXH-{quote['mission_id']:04d}</b>\n"
        f"Référence paiement : <b>{payment['mobile_money_ref']}</b>\n"
        f"Total payé : <b>{payment['total_client']:.2f} {quote['currency']}</b>\n"
        f"Frais Tola / techniques : <b>{payment['tola_fee']:.2f} {quote['currency']}</b>\n\n"
        "Le montant du devis est maintenant sécurisé. Le prestataire peut commencer.",
        parse_mode="HTML",
        reply_markup=clavier_client(get_user_language(callback.from_user.id)),
    )

    await bot.send_message(
        quote["provider_telegram_id"],
        "💰 <b>Paiement sécurisé reçu</b>\n\n"
        f"Mission : <b>NXH-{quote['mission_id']:04d}</b>\n"
        f"Montant brut : <b>{quote['amount']:.2f} {quote['currency']}</b>\n"
        f"Commission NEXIS HUB : <b>{payment['commission_amount']:.2f} {quote['currency']}</b>\n"
        f"Net prestataire : <b>{payment['net_provider']:.2f} {quote['currency']}</b>\n\n"
        "Vous pouvez commencer la mission.",
        parse_mode="HTML",
        reply_markup=clavier_mission_prestataire(quote["mission_id"], "start"),
    )
    await callback.answer("Paiement confirmé")


@dp.callback_query(F.data.startswith("mission_start_"))
async def prestataire_demarre_mission(callback: CallbackQuery):
    mission_id = int(callback.data.replace("mission_start_", "", 1))
    try:
        mission = start_mission(mission_id, callback.from_user.id)
    except ValueError as error:
        await callback.answer(str(error), show_alert=True)
        return

    await callback.message.edit_text(
        f"▶️ Mission <b>NXH-{mission_id:04d}</b> démarrée.\n\n"
        "Quand le travail est terminé, appuyez sur le bouton ci-dessous.",
        parse_mode="HTML",
        reply_markup=clavier_mission_prestataire(mission_id, "finish"),
    )
    await bot.send_message(
        mission["client_telegram_id"],
        get_message("mission_started", "fr", mission_id=mission_id),
        parse_mode="HTML",
    )
    await callback.answer("Mission démarrée")


@dp.callback_query(F.data.startswith("mission_finish_"))
async def prestataire_termine_mission(callback: CallbackQuery):
    mission_id = int(callback.data.replace("mission_finish_", "", 1))
    try:
        mission = finish_mission(mission_id, callback.from_user.id)
    except ValueError as error:
        await callback.answer(str(error), show_alert=True)
        return

    await callback.message.edit_text(
        f"✅ Mission <b>NXH-{mission_id:04d}</b> marquée comme terminée.\n\n"
        "Le client doit maintenant confirmer pour libérer le paiement.",
        parse_mode="HTML",
        reply_markup=clavier_prestataire(get_provider_language(callback.from_user.id)),
    )
    await bot.send_message(
        mission["client_telegram_id"],
        get_message("mission_finished_client", "fr", mission_id=mission_id),
        parse_mode="HTML",
        reply_markup=clavier_confirmation_client(mission_id),
    )
    await callback.answer("Client notifié")


@dp.callback_query(F.data.startswith("client_confirm_done_"))
async def client_confirme_mission_terminee(callback: CallbackQuery):
    mission_id = int(callback.data.replace("client_confirm_done_", "", 1))
    try:
        mission = release_payment(mission_id)
    except ValueError as error:
        await callback.answer(str(error), show_alert=True)
        return

    await callback.message.edit_text(
        get_message("payment_released_client", "fr", mission_id=mission_id),
        parse_mode="HTML",
        reply_markup=clavier_client(get_user_language(callback.from_user.id)),
    )
    if mission["provider_telegram_id"]:
        await bot.send_message(
            mission["provider_telegram_id"],
            get_message(
                "payment_released_provider",
                "fr",
                mission_id=mission_id,
                net=f"{mission['net_provider']:.2f}",
                currency=mission["currency"],
            ),
            parse_mode="HTML",
            reply_markup=clavier_prestataire(get_provider_language(mission["provider_telegram_id"])),
        )
    await callback.answer("Paiement libéré")


@dp.callback_query(F.data.startswith("client_report_issue_"))
async def client_signale_probleme(callback: CallbackQuery):
    mission_id = int(callback.data.replace("client_report_issue_", "", 1))
    await callback.message.edit_text(
        get_message("dispute_opened", "fr", mission_id=mission_id),
        parse_mode="HTML",
        reply_markup=clavier_client(get_user_language(callback.from_user.id)),
    )
    await callback.answer("Paiement maintenu en escrow")


@dp.callback_query(F.data.startswith("pay_wallet_"))
async def paiement_wallet(callback: CallbackQuery):
    await callback.answer(
        "Wallet prévu dans la suite. Pour l'instant, utilisez Mobile Money simulé.",
        show_alert=True,
    )


@dp.callback_query(F.data.startswith("client_reject_quote_"))
async def client_refuse_devis(callback: CallbackQuery):
    quote_id = int(callback.data.replace("client_reject_quote_", "", 1))
    quote = reject_quote(quote_id)
    await callback.message.edit_text(
        "❌ <b>Devis refusé.</b>\n\n"
        f"Mission : <b>NXH-{quote['mission_id']:04d}</b>\n"
        f"Prestataire : <b>{html.escape(quote['provider_name'])}</b>",
        parse_mode="HTML",
    )
    await bot.send_message(
        quote["provider_telegram_id"],
        "❌ <b>Votre devis a été refusé</b>\n\n"
        f"Mission : <b>NXH-{quote['mission_id']:04d}</b>",
        parse_mode="HTML",
    )
    await callback.answer("Devis refusé")


@dp.callback_query(F.data == "mission_annuler")
async def mission_annuler(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "❌ Demande annulée.\n\nRetour à votre espace client.",
        reply_markup=clavier_client(get_user_language(callback.from_user.id)),
    )
    await callback.answer("Demande annulée")


@dp.callback_query(F.data == "client_missions")
async def afficher_missions_client(callback: CallbackQuery):
    missions = get_user_missions(callback.from_user.id)
    if not missions:
        await callback.message.edit_text(
            "📋 <b>Mes missions en cours</b>\n\n"
            "Vous n'avez pas encore de mission enregistrée.",
            parse_mode="HTML",
            reply_markup=clavier_client(get_user_language(callback.from_user.id)),
        )
        await callback.answer()
        return

    text = "📋 <b>Mes dernières missions</b>\n\n" + "\n\n".join(
        html.escape(format_mission_client(mission)) for mission in missions
    )
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=clavier_client(get_user_language(callback.from_user.id)),
    )
    await callback.answer()


@dp.callback_query(F.data == "client_wallet")
async def afficher_wallet_client(callback: CallbackQuery):
    user = get_user_by_telegram_id(callback.from_user.id)
    if user is None:
        await callback.answer("Client introuvable.", show_alert=True)
        return

    await callback.message.edit_text(
        "👛 <b>Mon Wallet Client</b>\n\n"
        f"Solde USD : <b>{user['wallet_balance_usd']:.2f} USD</b>\n"
        f"Solde CDF : <b>{user['wallet_balance_cdf']:.2f} CDF</b>\n\n"
        "Le rechargement wallet sera ajouté avec la vraie API Mobile Money.",
        parse_mode="HTML",
        reply_markup=clavier_client(get_user_language(callback.from_user.id)),
    )
    await callback.answer()


@dp.callback_query(F.data == "client_profil")
async def afficher_profil_client(callback: CallbackQuery):
    user = get_user_by_telegram_id(callback.from_user.id)
    if user is None:
        await callback.answer("Client introuvable.", show_alert=True)
        return

    await callback.message.edit_text(
        "👤 <b>Mon profil client</b>\n\n"
        f"Nom : <b>{html.escape(user['first_name'] or 'Client')}</b>\n"
        f"Téléphone : <b>{html.escape(user['phone_number'])}</b>\n"
        f"Langue : <b>{html.escape(user['language'])}</b>\n"
        f"Missions totales : <b>{user['total_missions']}</b>",
        parse_mode="HTML",
        reply_markup=clavier_client(get_user_language(callback.from_user.id)),
    )
    await callback.answer()


@dp.callback_query(F.data == "prest_missions")
async def afficher_missions_prestataire(callback: CallbackQuery):
    missions = get_provider_missions(callback.from_user.id)
    if not missions:
        await callback.message.edit_text(
            "📋 <b>Mes missions</b>\n\n"
            "Aucune mission attribuée pour l'instant.",
            parse_mode="HTML",
            reply_markup=clavier_prestataire(get_provider_language(callback.from_user.id)),
        )
        await callback.answer()
        return

    text = "📋 <b>Mes dernières missions</b>\n\n" + "\n\n".join(
        html.escape(format_mission_provider(mission)) for mission in missions
    )
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=clavier_prestataire(get_provider_language(callback.from_user.id)),
    )
    await callback.answer()


@dp.callback_query(F.data == "prest_wallet")
async def afficher_wallet_prestataire(callback: CallbackQuery):
    provider = get_provider_by_telegram_id(callback.from_user.id)
    if provider is None:
        await callback.answer("Prestataire introuvable.", show_alert=True)
        return

    await callback.message.edit_text(
        "💰 <b>Mon portefeuille prestataire</b>\n\n"
        f"Solde USD : <b>{provider['wallet_balance_usd']:.2f} USD</b>\n"
        f"Solde CDF : <b>{provider['wallet_balance_cdf']:.2f} CDF</b>\n\n"
        "Les retraits Mobile Money seront ajoutés après l'intégration API.",
        parse_mode="HTML",
        reply_markup=clavier_prestataire(get_provider_language(callback.from_user.id)),
    )
    await callback.answer()


@dp.callback_query(F.data == "prest_profil")
async def afficher_profil_prestataire(callback: CallbackQuery):
    provider = get_provider_by_telegram_id(callback.from_user.id)
    if provider is None:
        await callback.answer("Prestataire introuvable.", show_alert=True)
        return

    await callback.message.edit_text(
        "👤 <b>Mon profil prestataire</b>\n\n"
        f"Nom : <b>{html.escape(provider['full_name'])}</b>\n"
        f"Téléphone : <b>{html.escape(provider['phone_number'])}</b>\n"
        f"Badge : <b>{html.escape(provider['badge'])}</b>\n"
        f"Statut : <b>{html.escape(provider['status'])}</b>\n"
        f"Missions totales : <b>{provider['total_missions']}</b>",
        parse_mode="HTML",
        reply_markup=clavier_prestataire(get_provider_language(callback.from_user.id)),
    )
    await callback.answer()


@dp.callback_query(
    F.data.in_(
        [
            "client_historique",
            "client_aide",
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
