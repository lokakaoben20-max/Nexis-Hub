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
    Message,
    RichBlockTableCell,
    WebAppInfo,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv
from aiogram.exceptions import TelegramBadRequest

from messages import get_message
from db import (
    accept_quote,
    create_service_request,
    get_mission_by_id,
    get_admin_stats,
    get_all_providers,
    get_all_users,
    get_disputed_missions,
    get_provider_by_id,
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
    set_provider_suspended,
    set_provider_verified,
    start_mission,
    update_provider_status,
    update_service_request_status,
)
# Phase 3 (voir V5_MIGRATION_PLAN.md) : les flows inscription/profil et
# mission/devis vivent maintenant dans telegram_bot/ (modules séparés, même
# process — pas encore des services à part, voir dp.include_router ci-dessous).
from telegram_bot import mission as mission_flow
from telegram_bot import registration
from telegram_bot.backend_client import (
    _safe_backend_call,
    fetch_backend_profile,
    get_provider_language,
    get_state_language,
    get_user_language,
    load_profile_from_backend,
    sync_provider_status_to_backend,
)
from telegram_bot.keyboards import (
    MINI_APP_URL,
    SERVICES,
    _parse_quote_callback_ids,
    button_label,
    clavier_client,
    clavier_langue,
    clavier_prestataire,
    clavier_services_actions,
)
from telegram_bot.mission import provider_trust_line


load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_TELEGRAM_ID = os.getenv("ADMIN_TELEGRAM_ID")
BACKEND_BASE_URL = os.getenv("BACKEND_BASE_URL", "http://127.0.0.1:8000")
BACKEND_API_KEY = os.getenv("BACKEND_API_KEY", "")
BACKEND_AUTH_HEADERS = {"X-API-Key": BACKEND_API_KEY}

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN manquant dans le fichier .env")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
# Flows extraits (Phase 3) : routers séparés plutôt que des handlers directement
# sur `dp`. Voir telegram_bot/registration.py et telegram_bot/mission.py.
dp.include_router(registration.router)
dp.include_router(mission_flow.router)


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


SERVICE_CALLBACKS = list(SERVICES.keys())

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


async def sync_review_to_backend(mission_id: int, client_telegram_id: int, rating: int, comment: str = "") -> dict:
    payload = {
        "mission_id": mission_id,
        "client_telegram_id": client_telegram_id,
        "rating": rating,
        "comment": comment,
    }
    async with httpx.AsyncClient(timeout=5.0, headers=BACKEND_AUTH_HEADERS) as client:
        response = await client.post(f"{BACKEND_BASE_URL}/api/bot/reviews", json=payload)
        response.raise_for_status()
        return response.json()


async def sync_quote_accept_to_backend(backend_quote_id: int) -> dict:
    async with httpx.AsyncClient(timeout=5.0, headers=BACKEND_AUTH_HEADERS) as client:
        response = await client.post(f"{BACKEND_BASE_URL}/api/bot/quotes/{backend_quote_id}/accept")
        response.raise_for_status()
        return response.json()


async def sync_quote_reject_to_backend(backend_quote_id: int) -> dict:
    async with httpx.AsyncClient(timeout=5.0, headers=BACKEND_AUTH_HEADERS) as client:
        response = await client.post(f"{BACKEND_BASE_URL}/api/bot/quotes/{backend_quote_id}/reject")
        response.raise_for_status()
        return response.json()


async def sync_provider_verified_to_backend(telegram_id: int) -> dict:
    async with httpx.AsyncClient(timeout=5.0, headers=BACKEND_AUTH_HEADERS) as client:
        response = await client.post(f"{BACKEND_BASE_URL}/api/bot/providers/{telegram_id}/verify")
        response.raise_for_status()
        return response.json()


async def sync_provider_suspended_to_backend(telegram_id: int) -> dict:
    async with httpx.AsyncClient(timeout=5.0, headers=BACKEND_AUTH_HEADERS) as client:
        response = await client.post(f"{BACKEND_BASE_URL}/api/bot/providers/{telegram_id}/suspend")
        response.raise_for_status()
        return response.json()


