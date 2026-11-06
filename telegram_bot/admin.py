"""Flow admin (Phase 3, groupe admin — voir AGENTS.md/V5_MIGRATION_PLAN.md).

Même contrat que `telegram_bot/registration.py`, `telegram_bot/mission.py` et
`telegram_bot/payment.py` : Router aiogram dédié, `callback.bot`/`message.bot`
plutôt que l'instance globale `bot` (voir la note dans `telegram_bot/mission.py`
sur `from main import`). Six handlers de ce groupe (`admin_accept_service`,
`admin_verify_provider`, `admin_reject_provider`, `admin_suspend_provider`,
`admin_unsuspend_provider`, `admin_reject_service`) utilisaient encore le `bot`
global dans `main.py` — corrigé au passage de l'extraction, sinon un
`from main import bot` aurait été nécessaire et aurait recréé un second
`Bot`/`Dispatcher` (voir la note ci-dessus).

Couvre : tableau de bord admin (stats, prestataires, missions, clients),
résolution des litiges (rembourser / payer le prestataire / partager à
l'amiable — décidée par le registre du backend, voir CONCEPTION_ARGENT.md),
validation des propositions de
service, et vérification/suspension des prestataires (V5_MIGRATION_PLAN.md,
vérification obligatoire).

`is_admin`/`ADMIN_TELEGRAM_ID` sont dupliqués ici plutôt que réimportés depuis
`main.py`, comme `telegram_bot/registration.py` le fait déjà pour la
notification admin à l'inscription — même limitation, pas une régression.
Sans `ADMIN_TELEGRAM_ID`, personne n'est admin (avant, tout le monde l'était).
"""

import html
import os

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from dotenv import load_dotenv

from db import (
    decide_pending_service_request,
    get_admin_stats,
    get_all_providers,
    get_all_users,
    get_disputed_missions,
    get_mission_by_id,
    get_pending_service_requests,
    get_provider_by_id,
    get_provider_by_telegram_id,
    get_recent_missions,
    get_service_request_by_id,
    set_provider_suspended,
    set_provider_verified,
    update_provider_status,
)
from messages import get_message
from telegram_bot.backend_client import (
    BackendUnavailable,
    MoneyRefused,
    _safe_backend_call,
    apply_backend_mission,
    get_provider_language,
    get_user_language,
    money_failure_text,
    decide_payout,
    list_payment_mismatches,
    list_payouts_awaiting_approval,
    resolve_payment_mismatch,
    resolve_dispute,
    sync_provider_status_to_backend,
    sync_provider_suspended_to_backend,
    sync_provider_unsuspended_to_backend,
    sync_provider_verified_to_backend,
    sync_service_request_status_to_backend,
)
from telegram_bot.keyboards import (
    SERVICES,
    clavier_admin_dispute,
    clavier_admin_menu,
    clavier_admin_mismatch,
    clavier_admin_payout,
    clavier_admin_provider,
    clavier_admin_service_request,
)

load_dotenv()
ADMIN_TELEGRAM_ID = os.getenv("ADMIN_TELEGRAM_ID")

router = Router()


def is_admin(telegram_id: int) -> bool:
    # Sans admin configuré, personne n'a accès : ces écrans déplacent de
    # l'argent (litiges) et valident des prestataires.
    if not ADMIN_TELEGRAM_ID:
        return False
    return str(telegram_id) == ADMIN_TELEGRAM_ID


class AdminDisputeSplit(StatesGroup):
    percentage = State()


@router.message(Command("admin"))
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


@router.callback_query(F.data == "admin_home")
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


@router.callback_query(F.data == "admin_stats")
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


@router.callback_query(F.data == "admin_providers")
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
            reply_markup=clavier_admin_provider(provider["telegram_id"]),
        )
    await callback.answer()


@router.callback_query(F.data == "admin_missions")
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


@router.callback_query(F.data == "admin_clients")
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


