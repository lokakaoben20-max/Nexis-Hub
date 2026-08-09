"""Flow missions/wallet (Phase 3, dernier groupe — voir AGENTS.md/V5_MIGRATION_PLAN.md).

Même contrat que `telegram_bot/registration.py`, `telegram_bot/mission.py`,
`telegram_bot/payment.py` et `telegram_bot/admin.py` : Router aiogram dédié,
`callback.bot`/`message.bot` plutôt que l'instance globale `bot`.

Couvre : services du prestataire (affichage, proposition de service
manquant), missions/wallet client et prestataire, historique, aide.

`fetch_backend_missions` réutilise `backend_client.fetch_backend_profile`
(déjà l'endpoint `/api/profile/{telegram_id}`) au lieu de refaire son propre
appel `httpx` comme dans `main.py` — même comportement (liste vide sur tout
échec), sans dupliquer la logique de requête déjà centralisée.
"""

import html
import json

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InputRichBlockDetails,
    InputRichBlockParagraph,
    InputRichBlockTable,
    InputRichMessage,
    Message,
)

from db import (
    create_service_request,
    get_provider_by_telegram_id,
    get_provider_missions,
    get_provider_service_requests,
    get_user_by_telegram_id,
    get_user_missions,
)
from messages import get_message
from telegram_bot.backend_client import fetch_backend_profile, get_provider_language, get_user_language
from telegram_bot.keyboards import SERVICES, _rich_cell, clavier_client, clavier_prestataire, clavier_services_actions

router = Router()


class ProviderServiceRequest(StatesGroup):
    service_name = State()
    description = State()


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
    profile = await fetch_backend_profile(telegram_id)
    return profile.get("client_missions", []) if isinstance(profile, dict) else []


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


@router.callback_query(F.data == "prest_services")
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


@router.callback_query(F.data == "prest_missing_service")
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


@router.message(ProviderServiceRequest.service_name)
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


@router.message(ProviderServiceRequest.description)
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


@router.callback_query(F.data == "client_missions")
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
        html.escape(format_mission_client(mission)) if mission_value(mission, "service") is not None else html.escape(str(mission))
        for mission in missions
    )
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=clavier_client(lang),
    )
    await callback.answer()


@router.callback_query(F.data == "client_wallet")
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


@router.callback_query(F.data == "prest_missions")
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


@router.callback_query(F.data == "prest_wallet")
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


@router.callback_query(F.data == "client_historique")
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


@router.callback_query(F.data == "client_aide")
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