async def sync_provider_unsuspended_to_backend(telegram_id: int) -> dict:
    async with httpx.AsyncClient(timeout=5.0, headers=BACKEND_AUTH_HEADERS) as client:
        response = await client.post(f"{BACKEND_BASE_URL}/api/bot/providers/{telegram_id}/unsuspend")
        response.raise_for_status()
        return response.json()


async def fetch_backend_missions(telegram_id: int) -> list[dict]:
    try:
        async with httpx.AsyncClient(timeout=5.0, headers=BACKEND_AUTH_HEADERS) as client:
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
    async with httpx.AsyncClient(timeout=5.0, headers=BACKEND_AUTH_HEADERS) as client:
        response = await client.post(f"{BACKEND_BASE_URL}/api/bot/missions/status", json=payload)
        response.raise_for_status()
        return response.json()


async def sync_payment_to_backend(quote_id: int, payment_status: str, mission_id: int | None = None) -> dict:
    payload = {"quote_id": quote_id, "payment_status": payment_status}
    if mission_id is not None:
        payload["mission_id"] = mission_id
    async with httpx.AsyncClient(timeout=5.0, headers=BACKEND_AUTH_HEADERS) as client:
        response = await client.post(f"{BACKEND_BASE_URL}/api/bot/payments", json=payload)
        response.raise_for_status()
        return response.json()


class ProviderServiceRequest(StatesGroup):
    service_name = State()
    description = State()


class RatingFlow(StatesGroup):
    rating = State()
    comment = State()


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
    builder.button(text="❌ Refuser", callback_data=f"admin_reject_provider_{provider_id}")
    builder.button(text="⛔ Suspendre", callback_data=f"admin_suspend_provider_{provider_id}")
    builder.button(text="♻️ Réactiver", callback_data=f"admin_unsuspend_provider_{provider_id}")
    builder.button(text="⬅️ Admin", callback_data="admin_home")
    builder.adjust(1)
    return builder.as_markup()


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


def clavier_mini_app(lang: str = "fr"):
    builder = InlineKeyboardBuilder()
    if MINI_APP_URL:
        builder.button(text=button_label("open_mini_app", lang), web_app=WebAppInfo(url=MINI_APP_URL))
    builder.adjust(1)
    return builder.as_markup()


def mission_value(mission, key: str, default=None):
    """Read fields from either a SQLite Row or a backend V5 dictionary."""
    try:
        value = mission[key]
    except (KeyError, IndexError, TypeError):
        return default
    return default if value is None else value


def mission_id(mission) -> int:
    return int(mission_value(mission, "id", mission_value(mission, "mission_id", 0)))


