"""Flow paiement / lifecycle / notation (Phase 3, flow 3 — voir V5_MIGRATION_PLAN.md).

Couvre l'acceptation du devis par le client jusqu'à la libération de l'escrow et la
notation du prestataire : paiement (mobile money / wallet), démarrage et fin de
mission côté prestataire, confirmation client, signalement de litige, notation.

Même contrat que `telegram_bot/registration.py` et `telegram_bot/mission.py` : Router
aiogram dédié, double écriture backend + `db.py` maintenue côté paiement/mission,
`callback.bot`/`message.bot` plutôt que l'instance globale `bot` (voir la note dans
`telegram_bot/mission.py` sur `from main import`).

Trouvaille connue, pas corrigée ici (décision produit à trancher séparément — voir
AGENTS.md) : `client_signale_probleme` affiche un message de litige mais ne pose
aucun statut `disputed` réel ni ne gèle `release_payment`.
"""

import html

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from db import (
    accept_quote,
    finish_mission,
    get_provider_by_telegram_id,
    get_user_by_telegram_id,
    mark_quote_paid,
    mark_quote_paid_with_wallet,
    reject_quote,
    release_payment,
    start_mission,
)
from messages import get_message
from telegram_bot.backend_client import (
    _safe_backend_call,
    get_provider_language,
    get_user_language,
    sync_mission_status_to_backend,
    sync_payment_to_backend,
    sync_quote_accept_to_backend,
    sync_quote_reject_to_backend,
    sync_review_to_backend,
)
from telegram_bot.keyboards import (
    _parse_quote_callback_ids,
    build_quote_accept_rich_message,
    clavier_client,
    clavier_confirmation_client,
    clavier_mission_prestataire,
    clavier_notation,
    clavier_notation_commentaire,
    clavier_paiement,
    clavier_prestataire,
)

router = Router()


class RatingFlow(StatesGroup):
    rating = State()
    comment = State()


@router.callback_query(F.data.startswith("client_accept_quote_"))
async def client_accepte_devis(callback: CallbackQuery):
    quote_id, backend_quote_id = _parse_quote_callback_ids(callback.data.replace("client_accept_quote_", "", 1))
    try:
        quote = accept_quote(quote_id, callback.from_user.id)
    except ValueError as error:
        await callback.answer(str(error), show_alert=True)
        return
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
    await callback.bot.send_message(
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


@router.callback_query(F.data.startswith("pay_mobile_"))
async def paiement_mobile_money(callback: CallbackQuery):
    quote_id = int(callback.data.replace("pay_mobile_", "", 1))
    try:
        payment = mark_quote_paid(quote_id, callback.from_user.id, operator="mobile_money_simulation")
    except ValueError as error:
        await callback.answer(str(error), show_alert=True)
        return
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
    await callback.bot.send_message(
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


@router.callback_query(F.data.startswith("mission_start_"))
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
    await callback.bot.send_message(
        mission["client_telegram_id"],
        get_message("mission_started", client_lang, mission_id=mission_id),
        parse_mode="HTML",
    )
    await callback.answer(get_message("toast_mission_started", provider_lang))


@router.callback_query(F.data.startswith("mission_finish_"))
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
    await callback.bot.send_message(
        mission["client_telegram_id"],
        get_message("mission_finished_client", client_lang, mission_id=mission_id),
        parse_mode="HTML",
        reply_markup=clavier_confirmation_client(mission_id),
    )
    await callback.answer(get_message("toast_client_notified", provider_lang))


@router.callback_query(F.data.startswith("client_confirm_done_"))
async def client_confirme_mission_terminee(callback: CallbackQuery, state: FSMContext):
    mission_id = int(callback.data.replace("client_confirm_done_", "", 1))
    try:
        mission = release_payment(mission_id, callback.from_user.id)
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
        await callback.bot.send_message(
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


@router.callback_query(RatingFlow.rating, F.data.startswith("rate_star_"))
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


@router.callback_query(RatingFlow.rating, F.data.startswith("rate_skip_"))
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


@router.message(RatingFlow.comment)
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


@router.callback_query(RatingFlow.comment, F.data.startswith("rate_comment_skip_"))
async def notation_commentaire_ignore(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = await get_user_language(callback.from_user.id)
    result = await _finalize_review(callback.from_user.id, data, None, state)
    if result is None:
        await callback.answer(get_message("rate_save_failed", lang), show_alert=True)
        return
    await callback.message.edit_text(get_message("rate_thanks", lang), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("client_report_issue_"))
async def client_signale_probleme(callback: CallbackQuery):
    mission_id = int(callback.data.replace("client_report_issue_", "", 1))
    lang = await get_user_language(callback.from_user.id)
    await callback.message.edit_text(
        get_message("dispute_opened", lang, mission_id=mission_id),
        parse_mode="HTML",
        reply_markup=clavier_client(lang),
    )
    await callback.answer(get_message("toast_dispute_opened", lang))


@router.callback_query(F.data.startswith("pay_wallet_"))
async def paiement_wallet(callback: CallbackQuery):
    quote_id = int(callback.data.replace("pay_wallet_", "", 1))
    try:
        payment = mark_quote_paid_with_wallet(quote_id, callback.from_user.id, operator="wallet")
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
    await callback.bot.send_message(
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


@router.callback_query(F.data.startswith("client_reject_quote_"))
async def client_refuse_devis(callback: CallbackQuery):
    quote_id, backend_quote_id = _parse_quote_callback_ids(callback.data.replace("client_reject_quote_", "", 1))
    try:
        quote = reject_quote(quote_id, callback.from_user.id)
    except ValueError as error:
        await callback.answer(str(error), show_alert=True)
        return
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
    await callback.bot.send_message(
        quote["provider_telegram_id"],
        get_message("quote_rejected_provider_notify", provider_lang, mission_id=quote["mission_id"]),
        parse_mode="HTML",
    )
    await callback.answer(get_message("toast_quote_rejected", client_lang))
