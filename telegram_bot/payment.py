"""Flow paiement / lifecycle / notation (Phase 3, flow 3 — voir V5_MIGRATION_PLAN.md).

Couvre l'acceptation du devis par le client jusqu'à la libération de l'escrow et la
notation du prestataire : paiement (mobile money / wallet), démarrage et fin de
mission côté prestataire, confirmation client, signalement de litige, notation.

Même contrat que `telegram_bot/registration.py` et `telegram_bot/mission.py` : Router
aiogram dédié, `callback.bot`/`message.bot` plutôt que l'instance globale `bot` (voir
la note dans `telegram_bot/mission.py` sur `from main import`).

Argent (voir CONCEPTION_ARGENT.md) : l'acceptation et le refus du devis restent dans
db.py ; tout ce qui suit (paiement, démarrage, fin, confirmation, litige) est une
demande au registre du backend, seule source de vérité. Le bot recopie l'état renvoyé
(`db.apply_backend_mission`) après la réponse, jamais avant. Backend injoignable : rien
ne bouge, l'utilisateur réessaie. La résolution des litiges est une action admin
(telegram_bot/admin.py).
"""

import html

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from db import (
    accept_quote,
    apply_backend_mission,
    get_mission_by_id,
    get_provider_by_telegram_id,
    get_quote_by_id,
    get_user_by_telegram_id,
    reject_quote,
)
from messages import get_message
from telegram_bot import backend_client
from telegram_bot.backend_client import (
    BackendUnavailable,
    MoneyRefused,
    _safe_backend_call,
    detect_operator,
    fetch_backend_profile,
    fetch_wallets,
    get_provider_language,
    get_user_language,
    money_failure_text,
    normalize_phone,
    sync_quote_accept_to_backend,
    sync_quote_reject_to_backend,
    sync_review_to_backend,
    wallet_balance,
)
from telegram_bot.keyboards import (
    _parse_quote_callback_ids,
    build_quote_accept_rich_message,
    clavier_client,
    clavier_confirmation_client,
    clavier_mission_prestataire,
    clavier_notation,
    clavier_notation_commentaire,
    clavier_operateurs,
    clavier_paiement,
    clavier_prestataire,
    clavier_verifier_paiement,
)

router = Router()


class RatingFlow(StatesGroup):
    rating = State()
    comment = State()