def format_mission_client(mission) -> str:
    service_key = mission_value(mission, "service", "")
    status_key = mission_value(mission, "status", "")
    payment_key = mission_value(mission, "payment_status", "")
    service = SERVICES.get(service_key, service_key)
    status = STATUS_LABELS.get(status_key, status_key)
    payment_status = PAYMENT_STATUS_LABELS.get(payment_key, payment_key)
    provider = mission_value(mission, "provider_name", "Non attribué")
    return (
        f"NXH-{mission_id(mission):04d} | {service}\n"
        f"Commune : {mission_value(mission, 'commune', '')} | Statut : {status}\n"
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

    # Lève le blocage matching posé à l'inscription (V5_MIGRATION_PLAN.md,
    # vérification obligatoire) : find_matching_providers ne filtre que sur
    # status='available', donc c'est ce qui rend le prestataire matchable à nouveau.
    provider = update_provider_status(provider["telegram_id"], "available")

    # Bug corrigé : ces deux appels utilisaient `provider_id` (id interne SQLite,
    # auto-increment) au lieu de `provider["telegram_id"]` (clé primaire côté
    # backend Postgres) — le sync backend échouait silencieusement à tous les coups
    # depuis le début (404 avalé par _safe_backend_call), ou pire, aurait pu agir
    # sur un autre prestataire en cas de collision numérique entre les deux espaces.
    await _safe_backend_call(sync_provider_verified_to_backend(provider["telegram_id"]))
    await _safe_backend_call(sync_provider_status_to_backend(provider["telegram_id"], "available"))

    await callback.message.edit_text(
        f"✅ Prestataire vérifié : <b>{html.escape(provider['full_name'])}</b>",
        parse_mode="HTML",
        reply_markup=clavier_admin_menu(),
    )
    provider_lang = await get_provider_language(provider["telegram_id"])
    await bot.send_message(
        provider["telegram_id"],
        get_message("provider_verified_and_active", provider_lang),
        parse_mode="HTML",
    )
    await callback.answer("Prestataire vérifié")


@dp.callback_query(F.data.startswith("admin_reject_provider_"))
async def admin_reject_provider(callback: CallbackQuery):
    """Refuse un prestataire en attente de validation (V5_MIGRATION_PLAN.md,
    vérification obligatoire). Distinct de admin_suspend_provider : suspendre
    implique "était actif, mis en pause", refuser implique "jamais approuvé,
    documents insuffisants" — messages et statuts différents. `status="rejected"`
    ne correspond à aucune valeur filtrée par find_matching_providers, donc le
    prestataire reste invisible du matching comme s'il était toujours en attente.
    """
    if not is_admin(callback.from_user.id):
        await callback.answer("Accès admin refusé.", show_alert=True)
        return

    provider_id = int(callback.data.replace("admin_reject_provider_", "", 1))
    provider = get_provider_by_id(provider_id)
    if provider is None:
        await callback.answer("Prestataire introuvable.", show_alert=True)
        return

    provider = update_provider_status(provider["telegram_id"], "rejected")
    await _safe_backend_call(sync_provider_status_to_backend(provider["telegram_id"], "rejected"))

    await callback.message.edit_text(
        f"❌ Prestataire refusé : <b>{html.escape(provider['full_name'])}</b>",
        parse_mode="HTML",
        reply_markup=clavier_admin_menu(),
    )
    provider_lang = await get_provider_language(provider["telegram_id"])
    await bot.send_message(
        provider["telegram_id"],
        get_message("provider_registration_rejected", provider_lang),
        parse_mode="HTML",
    )
    await callback.answer("Prestataire refusé")


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

    # Même bug que admin_verify_provider : provider_id (id interne SQLite) au lieu
    # de provider["telegram_id"] (clé primaire backend) — le sync échouait
    # silencieusement depuis le début.
    await _safe_backend_call(sync_provider_suspended_to_backend(provider["telegram_id"]))

    await callback.message.edit_text(
        f"⛔ Prestataire suspendu : <b>{html.escape(provider['full_name'])}</b>",
        parse_mode="HTML",
        reply_markup=clavier_admin_menu(),
    )
    provider_lang = await get_provider_language(provider["telegram_id"])
    await bot.send_message(
        provider["telegram_id"],
        get_message("provider_suspended_notice", provider_lang),
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

    # Même bug que admin_verify_provider (id interne SQLite au lieu de telegram_id).
    await _safe_backend_call(sync_provider_unsuspended_to_backend(provider["telegram_id"]))

    await callback.message.edit_text(
        f"♻️ Prestataire réactivé : <b>{html.escape(provider['full_name'])}</b>",
        parse_mode="HTML",
        reply_markup=clavier_admin_menu(),
    )
    provider_lang = await get_provider_language(provider["telegram_id"])
    await bot.send_message(
        provider["telegram_id"],
        get_message("provider_unsuspended_notice", provider_lang),
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
        if mission_value(mission, "status") in terminal_statuses
    ]

    if not history:
        await callback.message.edit_text(
            get_message("mission_history_empty", lang),
            parse_mode="HTML",
            reply_markup=clavier_client(lang),
        )
        await callback.answer()
        return

    try:
        await callback.message.edit_text(
            rich_message=build_history_rich_message(lang, history),
            reply_markup=clavier_client(lang),
        )
    except Exception:
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
                _rich_cell(f"NXH-{mission_id(mission):04d}"),
                _rich_cell(SERVICES.get(mission_value(mission, "service", ""), mission_value(mission, "service", ""))),
                _rich_cell(STATUS_LABELS.get(mission_value(mission, "status", ""), mission_value(mission, "status", ""))),
                _rich_cell(PAYMENT_STATUS_LABELS.get(mission_value(mission, "payment_status", ""), mission_value(mission, "payment_status", ""))),
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