@router.callback_query(F.data == "admin_disputes")
async def admin_disputes(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Accès admin refusé.", show_alert=True)
        return

    disputes = get_disputed_missions()
    if not disputes:
        await callback.message.edit_text("✅ Aucun litige ouvert.", reply_markup=clavier_admin_menu())
        await callback.answer()
        return

    await callback.message.edit_text("⚠️ <b>Litiges ouverts</b>", parse_mode="HTML", reply_markup=clavier_admin_menu())
    for mission in disputes:
        text = (
            f"NXH-{mission['id']:04d} | {SERVICES.get(mission['service'], mission['service'])}\n"
            f"Client : {mission['client_name'] or 'Client'} | Prestataire : {mission['provider_name'] or 'Non attribué'}\n"
            f"Montant escrow : {mission['total_client']:.2f} {mission['currency']}\n"
            f"Raison : {mission['dispute_reason'] or 'Non précisée'}\n"
            f"Délai résolution : {mission['dispute_deadline'] or 'N/A'}"
        )
        await callback.message.answer(
            html.escape(text),
            reply_markup=clavier_admin_dispute(mission["id"]),
        )
    await callback.answer()


async def _resolve(mission_id: int, decision: str, admin_telegram_id: int, percentage: float | None = None):
    """Décision de litige par le registre du backend.

    Retourne (mission db.py, montants du règlement, None) si elle est
    enregistrée, sinon (None, None, erreur)."""
    try:
        result = await resolve_dispute(mission_id, decision, admin_telegram_id, percentage)
    except (MoneyRefused, BackendUnavailable) as error:
        return None, None, error
    return apply_backend_mission(mission_id, result["mission"]), result["money"]["settlement"], None


@router.callback_query(F.data.startswith("admin_dispute_refund_"))
async def admin_litige_rembourser(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Accès admin refusé.", show_alert=True)
        return

    mission_id = int(callback.data.replace("admin_dispute_refund_", "", 1))
    mission, settlement, error = await _resolve(mission_id, "refund", callback.from_user.id)
    if error is not None:
        await callback.answer(money_failure_text(mission_id, error, "fr"), show_alert=True)
        return

    await callback.message.edit_text(f"💸 Litige NXH-{mission_id:04d} : client remboursé.")

    client_lang = await get_user_language(mission["client_telegram_id"])
    await callback.bot.send_message(
        mission["client_telegram_id"],
        get_message("dispute_resolved_refund_client", client_lang, mission_id=mission_id),
        parse_mode="HTML",
    )
    if mission["provider_telegram_id"]:
        provider_lang = await get_provider_language(mission["provider_telegram_id"])
        await callback.bot.send_message(
            mission["provider_telegram_id"],
            get_message("dispute_resolved_refund_provider", provider_lang, mission_id=mission_id),
            parse_mode="HTML",
        )
    await callback.answer("Client remboursé")


@router.callback_query(F.data.startswith("admin_dispute_release_"))
async def admin_litige_payer_prestataire(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Accès admin refusé.", show_alert=True)
        return

    mission_id = int(callback.data.replace("admin_dispute_release_", "", 1))
    mission, settlement, error = await _resolve(mission_id, "release", callback.from_user.id)
    if error is not None:
        await callback.answer(money_failure_text(mission_id, error, "fr"), show_alert=True)
        return

    await callback.message.edit_text(f"✅ Litige NXH-{mission_id:04d} : prestataire payé.")

    client_lang = await get_user_language(mission["client_telegram_id"])
    await callback.bot.send_message(
        mission["client_telegram_id"],
        get_message("dispute_resolved_release_client", client_lang, mission_id=mission_id),
        parse_mode="HTML",
    )
    if mission["provider_telegram_id"]:
        provider_lang = await get_provider_language(mission["provider_telegram_id"])
        await callback.bot.send_message(
            mission["provider_telegram_id"],
            get_message(
                "dispute_resolved_release_provider",
                provider_lang,
                mission_id=mission_id,
                net=settlement["provider_amount"],
                currency=mission["currency"],
            ),
            parse_mode="HTML",
        )
    await callback.answer("Prestataire payé")


@router.callback_query(F.data.startswith("admin_dispute_split_"))
async def admin_litige_demarrer_partage(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Accès admin refusé.", show_alert=True)
        return

    mission_id = int(callback.data.replace("admin_dispute_split_", "", 1))
    await state.set_state(AdminDisputeSplit.percentage)
    await state.update_data(dispute_split_mission_id=mission_id)
    await callback.message.answer(
        f"🤝 Litige NXH-{mission_id:04d} : quel pourcentage du net prestataire lui revient ?\n\n"
        "Envoie un nombre entre 0 et 100. Le reste du net est remboursé au client ; "
        "la commission Nexis Hub reste acquise. Exemple : 50"
    )
    await callback.answer()


@router.message(AdminDisputeSplit.percentage)
async def admin_litige_partage_recu(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear()
        return

    data = await state.get_data()
    mission_id = data["dispute_split_mission_id"]
    text = (message.text or "").strip().replace(",", ".")
    try:
        percentage = float(text)
    except ValueError:
        await message.answer("Envoie un nombre entre 0 et 100. Exemple : 50")
        return

    mission, settlement, error = await _resolve(mission_id, "split", message.from_user.id, percentage)
    if error is not None:
        # Panne : on garde l'état, l'admin renvoie le même pourcentage.
        if not isinstance(error, BackendUnavailable):
            await state.clear()
        await message.answer(money_failure_text(mission_id, error, "fr"))
        return
    await state.clear()

    provider_share = settlement["provider_amount"]
    client_refund = settlement["client_amount"]
    await message.answer(
        f"🤝 Litige NXH-{mission_id:04d} résolu : {provider_share} {mission['currency']} au "
        f"prestataire, {client_refund} {mission['currency']} remboursés au client, "
        f"{settlement['platform_amount']} {mission['currency']} de commission."
    )

    client_lang = await get_user_language(mission["client_telegram_id"])
    await message.bot.send_message(
        mission["client_telegram_id"],
        get_message(
            "dispute_resolved_split_client",
            client_lang,
            mission_id=mission_id,
            refund=client_refund,
            currency=mission["currency"],
        ),
        parse_mode="HTML",
    )
    if mission["provider_telegram_id"]:
        provider_lang = await get_provider_language(mission["provider_telegram_id"])
        await message.bot.send_message(
            mission["provider_telegram_id"],
            get_message(
                "dispute_resolved_split_provider",
                provider_lang,
                mission_id=mission_id,
                net=provider_share,
                currency=mission["currency"],
            ),
            parse_mode="HTML",
        )


REVIEW_REASONS = {
    "above_auto_limit": "au-dessus du plafond automatique",
    "refund_funds": "contient de l'argent de remboursement",
}


@router.callback_query(F.data == "admin_payouts")
async def admin_payouts(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Accès admin refusé.", show_alert=True)
        return
    try:
        payouts = await list_payouts_awaiting_approval()
    except (MoneyRefused, BackendUnavailable) as error:
        await callback.answer(money_failure_text(0, error, "fr"), show_alert=True)
        return
    if not payouts:
        await callback.message.edit_text("✅ Aucun retrait à valider.", reply_markup=clavier_admin_menu())
        await callback.answer()
        return
    await callback.message.edit_text("💸 <b>Retraits à valider</b>", parse_mode="HTML", reply_markup=clavier_admin_menu())
    for payout in payouts:
        await callback.message.answer(
            html.escape(
                f"Retrait #{payout['id']} | demandé par {payout['requested_by_telegram_id']}\n"
                f"{payout['amount']} {payout['currency']} (frais {payout['fee']}, versé {payout['net']})\n"
                f"Vers {payout['phone']} ({payout['operator']})\n"
                f"À vérifier : {REVIEW_REASONS.get(payout['needs_review_reason'], payout['needs_review_reason'] or '—')}"
            ),
            reply_markup=clavier_admin_payout(payout["id"]),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_payout_ok_") | F.data.startswith("admin_payout_no_"))
async def admin_decider_retrait(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Accès admin refusé.", show_alert=True)
        return
    approve = callback.data.startswith("admin_payout_ok_")
    payout_id = int(callback.data.rsplit("_", 1)[1])
    try:
        payout = await decide_payout(payout_id, approve, callback.from_user.id)
    except (MoneyRefused, BackendUnavailable) as error:
        await callback.answer(money_failure_text(0, error, "fr"), show_alert=True)
        return
    await callback.message.edit_text(f"Retrait #{payout_id} : {payout['status']}.")
    from telegram_bot.dashboard import payout_status_text

    requester = payout["requested_by_telegram_id"]
    lang = await get_provider_language(requester) if get_provider_by_telegram_id(requester) else await get_user_language(requester)
    await callback.bot.send_message(requester, payout_status_text(payout, lang), parse_mode="HTML")
    await callback.answer("Retrait validé" if approve else "Retrait refusé")


MISMATCH_REFUSALS = {
    "gateway_not_confirmed": "L'agrégateur ne confirme plus ce paiement : rien n'a bougé. À vérifier avec lui.",
    "invalid_received_amount": "Montant ou devise reçus illisibles pour le registre : à régler avec l'agrégateur, rien n'a bougé.",
    "reference_mismatch": "La référence de l'agrégateur a changé : rien n'a bougé. À vérifier avec lui.",
    "missing_reference": "L'agrégateur ne donne aucune référence pour ce paiement : rien n'a bougé. À vérifier avec lui.",
    "gateway_unavailable": "L'agrégateur ne répond pas : rien n'a bougé. Réessayez plus tard.",
    "received_amount_too_low": "Montant reçu insuffisant (ou autre devise) pour payer la mission : créditez le wallet du client.",
    "already_paid": "La mission est déjà payée : créditez le wallet du client.",
    "invalid_state": "La mission ne peut plus être payée : créditez le wallet du client.",
    "already_resolved": "Ce paiement a déjà été réglé autrement.",
    "not_admin": "Le backend ne reconnaît pas cet admin (ADMIN_TELEGRAM_ID).",
}


def _received_text(intent: dict) -> str:
    if intent.get("received_amount") is not None:
        return f"{intent['received_amount']} {intent['received_currency']}"
    return intent.get("failure_reason") or "inconnu"


def _can_pay_mission(intent: dict) -> bool:
    try:
        return intent.get("received_currency") == intent["currency"] and float(intent["received_amount"]) >= float(intent["amount"])
    except (TypeError, ValueError):
        return False


@router.callback_query(F.data == "admin_mismatches")
async def admin_montants_differents(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Accès admin refusé.", show_alert=True)
        return
    try:
        intents = await list_payment_mismatches(callback.from_user.id)
    except MoneyRefused as error:
        await callback.answer(MISMATCH_REFUSALS.get(error.code, money_failure_text(0, error, "fr")), show_alert=True)
        return
    except BackendUnavailable as error:
        await callback.answer(money_failure_text(0, error, "fr"), show_alert=True)
        return
    if not intents:
        await callback.message.edit_text("✅ Aucun paiement à montant différent.", reply_markup=clavier_admin_menu())
        await callback.answer()
        return
    await callback.message.edit_text("⚖️ <b>Paiements à montant différent</b>", parse_mode="HTML", reply_markup=clavier_admin_menu())
    for intent in intents:
        await callback.message.answer(
            html.escape(
                f"Paiement #{intent['id']} | mission NXH-{intent['mission_id']:04d} | client {intent['client_telegram_id']}\n"
                f"Demandé : {intent['amount']} {intent['currency']}\n"
                f"Reçu : {_received_text(intent)}\n"
                f"Depuis {intent['phone']} ({intent['operator']}), réf. {intent['gateway_reference'] or '—'}\n"
                "Le montant est relu chez l'agrégateur au moment de votre choix."
            ),
            reply_markup=clavier_admin_mismatch(intent["id"], _can_pay_mission(intent)),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_mismatch_pay_") | F.data.startswith("admin_mismatch_wallet_"))
async def admin_regler_montant_different(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Accès admin refusé.", show_alert=True)
        return
    decision = "pay_mission" if callback.data.startswith("admin_mismatch_pay_") else "credit_wallet"
    intent_id = int(callback.data.rsplit("_", 1)[1])
    try:
        result = await resolve_payment_mismatch(intent_id, decision, callback.from_user.id)
    except MoneyRefused as error:
        await callback.answer(MISMATCH_REFUSALS.get(error.code, money_failure_text(0, error, "fr")), show_alert=True)
        return
    except BackendUnavailable as error:
        await callback.answer(money_failure_text(0, error, "fr"), show_alert=True)
        return
    intent = result["intent"]
    apply_backend_mission(intent["mission_id"], result["mission"])
    outcome = "mission payée, surplus au wallet" if intent["status"] == "mismatch_paid" else "crédité au wallet du client"
    await callback.message.edit_text(
        html.escape(f"Paiement #{intent_id} : {_received_text(intent)} {outcome}. Le client a été prévenu.")
    )
    await callback.answer("Réglé")


@router.callback_query(F.data == "admin_service_requests")
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


async def _decide_service_request(callback: CallbackQuery, request_id: int, status: str, admin_note: str):
    """Applique la décision admin une seule fois (étape C).

    Même règle que le backend V5 : une proposition déjà acceptée ou refusée
    n'est plus retraitée. Avant, un second clic écrasait le statut et
    renotifiait le prestataire. La décision locale fait foi (la Mini App lit
    db.py) ; le backend est mis à jour quand la proposition y a été recopiée.
    """
    request = get_service_request_by_id(request_id)
    if request is None:
        await callback.answer("Proposition introuvable.", show_alert=True)
        return None
    if not decide_pending_service_request(request_id, status, admin_note):
        await callback.answer("Cette proposition a déjà été traitée.", show_alert=True)
        return None
    if request["backend_request_id"] is not None:
        await _safe_backend_call(
            sync_service_request_status_to_backend(request["backend_request_id"], status, admin_note)
        )
    return request


@router.callback_query(F.data.startswith("admin_accept_service_"))
async def admin_accept_service(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Accès admin refusé.", show_alert=True)
        return

    request_id = int(callback.data.replace("admin_accept_service_", "", 1))
    request = await _decide_service_request(callback, request_id, "accepted", "Accepté par Nexis.")
    if request is None:
        return

    await callback.message.edit_text(
        "✅ <b>Service accepté</b>\n\n"
        f"Référence : <b>SRV-{request_id:04d}</b>\n"
        f"Service : <b>{html.escape(request['service_name'])}</b>",
        parse_mode="HTML",
    )
    await callback.bot.send_message(
        request["provider_telegram_id"],
        "✅ <b>Votre proposition de service a été acceptée par Nexis.</b>\n\n"
        f"Service : <b>{html.escape(request['service_name'])}</b>\n\n"
        "Merci. Nexis pourra l'ajouter au catalogue des services proposés.",
        parse_mode="HTML",
    )
    await callback.answer("Service accepté")


def _provider_from_callback(data: str, prefix: str):
    """Prestataire visé par un bouton admin. Boutons actuels : `{prefix}tg_{telegram_id}`,
    l'identifiant commun au bot et au backend. Les anciens boutons déjà envoyés
    dans les chats admin portent encore l'id interne SQLite : toujours acceptés."""
    raw = data.replace(prefix, "", 1)
    try:
        if raw.startswith("tg_"):
            return get_provider_by_telegram_id(int(raw[3:]))
        return get_provider_by_id(int(raw))
    except ValueError:
        return None


@router.callback_query(F.data.startswith("admin_verify_provider_"))
async def admin_verify_provider(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Accès admin refusé.", show_alert=True)
        return

    provider = _provider_from_callback(callback.data, "admin_verify_provider_")
    if provider is None:
        await callback.answer("Prestataire introuvable.", show_alert=True)
        return
    provider = set_provider_verified(provider["id"], True)

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
    await callback.bot.send_message(
        provider["telegram_id"],
        get_message("provider_verified_and_active", provider_lang),
        parse_mode="HTML",
    )
    await callback.answer("Prestataire vérifié")


@router.callback_query(F.data.startswith("admin_reject_provider_"))
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

    provider = _provider_from_callback(callback.data, "admin_reject_provider_")
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
    await callback.bot.send_message(
        provider["telegram_id"],
        get_message("provider_registration_rejected", provider_lang),
        parse_mode="HTML",
    )
    await callback.answer("Prestataire refusé")


@router.callback_query(F.data.startswith("admin_suspend_provider_"))
async def admin_suspend_provider(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Accès admin refusé.", show_alert=True)
        return

    provider = _provider_from_callback(callback.data, "admin_suspend_provider_")
    if provider is None:
        await callback.answer("Prestataire introuvable.", show_alert=True)
        return
    provider = set_provider_suspended(provider["id"], True)

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
    await callback.bot.send_message(
        provider["telegram_id"],
        get_message("provider_suspended_notice", provider_lang),
        parse_mode="HTML",
    )
    await callback.answer("Prestataire suspendu")


@router.callback_query(F.data.startswith("admin_unsuspend_provider_"))
async def admin_unsuspend_provider(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Accès admin refusé.", show_alert=True)
        return

    provider = _provider_from_callback(callback.data, "admin_unsuspend_provider_")
    if provider is None:
        await callback.answer("Prestataire introuvable.", show_alert=True)
        return
    provider = set_provider_suspended(provider["id"], False)

    # Même bug que admin_verify_provider (id interne SQLite au lieu de telegram_id).
    await _safe_backend_call(sync_provider_unsuspended_to_backend(provider["telegram_id"]))

    await callback.message.edit_text(
        f"♻️ Prestataire réactivé : <b>{html.escape(provider['full_name'])}</b>",
        parse_mode="HTML",
        reply_markup=clavier_admin_menu(),
    )
    provider_lang = await get_provider_language(provider["telegram_id"])
    await callback.bot.send_message(
        provider["telegram_id"],
        get_message("provider_unsuspended_notice", provider_lang),
        parse_mode="HTML",
    )
    await callback.answer("Prestataire réactivé")


@router.callback_query(F.data.startswith("admin_reject_service_"))
async def admin_reject_service(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Accès admin refusé.", show_alert=True)
        return

    request_id = int(callback.data.replace("admin_reject_service_", "", 1))
    request = await _decide_service_request(
        callback, request_id, "rejected", "Service non pris en charge pour le moment."
    )
    if request is None:
        return

    await callback.message.edit_text(
        "❌ <b>Service refusé</b>\n\n"
        f"Référence : <b>SRV-{request_id:04d}</b>\n"
        f"Service : <b>{html.escape(request['service_name'])}</b>",
        parse_mode="HTML",
    )
    await callback.bot.send_message(
        request["provider_telegram_id"],
        "❌ <b>Votre proposition de service a été examinée.</b>\n\n"
        f"Service : <b>{html.escape(request['service_name'])}</b>\n\n"
        "Pour le moment, Nexis ne peut pas prendre en charge ce service.",
        parse_mode="HTML",
    )
    await callback.answer("Service refusé")