class DisputeFlow(StatesGroup):
    reason = State()


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
    balance = wallet_balance(await fetch_wallets(callback.from_user.id), quote["currency"])

    try:
        await callback.message.edit_text(
            rich_message=build_quote_accept_rich_message(
                client_lang,
                mission_id=quote["mission_id"],
                prestataire=quote["provider_name"],
                devis=quote["amount"],
                total=total_client,
                currency=quote["currency"],
                wallet_balance=balance,
            ),
            reply_markup=clavier_paiement(quote_id),
        )
    except Exception:
        await callback.message.edit_text(
            get_message(
                "quote_accept_confirmation" if balance is not None else "quote_accept_confirmation_wallet_unknown",
                client_lang,
                mission_id=quote["mission_id"],
                prestataire=html.escape(quote["provider_name"]),
                devis=quote["amount"],
                total=total_client,
                currency=quote["currency"],
                wallet_balance=balance,
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


async def _payable_quote(callback: CallbackQuery, quote_id: int):
    """Devis que ce client peut payer, ou None (l'alerte est faite)."""
    lang = await get_user_language(callback.from_user.id)
    quote = get_quote_by_id(quote_id)
    if quote is None or quote["client_telegram_id"] != callback.from_user.id:
        await callback.answer(get_message("money_error_not_mission_client" if quote else "money_error_mission_not_found", lang), show_alert=True)
        return None
    if quote["status"] != "accepted":
        # Seul le devis accepté se paie (un ancien bouton d'un devis refusé ou
        # remplacé ne doit pas payer un autre montant ou un autre prestataire).
        await callback.answer(get_message("money_error_invalid_state", lang), show_alert=True)
        return None
    return quote


async def _notify_provider_paid(callback: CallbackQuery, quote, funding: dict, message_key: str):
    provider_lang = await get_provider_language(quote["provider_telegram_id"])
    await callback.bot.send_message(
        quote["provider_telegram_id"],
        get_message(
            message_key,
            provider_lang,
            mission_id=quote["mission_id"],
            brut=float(funding["total"]),
            commission=float(funding["commission"]),
            net=float(funding["net"]),
            currency=quote["currency"],
        ),
        parse_mode="HTML",
        reply_markup=clavier_mission_prestataire(quote["mission_id"], "start", provider_lang),
    )


def _client_phone(telegram_id: int):
    user = get_user_by_telegram_id(telegram_id)
    return normalize_phone(user["phone_number"] if user else None)


async def _show_mobile_money_status(callback: CallbackQuery, result: dict, lang: str, notify_provider):
    """Écran selon le statut de l'intention. `notify_provider` : prévenir le
    prestataire si le paiement vient d'être confirmé par cet appel (sinon le
    backend s'en charge)."""
    intent = result["intent"]
    mission_id = intent["mission_id"]
    apply_backend_mission(mission_id, result["mission"])
    if intent["status"] == "succeeded":
        funding = result["money"]["funding"]
        text = get_message(
            "payment_mobile_confirmed_client", lang,
            mission_id=mission_id, ref=funding["reference"], total=float(funding["total"]), currency=intent["currency"],
        )
        markup = clavier_client(lang)
    elif intent["status"] in ("created", "pending"):
        text = get_message("payment_mobile_pending_client", lang, total=float(intent["amount"]), currency=intent["currency"])
        markup = clavier_verifier_paiement(intent["id"], lang)
    elif intent["status"] == "overpaid":
        text = get_message("payment_overpaid_client", lang, mission_id=mission_id, amount=intent["amount"], currency=intent["currency"])
        markup = clavier_client(lang)
    elif intent["status"] == "mismatch":  # argent reçu, montant différent : l'admin tranche
        text = get_message("payment_mismatch_client", lang, mission_id=mission_id)
        markup = clavier_client(lang)
    elif intent["status"] in ("mismatch_credited", "mismatch_paid"):
        key = "payment_mismatch_credited_client" if intent["status"] == "mismatch_credited" else "payment_mismatch_paid_client"
        text = get_message(key, lang, mission_id=mission_id, amount=intent["received_amount"], currency=intent["received_currency"])
        markup = clavier_client(lang)
    else:  # failed, expired : rien n'a été payé
        text = get_message("payment_mobile_failed_client", lang, mission_id=mission_id)
        markup = clavier_client(lang)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=markup)
    if intent["status"] == "succeeded" and notify_provider is not None:
        await notify_provider(result["money"]["funding"])
    await callback.answer()


@router.callback_query(F.data.startswith("pay_mobile_"))
async def paiement_mobile_money(callback: CallbackQuery):
    """Choix de l'opérateur ; le numéro est celui du profil du client."""
    quote = await _payable_quote(callback, int(callback.data.replace("pay_mobile_", "", 1)))
    if quote is None:
        return
    lang = await get_user_language(callback.from_user.id)
    phone = _client_phone(callback.from_user.id)
    if phone is None:
        await callback.answer(get_message("money_error_invalid_phone", lang), show_alert=True)
        return
    await callback.message.edit_text(
        get_message("choose_operator", lang, total=float(quote["amount"]), currency=quote["currency"], phone=phone),
        parse_mode="HTML",
        reply_markup=clavier_operateurs(f"pay_mm_{quote['id']}", detect_operator(phone), lang),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("pay_mm_"))
async def paiement_mobile_money_operateur(callback: CallbackQuery):
    """Ouvre l'intention de paiement : l'agrégateur envoie la demande sur le
    téléphone du client. Seule sa confirmation paie la mission."""
    quote_part, _, operator = callback.data.removeprefix("pay_mm_").rpartition("_")
    quote = await _payable_quote(callback, int(quote_part))
    if quote is None:
        return
    lang = await get_user_language(callback.from_user.id)
    phone = _client_phone(callback.from_user.id)
    if phone is None:
        await callback.answer(get_message("money_error_invalid_phone", lang), show_alert=True)
        return
    try:
        result = await backend_client.create_payment_intent(get_mission_by_id(quote["mission_id"]), quote, phone, operator)
    except (MoneyRefused, BackendUnavailable) as error:
        await callback.answer(money_failure_text(quote["mission_id"], error, lang), show_alert=True)
        return

    async def notify_provider(funding):
        await _notify_provider_paid(callback, quote, funding, "payment_confirmed_provider_notify")

    await _show_mobile_money_status(callback, result, lang, notify_provider)


@router.callback_query(F.data.startswith("check_mm_"))
async def verifier_paiement_mobile_money(callback: CallbackQuery):
    """Relit le statut chez l'agrégateur. Si le paiement vient d'être confirmé,
    c'est le backend qui prévient client et prestataire (un seul envoi)."""
    intent_id = int(callback.data.removeprefix("check_mm_"))
    lang = await get_user_language(callback.from_user.id)
    try:
        result = await backend_client.refresh_payment_intent(intent_id)
    except (MoneyRefused, BackendUnavailable) as error:
        await callback.answer(money_failure_text(0, error, lang), show_alert=True)
        return
    if result["mission"]["telegram_id"] != callback.from_user.id:
        await callback.answer(get_message("money_error_not_mission_client", lang), show_alert=True)
        return
    await _show_mobile_money_status(callback, result, lang, None)


@router.callback_query(F.data.startswith("mission_start_"))
async def prestataire_demarre_mission(callback: CallbackQuery):
    mission_id = int(callback.data.replace("mission_start_", "", 1))
    provider_lang = await get_provider_language(callback.from_user.id)
    try:
        result = await backend_client.start_mission(mission_id, callback.from_user.id)
    except (MoneyRefused, BackendUnavailable) as error:
        await callback.answer(money_failure_text(mission_id, error, provider_lang), show_alert=True)
        return
    mission = apply_backend_mission(mission_id, result["mission"])

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
    provider_lang = await get_provider_language(callback.from_user.id)
    try:
        result = await backend_client.finish_mission(mission_id, callback.from_user.id)
    except (MoneyRefused, BackendUnavailable) as error:
        await callback.answer(money_failure_text(mission_id, error, provider_lang), show_alert=True)
        return
    mission = apply_backend_mission(mission_id, result["mission"])

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
    lang = await get_user_language(callback.from_user.id)
    try:
        result = await backend_client.confirm_mission(mission_id, callback.from_user.id)
    except (MoneyRefused, BackendUnavailable) as error:
        await callback.answer(money_failure_text(mission_id, error, lang), show_alert=True)
        return
    mission = apply_backend_mission(mission_id, result["mission"])
    settlement = result["money"]["settlement"] or {}

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
                net=settlement.get("provider_amount", f"{mission['net_provider']:.2f}"),
                currency=mission["currency"],
            ),
            parse_mode="HTML",
            reply_markup=clavier_prestataire(provider_lang),
        )

    provider = get_provider_by_telegram_id(mission["provider_telegram_id"]) if mission["provider_telegram_id"] else None
    if provider is not None:
        # Lecture backend-first pour le nom affiché uniquement — l'existence
        # du prestataire (déclenche ou non le flow de notation) reste sur la
        # lecture locale ci-dessus, inchangée.
        backend_profile = await fetch_backend_profile(mission["provider_telegram_id"])
        provider_data = (backend_profile or {}).get("provider") if backend_profile else None
        display_full_name = provider_data.get("full_name") if provider_data else provider["full_name"]
        await state.set_state(RatingFlow.rating)
        await state.update_data(rating_mission_id=mission_id)
        await callback.message.answer(
            get_message("rate_provider", lang, mission_id=mission_id, prestataire=display_full_name),
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
async def client_signale_probleme(callback: CallbackQuery, state: FSMContext):
    mission_id = int(callback.data.replace("client_report_issue_", "", 1))
    await state.set_state(DisputeFlow.reason)
    await state.update_data(dispute_mission_id=mission_id)
    lang = await get_user_language(callback.from_user.id)
    await callback.message.edit_text(
        get_message("dispute_reason_prompt", lang, mission_id=mission_id),
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(DisputeFlow.reason)
async def litige_motif_recu(message: Message, state: FSMContext):
    data = await state.get_data()
    mission_id = data["dispute_mission_id"]
    reason = (message.text or "").strip()
    lang = await get_user_language(message.from_user.id)
    if not reason:
        await message.answer(get_message("dispute_reason_invalid", lang), parse_mode="HTML")
        return

    try:
        result = await backend_client.open_dispute(mission_id, message.from_user.id, reason)
    except BackendUnavailable as error:
        # On garde le motif saisi : le client renvoie le même message quand
        # le service répond de nouveau.
        await message.answer(money_failure_text(mission_id, error, lang), parse_mode="HTML")
        return
    except MoneyRefused as error:
        await state.clear()
        if error.code == "already_settled" and (error.mission or {}).get("payment_status") == "released":
            # Libérée entre-temps (confirmation ou délai de 24 h dépassé).
            apply_backend_mission(mission_id, error.mission)
            text = get_message("dispute_already_released", lang, mission_id=mission_id)
        else:
            text = money_failure_text(mission_id, error, lang)
        await message.answer(text, parse_mode="HTML", reply_markup=clavier_client(lang))
        return
    await state.clear()
    mission = apply_backend_mission(mission_id, result["mission"])

    await message.answer(
        get_message("dispute_opened", lang, mission_id=mission_id),
        parse_mode="HTML",
        reply_markup=clavier_client(lang),
    )
    if mission["provider_telegram_id"]:
        provider_lang = await get_provider_language(mission["provider_telegram_id"])
        await message.bot.send_message(
            mission["provider_telegram_id"],
            get_message("dispute_opened_provider_notify", provider_lang, mission_id=mission_id),
            parse_mode="HTML",
        )


@router.callback_query(F.data.startswith("pay_wallet_"))
async def paiement_wallet(callback: CallbackQuery):
    quote = await _payable_quote(callback, int(callback.data.replace("pay_wallet_", "", 1)))
    if quote is None:
        return
    lang = await get_user_language(callback.from_user.id)
    try:
        result = await backend_client.fund_mission(get_mission_by_id(quote["mission_id"]), quote, "wallet")
    except (MoneyRefused, BackendUnavailable) as error:
        await callback.answer(money_failure_text(quote["mission_id"], error, lang), show_alert=True)
        return
    apply_backend_mission(quote["mission_id"], result["mission"])
    funding = result["money"]["funding"]
    client_lang = await get_user_language(callback.from_user.id)
    await callback.message.edit_text(
        get_message(
            "payment_wallet_confirmed_client",
            client_lang,
            mission_id=quote["mission_id"],
            ref=funding["reference"],
            total=float(funding["total"]),
            currency=quote["currency"],
        ),
        parse_mode="HTML",
        reply_markup=clavier_client(client_lang),
    )
    await _notify_provider_paid(callback, quote, funding, "payment_wallet_confirmed_provider_notify")
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
