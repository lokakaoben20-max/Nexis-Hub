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
    WebAppInfo,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv
from aiogram.exceptions import TelegramBadRequest

from messages import get_message
from db import (
    create_service_request,
    get_provider_by_telegram_id,
    get_provider_missions,
    get_provider_service_requests,
    get_user_by_telegram_id,
    get_user_missions,
    init_db,
)
# Phase 3 (voir V5_MIGRATION_PLAN.md) : les flows inscription/profil,
# mission/devis, paiement/lifecycle/notation et admin vivent maintenant dans
# telegram_bot/ (modules séparés, même process — pas encore des services à
# part, voir dp.include_router ci-dessous).
from telegram_bot import admin
from telegram_bot import mission as mission_flow
from telegram_bot import payment
from telegram_bot import registration
from telegram_bot.backend_client import (
    _safe_backend_call,
    fetch_backend_profile,
    get_provider_language,
    get_state_language,
    get_user_language,
    load_profile_from_backend,
    sync_mission_status_to_backend,
    sync_provider_status_to_backend,
)
from telegram_bot.keyboards import (
    MINI_APP_URL,
    SERVICES,
    _rich_cell,
    button_label,
    clavier_client,
    clavier_langue,
    clavier_prestataire,
    clavier_services_actions,
)
from telegram_bot.mission import provider_trust_line


load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
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
dp.include_router(payment.router)
dp.include_router(admin.router)


_original_edit_text = Message.edit_text


async def _safe_edit_text(self, text, *args, **kwargs):
    try:
        return await _original_edit_text(self, text, *args, **kwargs)
    except TelegramBadRequest as exc:
        if "message is not modified" in str(exc).lower():
            return None
        raise


Message.edit_text = _safe_edit_text


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


async def fetch_backend_missions(telegram_id: int) -> list[dict]:
    try:
        async with httpx.AsyncClient(timeout=5.0, headers=BACKEND_AUTH_HEADERS) as client:
            response = await client.get(f"{BACKEND_BASE_URL}/api/profile/{telegram_id}")
            response.raise_for_status()
            payload = response.json()
            return payload.get("client_missions", [])
    except Exception:
        return []


class ProviderServiceRequest(StatesGroup):
    service_name = State()
    description = State()


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
