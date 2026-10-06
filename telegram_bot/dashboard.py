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
    set_service_request_backend_id,
)
from messages import MESSAGES, get_message
from telegram_bot.backend_client import (
    BackendUnavailable,
    MoneyRefused,
    _safe_backend_call,
    detect_operator,
    fetch_backend_profile,
    fetch_wallets,
    get_provider_language,
    get_user_language,
    normalize_phone,
    request_payout,
    sync_service_request_to_backend,
    wallet_balance,
)
from telegram_bot.keyboards import (
    SERVICES,
    _rich_cell,
    clavier_client,
    clavier_devises_retrait,
    clavier_operateurs,
    clavier_prestataire,
    clavier_services_actions,
    clavier_wallet,
)

router = Router()


class WithdrawFlow(StatesGroup):
    amount = State()
    operator = State()


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


async def fetch_backend_provider_missions(telegram_id: int) -> list[dict]:
    """Retourne les missions attribuées au prestataire depuis le profil V5.

    Une liste vide garde le même contrat que ``fetch_backend_missions`` :
    l'appelant peut alors réutiliser les données SQLite locales si le backend
    est indisponible ou ne contient pas encore de mission synchronisée.
    """
    profile = await fetch_backend_profile(telegram_id)
    return profile.get("provider_missions", []) if isinstance(profile, dict) else []


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
    """Formate indifféremment une mission SQLite ou une mission du backend V5."""
    service_key = mission_value(mission, "service", "")
    status_key = mission_value(mission, "status", "")
    payment_key = mission_value(mission, "payment_status", "")
    service = SERVICES.get(service_key, service_key)
    status = STATUS_LABELS.get(status_key, status_key)
    payment_status = PAYMENT_STATUS_LABELS.get(payment_key, payment_key)
    client = mission_value(mission, "client_name", "Client")
    return (
        f"NXH-{mission_id(mission):04d} | {service}\n"
        f"Client : {client} | Commune : {mission_value(mission, 'commune', '')}\n"
        f"Statut : {status} | Paiement : {payment_status}"
    )


@router.callback_query(F.data == "prest_services")
async def afficher_services_prestataire(callback: CallbackQuery):
    provider = get_provider_by_telegram_id(callback.from_user.id)
    lang = await get_provider_language(callback.from_user.id)
    if provider is None:
        await callback.answer(get_message("provider_profile_required", lang), show_alert=True)
        return

    # Lecture backend-first : `services` y est déjà une liste Python (colonne
    # JSON SQLAlchemy), pas une chaîne à parser comme côté db.py. Repli local
    # identique à avant si le backend ne répond pas.
    backend_profile = await fetch_backend_profile(callback.from_user.id)
    provider_data = (backend_profile or {}).get("provider") if backend_profile else None
    if provider_data is not None:
        selected_services = provider_data.get("services") or []
    else:
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
    # Vidé avant l'appel backend (jusqu'à 5 s) : un second message pendant
    # l'attente ne doit pas créer une seconde proposition.
    await state.clear()
    # Double écriture (étape C) : la Mini App crée et lit ses propositions
    # uniquement dans db.py, donc l'écriture locale reste la référence (et le
    # numéro SRV- affiché). On garde l'id backend pour que la décision admin
    # puisse être recopiée au backend.
    backend_result = await _safe_backend_call(
        sync_service_request_to_backend(message.from_user.id, data["missing_service_name"], description)
    )
    backend_request = (backend_result or {}).get("service_request") if isinstance(backend_result, dict) else None
    if isinstance(backend_request, dict) and backend_request.get("id") is not None:
        set_service_request_backend_id(request_id, backend_request["id"])
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


async def wallet_text(telegram_id: int, title_key: str, lang: str) -> str:
    """Écran wallet : soldes lus dans le registre du backend, seule source de
    vérité. Backend injoignable = « solde indisponible », jamais un chiffre
    local (il n'y en a plus)."""
    wallets = await fetch_wallets(telegram_id)
    usd = wallet_balance(wallets, "USD")
    cdf = wallet_balance(wallets, "CDF")
    if usd is None or cdf is None:
        return get_message("wallet_unavailable", lang)
    return get_message(title_key, lang, usd=usd, cdf=cdf)


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
        await wallet_text(callback.from_user.id, "wallet_title", lang),
        parse_mode="HTML",
        reply_markup=clavier_wallet("profil_client", lang),
    )
    await callback.answer()


@router.callback_query(F.data == "prest_missions")
async def afficher_missions_prestataire(callback: CallbackQuery):
    lang = await get_provider_language(callback.from_user.id)
    local_missions = get_provider_missions(callback.from_user.id)
    backend_missions = await fetch_backend_provider_missions(callback.from_user.id)
    missions = backend_missions or local_missions
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
        await wallet_text(callback.from_user.id, "provider_wallet_title", lang),
        parse_mode="HTML",
        reply_markup=clavier_wallet("profil_prestataire", lang),
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


# --- Retrait vers Mobile Money (CONCEPTION_MOBILE_MONEY.md) ------------------------
# Le backend bloque le montant, puis l'envoie quand l'admin l'a validé (ou
# tout de suite sous le plafond d'automatisation). Le numéro est celui du
# profil : prestataire s'il en a un, sinon client.


async def _withdraw_language(telegram_id: int) -> str:
    if get_provider_by_telegram_id(telegram_id) is not None:
        return await get_provider_language(telegram_id)
    return await get_user_language(telegram_id)


def _profile_phone(telegram_id: int):
    profile = get_provider_by_telegram_id(telegram_id) or get_user_by_telegram_id(telegram_id)
    return normalize_phone(profile["phone_number"] if profile else None)


def payout_status_text(payout: dict, lang: str) -> str:
    keys = {
        "awaiting_approval": "payout_awaiting_approval",
        "processing": "payout_processing",
        "succeeded": "payout_succeeded",
    }
    return get_message(
        keys.get(payout["status"], "payout_returned"), lang,
        amount=payout["net"], gross=payout["amount"], currency=payout["currency"],
    )


@router.callback_query(F.data == "wallet_withdraw")
async def retrait_choisir_devise(callback: CallbackQuery, state: FSMContext):
    lang = await _withdraw_language(callback.from_user.id)
    await state.clear()
    await callback.message.edit_text(get_message("withdraw_choose_currency", lang), parse_mode="HTML", reply_markup=clavier_devises_retrait(lang))
    await callback.answer()


@router.callback_query(F.data.startswith("wd_cur_"))
async def retrait_demander_montant(callback: CallbackQuery, state: FSMContext):
    currency = callback.data.removeprefix("wd_cur_")
    lang = await _withdraw_language(callback.from_user.id)
    balance = wallet_balance(await fetch_wallets(callback.from_user.id), currency)
    if balance is None:
        await callback.answer(get_message("money_backend_unavailable", lang), show_alert=True)
        return
    await state.set_state(WithdrawFlow.amount)
    await state.update_data(withdraw_currency=currency)
    await callback.message.edit_text(
        get_message("withdraw_ask_amount", lang, currency=currency, balance=f"{balance:.2f}"), parse_mode="HTML"
    )
    await callback.answer()


@router.message(WithdrawFlow.amount)
async def retrait_montant_recu(message: Message, state: FSMContext):
    lang = await _withdraw_language(message.from_user.id)
    try:
        amount = round(float((message.text or "").strip().replace(",", ".")), 2)
    except ValueError:
        amount = 0
    if amount <= 0:
        await message.answer(get_message("withdraw_invalid_amount", lang), parse_mode="HTML")
        return
    phone = _profile_phone(message.from_user.id)
    if phone is None:
        await state.clear()
        await message.answer(get_message("money_error_invalid_phone", lang), parse_mode="HTML")
        return
    data = await state.get_data()
    await state.update_data(withdraw_amount=amount, withdraw_phone=phone)
    await state.set_state(WithdrawFlow.operator)
    await message.answer(
        get_message("withdraw_choose_operator", lang, amount=f"{amount:.2f}", currency=data["withdraw_currency"], phone=phone),
        parse_mode="HTML",
        reply_markup=clavier_operateurs("wd_op", detect_operator(phone), lang),
    )


@router.callback_query(WithdrawFlow.operator, F.data.startswith("wd_op_"))
async def retrait_operateur_recu(callback: CallbackQuery, state: FSMContext):
    lang = await _withdraw_language(callback.from_user.id)
    data = await state.get_data()
    try:
        payout = await request_payout(
            callback.from_user.id, data["withdraw_amount"], data["withdraw_currency"], data["withdraw_phone"],
            callback.data.removeprefix("wd_op_"),
        )
    except BackendUnavailable:
        # On garde la saisie : la personne réessaie le même bouton.
        await callback.answer(get_message("money_backend_unavailable", lang), show_alert=True)
        return
    except MoneyRefused as error:
        await state.clear()
        key = f"money_error_{error.code}"
        await callback.message.edit_text(get_message(key if key in MESSAGES["fr"] else "money_error_generic", lang), parse_mode="HTML")
        await callback.answer()
        return
    await state.clear()
    await callback.message.edit_text(payout_status_text(payout, lang), parse_mode="HTML")
    await callback.answer()
