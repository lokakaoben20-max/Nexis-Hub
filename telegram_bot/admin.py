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

Qui est admin : le backend le dit (`is_admin`, rôles enregistrés en base par
`python -m backend.app.admins`). Plusieurs personnes peuvent l'être ; sans
réponse du backend, personne ne l'est.
"""

import html

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile, CallbackQuery, InputMediaPhoto, Message
from dotenv import load_dotenv

from messages import get_message
from telegram_bot import backend_client, catalogue
from telegram_bot.backend_client import (
    BackendUnavailable,
    MoneyRefused,
    get_language,
    money_failure_text,
    decide_dispute,
    decide_payout,
    list_payment_mismatches,
    list_payouts_awaiting_approval,
    resolve_payment_mismatch,
)
from telegram_bot.keyboards import (
    SERVICES,
    clavier_admin_client_request,
    clavier_admin_dispute,
    clavier_admin_menu,
    clavier_admin_mismatch,
    clavier_admin_payout,
    clavier_admin_provider,
    clavier_admin_service_addition,
    clavier_admin_service_request,
)

load_dotenv()

router = Router()


ACCESS_REFUSED = "Accès admin refusé."


async def admin_status(telegram_id: int) -> bool | None:
    # Le backend dit qui est admin (rôles en base, plusieurs personnes
    # possibles). Sans réponse (None), personne n'a accès : ces écrans
    # déplacent de l'argent (litiges) et valident des prestataires.
    return await backend_client.admin_status(telegram_id)


async def _access_refusal(telegram_id: int) -> str | None:
    """None si la personne est admin, sinon le texte du refus : le backend
    injoignable n'est pas présenté comme un refus de droit."""
    status = await admin_status(telegram_id)
    if status is True:
        return None
    if status is None:
        return get_message("money_backend_unavailable", "fr")
    return ACCESS_REFUSED


class AdminDisputeSplit(StatesGroup):
    percentage = State()


class AdminAdditionReason(StatesGroup):
    note = State()


STAT_KEYS = (
    "users", "providers", "providers_pending", "missions", "pending_services", "pending_service_additions",
    "pending_client_requests", "disputes",
)


async def _admin_stats(admin_telegram_id: int) -> dict:
    """Comptes des profils, des propositions et des missions, tous lus dans
    le backend. Backend injoignable : « ? » partout, jamais un chiffre local."""
    try:
        stats = await backend_client.admin_mission_stats(admin_telegram_id)
    except (BackendUnavailable, MoneyRefused):
        stats = {}
    return {key: stats.get(key, "?") for key in STAT_KEYS}


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if refusal := await _access_refusal(message.from_user.id):
        await message.answer(refusal)
        return

    stats = await _admin_stats(message.from_user.id)
    await message.answer(
        "🛠️ <b>Tableau admin NEXIS HUB</b>\n\n"
        f"👥 Clients : <b>{stats['users']}</b>\n"
        f"🔧 Prestataires : <b>{stats['providers']}</b> (à vérifier : <b>{stats['providers_pending']}</b>)\n"
        f"📋 Missions : <b>{stats['missions']}</b>\n"
        f"🆕 Services à valider : <b>{stats['pending_service_additions']}</b>\n"
        f"➕ Services en attente : <b>{stats['pending_services']}</b>\n"
        f"🙋 Besoins des clients : <b>{stats['pending_client_requests']}</b>\n"
        f"⚠️ Litiges : <b>{stats['disputes']}</b>",
        parse_mode="HTML",
        reply_markup=clavier_admin_menu(),
    )


@router.message(Command("couper_app"))
async def cmd_couper_app(message: Message):
    """`/couper_app <identifiant Telegram>` : coupe tous les téléphones de
    l'application de cette personne (téléphone volé, compte suspect). Elle
    devra se reconnecter par code ; son argent ne bouge pas. Le backend
    revérifie que l'auteur est l'admin."""
    if refusal := await _access_refusal(message.from_user.id):
        await message.answer(refusal)
        return
    parts = (message.text or "").split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Usage : /couper_app <identifiant Telegram de la personne>")
        return
    try:
        body = await backend_client.admin_revoke_app_devices(message.from_user.id, int(parts[1]))
    except MoneyRefused as refusal:
        if refusal.code == "account_not_found":
            await message.answer("Aucun compte Nexis pour cet identifiant Telegram.")
        else:
            await message.answer(f"Refusé par le backend : {html.escape(refusal.code)}")
        return
    except BackendUnavailable:
        await message.answer("Backend injoignable : aucun téléphone n'a été coupé. Réessaie plus tard.")
        return
    await message.answer(f"📵 Téléphones de l'application coupés : <b>{body['revoked']}</b>.", parse_mode="HTML")


@router.callback_query(F.data == "admin_home")
async def admin_home(callback: CallbackQuery):
    if refusal := await _access_refusal(callback.from_user.id):
        await callback.answer(refusal, show_alert=True)
        return

    stats = await _admin_stats(callback.from_user.id)
    await callback.message.edit_text(
        "🛠️ <b>Tableau admin NEXIS HUB</b>\n\n"
        f"👥 Clients : <b>{stats['users']}</b>\n"
        f"🔧 Prestataires : <b>{stats['providers']}</b> (à vérifier : <b>{stats['providers_pending']}</b>)\n"
        f"📋 Missions : <b>{stats['missions']}</b>\n"
        f"🆕 Services à valider : <b>{stats['pending_service_additions']}</b>\n"
        f"➕ Services en attente : <b>{stats['pending_services']}</b>\n"
        f"🙋 Besoins des clients : <b>{stats['pending_client_requests']}</b>\n"
        f"⚠️ Litiges : <b>{stats['disputes']}</b>",
        parse_mode="HTML",
        reply_markup=clavier_admin_menu(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if refusal := await _access_refusal(callback.from_user.id):
        await callback.answer(refusal, show_alert=True)
        return

    stats = await _admin_stats(callback.from_user.id)
    await callback.message.edit_text(
        "📊 <b>Statistiques</b>\n\n"
        f"Clients : <b>{stats['users']}</b>\n"
        f"Prestataires : <b>{stats['providers']}</b> (à vérifier : <b>{stats['providers_pending']}</b>)\n"
        f"Missions : <b>{stats['missions']}</b>\n"
        f"Nouveaux services à valider : <b>{stats['pending_service_additions']}</b>\n"
        f"Services proposés en attente : <b>{stats['pending_services']}</b>\n"
        f"Litiges ouverts : <b>{stats['disputes']}</b>",
        parse_mode="HTML",
        reply_markup=clavier_admin_menu(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin_providers")
async def admin_providers(callback: CallbackQuery):
    if refusal := await _access_refusal(callback.from_user.id):
        await callback.answer(refusal, show_alert=True)
        return

    try:
        providers = await backend_client.admin_providers(callback.from_user.id)
    except (BackendUnavailable, MoneyRefused) as error:
        await callback.answer(money_failure_text(0, error, "fr", "service_unavailable"), show_alert=True)
        return
    if not providers:
        await callback.message.edit_text("Aucun prestataire enregistré.", reply_markup=clavier_admin_menu())
        await callback.answer()
        return

    await callback.message.edit_text("🔧 <b>Prestataires</b> (les plus anciens d'abord)", parse_mode="HTML", reply_markup=clavier_admin_menu())
    for provider in providers:
        await callback.message.answer(
            f"#{provider['account_id']} | <b>{html.escape(provider['full_name'])}</b>\n"
            f"Tél : {html.escape(provider['phone_number'] or '')}\n"
            f"Badge : {provider['badge']} | Note : {provider['average_rating']:.1f}/5\n"
            f"Statut : {provider['status']} | Vérifié : {'Oui' if provider['is_verified'] else 'Non'}\n"
            f"Suspendu : {'Oui' if provider['is_suspended'] else 'Non'}",
            parse_mode="HTML",
            reply_markup=clavier_admin_provider(provider["account_id"]),
        )
    await callback.answer()


@router.callback_query(F.data == "admin_missions")
async def admin_missions(callback: CallbackQuery):
    if refusal := await _access_refusal(callback.from_user.id):
        await callback.answer(refusal, show_alert=True)
        return

    try:
        missions = await backend_client.admin_list_missions(callback.from_user.id)
    except (BackendUnavailable, MoneyRefused) as error:
        await callback.answer(money_failure_text(0, error, "fr"), show_alert=True)
        return
    if not missions:
        await callback.message.edit_text("Aucune mission enregistrée.", reply_markup=clavier_admin_menu())
        await callback.answer()
        return

    lines = []
    for mission in missions:
        lines.append(
            f"NXH-{mission['mission_id']:04d} | {SERVICES.get(mission['service'], mission['service'])}\n"
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
    if refusal := await _access_refusal(callback.from_user.id):
        await callback.answer(refusal, show_alert=True)
        return

    try:
        users = await backend_client.admin_clients(callback.from_user.id)
    except (BackendUnavailable, MoneyRefused) as error:
        await callback.answer(money_failure_text(0, error, "fr", "service_unavailable"), show_alert=True)
        return
    if not users:
        await callback.message.edit_text("Aucun client enregistré.", reply_markup=clavier_admin_menu())
        await callback.answer()
        return

    lines = [
        f"#{user['account_id']} | {user['first_name'] or 'Client'} | {user['phone_number'] or '-'}"
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
    if refusal := await _access_refusal(callback.from_user.id):
        await callback.answer(refusal, show_alert=True)
        return

    try:
        disputes = await backend_client.admin_list_missions(callback.from_user.id, status="disputed")
    except (BackendUnavailable, MoneyRefused) as error:
        await callback.answer(money_failure_text(0, error, "fr"), show_alert=True)
        return
    if not disputes:
        await callback.message.edit_text("✅ Aucun litige ouvert.", reply_markup=clavier_admin_menu())
        await callback.answer()
        return

    await callback.message.edit_text("⚠️ <b>Litiges ouverts</b>", parse_mode="HTML", reply_markup=clavier_admin_menu())
    for mission in disputes:
        text = (
            f"NXH-{mission['mission_id']:04d} | {SERVICES.get(mission['service'], mission['service'])}\n"
            f"Client : {mission['client_name'] or 'Client'} | Prestataire : {mission['provider_name'] or 'Non attribué'}\n"
            f"Montant escrow : {mission['total_client']:.2f} {mission['currency']}\n"
            f"Raison : {mission['dispute_reason'] or 'Non précisée'}\n"
            f"Délai résolution : {mission['dispute_deadline'] or 'N/A'}"
            f"{_decision_status(mission.get('dispute_decisions') or [])}"
        )
        await callback.message.answer(
            html.escape(text),
            reply_markup=clavier_admin_dispute(mission["mission_id"]),
        )
    await callback.answer()


def _decision_status(decisions: list[dict]) -> str:
    """État de la décision d'un litige, dans la liste admin."""
    if not decisions:
        return ""
    first = decisions[0]
    label = {"refund": "rembourser le client", "release": "payer le prestataire"}.get(
        first["decision"], f"partage, {first.get('percentage')} % au prestataire"
    )
    taken = f"{label} (décidé par {first.get('decided_by_telegram_id')})"
    if first["state"] == "pending":
        return f"\nDécision : {taken}, exécutée le {first['execute_after'][:16].replace('T', ' ')} UTC sauf contestation."
    who = "le client" if first.get("contested_by") == "client" else "le prestataire"
    return (
        f"\nDécision : {taken}, contestée par {who} : {first.get('contest_reason') or ''}\n"
        "À revoir par une autre personne de Nexis Hub que celle de la première décision."
    )


async def _decide(mission_id: int, decision: str, admin_telegram_id: int, percentage: float | None = None):
    """Décision de litige enregistrée par le registre du backend, qui prévient
    lui-même le client et le prestataire.

    Retourne (mission du backend, dernière décision, None) si elle est
    enregistrée, sinon (None, None, erreur)."""
    try:
        result = await decide_dispute(mission_id, decision, admin_telegram_id, percentage)
    except (MoneyRefused, BackendUnavailable) as error:
        return None, None, error
    return result["mission"], result["money"]["dispute_decisions"][-1], None


def _decision_summary(mission_id: int, mission: dict, decision: dict) -> str:
    """Ce que l'admin voit après sa décision : montants figés, et quand
    l'argent bougera."""
    currency = decision["currency"]
    amounts = (
        f"{decision['provider_amount']} {currency} au prestataire, "
        f"{decision['client_amount']} {currency} au client, "
        f"{decision['platform_amount']} {currency} de commission."
    )
    if decision["state"] == "executed":
        return f"⚖️ Litige NXH-{mission_id:04d} : révision appliquée. {amounts} Le client et le prestataire sont prévenus."
    return (
        f"⚖️ Litige NXH-{mission_id:04d} : décision enregistrée. {amounts}\n"
        f"L'argent reste bloqué. Exécution le {decision['execute_after'][:16].replace('T', ' ')} UTC, "
        "sauf contestation du client ou du prestataire. Ils sont prévenus."
    )


async def _admin_decision(admin_telegram_id: int, mission_id: int, decision: str, percentage: float | None = None):
    """(enregistrée, texte pour l'admin, à réessayer car le backend ne répond pas)."""
    mission, recorded, error = await _decide(mission_id, decision, admin_telegram_id, percentage)
    if error is not None:
        return False, money_failure_text(mission_id, error, "fr"), isinstance(error, BackendUnavailable)
    return True, _decision_summary(mission_id, mission, recorded), False


async def _admin_decision_button(callback: CallbackQuery, prefix: str, decision: str) -> None:
    if refusal := await _access_refusal(callback.from_user.id):
        await callback.answer(refusal, show_alert=True)
        return
    mission_id = int(callback.data.replace(prefix, "", 1))
    recorded, text, _ = await _admin_decision(callback.from_user.id, mission_id, decision)
    if not recorded:
        await callback.answer(text, show_alert=True)
        return
    await callback.message.edit_text(text)
    await callback.answer()


@router.callback_query(F.data.startswith("admin_dispute_refund_"))
async def admin_litige_rembourser(callback: CallbackQuery):
    await _admin_decision_button(callback, "admin_dispute_refund_", "refund")


@router.callback_query(F.data.startswith("admin_dispute_release_"))
async def admin_litige_payer_prestataire(callback: CallbackQuery):
    await _admin_decision_button(callback, "admin_dispute_release_", "release")


@router.callback_query(F.data.startswith("admin_dispute_split_"))
async def admin_litige_demarrer_partage(callback: CallbackQuery, state: FSMContext):
    if refusal := await _access_refusal(callback.from_user.id):
        await callback.answer(refusal, show_alert=True)
        return

    mission_id = int(callback.data.replace("admin_dispute_split_", "", 1))
    await state.set_state(AdminDisputeSplit.percentage)
    await state.update_data(dispute_split_mission_id=mission_id)
    await callback.message.answer(
        f"🤝 Litige NXH-{mission_id:04d} : quel pourcentage revient au prestataire ?\n\n"
        "Envoie un nombre entre 0 et 100. Le prestataire reçoit ce pourcentage de son montant, "
        "Nexis Hub garde ce même pourcentage de sa commission, et le client récupère le reste, "
        "frais compris. Le serveur calcule les montants exacts. Exemple : 50"
    )
    await callback.answer()


@router.message(AdminDisputeSplit.percentage)
async def admin_litige_partage_recu(message: Message, state: FSMContext):
    status = await admin_status(message.from_user.id)
    if status is None:
        # Panne : on garde l'état, l'admin renvoie le même pourcentage.
        await message.answer(get_message("money_backend_unavailable", "fr"))
        return
    if not status:
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

    _, text, retry = await _admin_decision(message.from_user.id, mission_id, "split", percentage)
    # Panne : on garde l'état, l'admin renvoie le même pourcentage.
    if not retry:
        await state.clear()
    await message.answer(text)


REVIEW_REASONS = {
    "above_auto_limit": "au-dessus du plafond automatique",
    "refund_funds": "contient de l'argent de remboursement",
}


@router.callback_query(F.data == "admin_payouts")
async def admin_payouts(callback: CallbackQuery):
    if refusal := await _access_refusal(callback.from_user.id):
        await callback.answer(refusal, show_alert=True)
        return
    try:
        payouts = await list_payouts_awaiting_approval(callback.from_user.id)
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
    if refusal := await _access_refusal(callback.from_user.id):
        await callback.answer(refusal, show_alert=True)
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
    lang = await get_language(requester)
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
    "not_admin": "Le backend ne reconnaît pas cet admin (python -m backend.app.admins liste).",
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
    if refusal := await _access_refusal(callback.from_user.id):
        await callback.answer(refusal, show_alert=True)
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
    if refusal := await _access_refusal(callback.from_user.id):
        await callback.answer(refusal, show_alert=True)
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
    outcome = "mission payée, surplus au wallet" if intent["status"] == "mismatch_paid" else "crédité au wallet du client"
    await callback.message.edit_text(
        html.escape(f"Paiement #{intent_id} : {_received_text(intent)} {outcome}. Le client a été prévenu.")
    )
    await callback.answer("Réglé")


@router.callback_query(F.data == "admin_service_requests")
async def admin_service_requests(callback: CallbackQuery):
    if refusal := await _access_refusal(callback.from_user.id):
        await callback.answer(refusal, show_alert=True)
        return

    try:
        requests = await backend_client.admin_service_requests(callback.from_user.id)
    except (BackendUnavailable, MoneyRefused) as error:
        await callback.answer(money_failure_text(0, error, "fr", "service_unavailable"), show_alert=True)
        return
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


# --- Besoins des clients hors catalogue -----------------------------------------


@router.callback_query(F.data == "admin_client_requests")
async def admin_client_requests(callback: CallbackQuery):
    if refusal := await _access_refusal(callback.from_user.id):
        await callback.answer(refusal, show_alert=True)
        return
    try:
        requests = await backend_client.admin_client_requests(callback.from_user.id)
    except (BackendUnavailable, MoneyRefused) as error:
        await callback.answer(money_failure_text(0, error, "fr", "service_unavailable"), show_alert=True)
        return
    if not requests:
        await callback.message.edit_text("✅ Aucun besoin de client en attente.", reply_markup=clavier_admin_menu())
        await callback.answer()
        return
    await callback.message.edit_text(
        f"🙋 <b>Besoins des clients</b>\n\n{len(requests)} besoin(s) hors catalogue en attente de réponse.",
        parse_mode="HTML",
        reply_markup=clavier_admin_menu(),
    )
    for request in requests:
        await callback.message.answer(
            "🙋 <b>Besoin d'un client</b>\n\n"
            f"Référence : <b>BES-{request['id']:04d}</b>\n"
            f"Client : <b>{html.escape(request['client_name'] or 'Client')}</b>\n\n"
            f"{html.escape(request['description'])}",
            parse_mode="HTML",
            reply_markup=clavier_admin_client_request(request["id"]),
        )
    await callback.answer()


CLIENT_REQUEST_REFUSALS = {
    "already_reviewed": "Ce besoin a déjà reçu une réponse.",
    "client_request_not_found": "Besoin introuvable.",
}


@router.callback_query(F.data.startswith("admin_client_need_ok_") | F.data.startswith("admin_client_need_no_"))
async def admin_answer_client_request(callback: CallbackQuery):
    """Réponse appliquée une seule fois par le backend : un second appui (ou
    un second admin) reçoit « déjà répondu » et le client n'est prévenu
    qu'une fois."""
    if refusal := await _access_refusal(callback.from_user.id):
        await callback.answer(refusal, show_alert=True)
        return
    accepted = callback.data.startswith("admin_client_need_ok_")
    request_id = int(callback.data.rsplit("_", 1)[1])
    try:
        request = await backend_client.admin_decide_client_request(
            callback.from_user.id, request_id, "accepted" if accepted else "rejected"
        )
    except MoneyRefused as error:
        await callback.answer(CLIENT_REQUEST_REFUSALS.get(error.code) or money_failure_text(0, error, "fr"), show_alert=True)
        return
    except BackendUnavailable as error:
        await callback.answer(money_failure_text(0, error, "fr", "service_unavailable"), show_alert=True)
        return
    reference = f"BES-{request_id:04d}"
    await callback.message.edit_text(
        f"{'✅ On s’en occupe' if accepted else '❌ Pas encore disponible'} : <b>{reference}</b>\n\n"
        f"{html.escape(request['description'])}",
        parse_mode="HTML",
    )
    if request.get("client_telegram_id"):
        lang = request.get("client_language") or "fr"
        await callback.bot.send_message(
            request["client_telegram_id"],
            get_message("client_need_accepted" if accepted else "client_need_rejected", lang, reference=reference),
            parse_mode="HTML",
        )
    await callback.answer("Réponse envoyée au client")


SERVICE_REQUEST_REFUSALS = {
    "already_reviewed": "Cette proposition a déjà été traitée.",
    "service_request_not_found": "Proposition introuvable.",
}


async def _decide_service_request(callback: CallbackQuery, request_id: int, status: str, admin_note: str):
    """Décision de l'admin, appliquée une seule fois par le backend : un
    second appui (ou un second admin) reçoit « déjà traitée » et le
    prestataire n'est pas prévenu deux fois."""
    try:
        return await backend_client.admin_decide_service_request(callback.from_user.id, request_id, status, admin_note)
    except MoneyRefused as error:
        text = SERVICE_REQUEST_REFUSALS.get(error.code) or money_failure_text(0, error, "fr")
        await callback.answer(text, show_alert=True)
    except BackendUnavailable as error:
        await callback.answer(money_failure_text(0, error, "fr", "service_unavailable"), show_alert=True)
    return None


@router.callback_query(F.data.startswith("admin_accept_service_"))
async def admin_accept_service(callback: CallbackQuery):
    if refusal := await _access_refusal(callback.from_user.id):
        await callback.answer(refusal, show_alert=True)
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


PROVIDER_DECISIONS = {
    # action : (texte pour l'admin, message au prestataire, toast)
    "verify": ("✅ Prestataire vérifié", "provider_verified_and_active", "Prestataire vérifié"),
    "reject": ("❌ Prestataire refusé", "provider_registration_rejected", "Prestataire refusé"),
    "suspend": ("⛔ Prestataire suspendu", "provider_suspended_notice", "Prestataire suspendu"),
    "unsuspend": ("♻️ Prestataire réactivé", "provider_unsuspended_notice", "Prestataire réactivé"),
}
PROVIDER_REFUSALS = {
    "provider_not_found": "Prestataire introuvable.",
    "provider_not_pending": "Ce prestataire n'est plus en attente : décision impossible.",
}


async def _decide_provider(callback: CallbackQuery, action: str) -> None:
    """Vérifier, refuser, suspendre ou réactiver : le backend applique ses
    règles (un vérifié ne se refuse pas, une décision rejouée ne change rien)
    et rend le profil, d'où le message au prestataire dans sa langue.

    Boutons : `admin_<action>_provider_acc_<compte Nexis>`. Les boutons plus
    anciens (identifiant Telegram ou numéro SQLite) ne désignent plus
    personne de façon sûre : refusés, l'admin rouvre la liste."""
    if refusal := await _access_refusal(callback.from_user.id):
        await callback.answer(refusal, show_alert=True)
        return
    raw = callback.data.removeprefix(f"admin_{action}_provider_")
    if not raw.startswith("acc_") or not raw[4:].isdigit():
        await callback.answer("Bouton périmé : rouvre la liste des prestataires depuis /admin.", show_alert=True)
        return
    try:
        provider = await backend_client.admin_decide_provider(callback.from_user.id, int(raw[4:]), action)
    except MoneyRefused as error:
        await callback.answer(PROVIDER_REFUSALS.get(error.code) or money_failure_text(0, error, "fr"), show_alert=True)
        return
    except BackendUnavailable as error:
        await callback.answer(money_failure_text(0, error, "fr", "service_unavailable"), show_alert=True)
        return

    admin_text, provider_message, toast = PROVIDER_DECISIONS[action]
    await callback.message.edit_text(
        f"{admin_text} : <b>{html.escape(provider['full_name'])}</b>",
        parse_mode="HTML",
        reply_markup=clavier_admin_menu(),
    )
    if provider["telegram_id"]:
        provider_lang = provider["language"]
        await callback.bot.send_message(provider["telegram_id"], get_message(provider_message, provider_lang), parse_mode="HTML")
    await callback.answer(toast)


@router.callback_query(F.data.startswith("admin_verify_provider_"))
async def admin_verify_provider(callback: CallbackQuery):
    """Validation : le prestataire devient vérifié et disponible."""
    await _decide_provider(callback, "verify")


@router.callback_query(F.data.startswith("admin_reject_provider_"))
async def admin_reject_provider(callback: CallbackQuery):
    """Refus d'un prestataire en attente (documents insuffisants). Distinct
    de la suspension, qui met en pause un prestataire déjà vérifié."""
    await _decide_provider(callback, "reject")


@router.callback_query(F.data.startswith("admin_suspend_provider_"))
async def admin_suspend_provider(callback: CallbackQuery):
    await _decide_provider(callback, "suspend")


@router.callback_query(F.data.startswith("admin_unsuspend_provider_"))
async def admin_unsuspend_provider(callback: CallbackQuery):
    await _decide_provider(callback, "unsuspend")


@router.callback_query(F.data.startswith("admin_reject_service_"))
async def admin_reject_service(callback: CallbackQuery):
    if refusal := await _access_refusal(callback.from_user.id):
        await callback.answer(refusal, show_alert=True)
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


# --- Nouveau service d'un prestataire vérifié : validé par l'équipe ----------------
# La demande arrive de la Mini App, avec (ou sans) photos de réalisations ; le
# service ne devient actif qu'à l'approbation. Les photos sont lues déchiffrées
# chez le backend (admins seulement) et envoyées ici sans être gardées.

ADDITION_REFUSALS = {
    "already_decided": "Cette demande n'attend plus de décision (déjà décidée autrement, ou annulée par le prestataire).",
    "service_addition_not_found": "Demande introuvable.",
    "too_many_services": "Ce prestataire a déjà le maximum de services : approbation impossible.",
    "invalid_admin_note": "Motif trop long (500 caractères au plus).",
}
MAX_ADMIN_NOTE_LENGTH = 500


def _addition_text(addition: dict) -> str:
    services = ", ".join(catalogue.service_label(key) for key in addition.get("provider_services") or []) or "aucun"
    lines = [
        "🆕 <b>Nouveau service à valider</b>",
        "",
        f"Référence : <b>AJ-{addition['id']:04d}</b>",
        f"Prestataire : <b>{html.escape(addition.get('provider_name') or 'Prestataire')}</b>",
        f"Service demandé : <b>{html.escape(catalogue.service_label(addition['service_key']))}</b>",
        f"Services actuels : {html.escape(services)}",
        f"Photos : <b>{len(addition.get('photo_ids') or [])}</b>",
    ]
    if addition.get("description"):
        lines += ["", html.escape(addition["description"])]
    if addition.get("previously_rejected"):
        note = addition.get("previous_rejection_note")
        lines += ["", "⚠️ Déjà refusé une fois" + (f" : {html.escape(note)}" if note else ".")]
    return "\n".join(lines)


async def _send_addition_photos(callback: CallbackQuery, addition: dict) -> None:
    photos = []
    for index, file_id in enumerate(addition.get("photo_ids") or []):
        try:
            data, _ = await backend_client.admin_file(callback.from_user.id, file_id)
        except (BackendUnavailable, MoneyRefused):
            await callback.message.answer(f"⚠️ Photo {index + 1} illisible pour le moment (AJ-{addition['id']:04d}).")
            continue
        photos.append(InputMediaPhoto(media=BufferedInputFile(data, filename=f"aj-{addition['id']}-{index + 1}.jpg")))
    # Un album Telegram : 2 à 10 photos ; une seule part en photo simple.
    if len(photos) == 1:
        await callback.message.answer_photo(photos[0].media)
    elif photos:
        await callback.message.answer_media_group(photos)


@router.callback_query(F.data == "admin_service_additions")
async def admin_service_additions(callback: CallbackQuery):
    if refusal := await _access_refusal(callback.from_user.id):
        await callback.answer(refusal, show_alert=True)
        return
    try:
        additions = await backend_client.admin_service_additions(callback.from_user.id)
    except (BackendUnavailable, MoneyRefused) as error:
        await callback.answer(money_failure_text(0, error, "fr", "service_unavailable"), show_alert=True)
        return
    if not additions:
        await callback.message.edit_text("✅ Aucun nouveau service à valider.", reply_markup=clavier_admin_menu())
        await callback.answer()
        return
    await callback.message.edit_text(
        f"🆕 <b>Services à valider</b>\n\n{len(additions)} demande(s) de prestataires vérifiés.",
        parse_mode="HTML",
        reply_markup=clavier_admin_menu(),
    )
    await callback.answer()
    for addition in additions:
        await _send_addition_photos(callback, addition)
        await callback.message.answer(
            _addition_text(addition), parse_mode="HTML", reply_markup=clavier_admin_service_addition(addition["id"])
        )


async def _decide_addition(bot, admin_telegram_id: int, addition_id: int, approve: bool, note: str = "") -> tuple[str, bool]:
    """Décision appliquée une seule fois par le backend. Renvoie (texte pour
    l'admin, réessayer) ; le prestataire n'est prévenu que si cette décision
    vient d'être prise (`decided_now`), jamais deux fois."""
    try:
        result = await backend_client.admin_decide_service_addition(admin_telegram_id, addition_id, approve, note)
    except MoneyRefused as error:
        return ADDITION_REFUSALS.get(error.code) or money_failure_text(0, error, "fr"), False
    except BackendUnavailable as error:
        return money_failure_text(0, error, "fr", "service_unavailable"), True
    addition = result["service_addition"]
    reference = f"AJ-{addition_id:04d}"
    label = catalogue.service_label(addition["service_key"])
    if not result.get("decided_now"):
        return f"Déjà fait : {reference} ({label}).", False
    telegram_id = addition.get("provider_telegram_id")
    if telegram_id:
        lang = addition.get("provider_language") or "fr"
        service = html.escape(catalogue.service_label(addition["service_key"], lang))
        if approve:
            text = get_message("service_addition_approved", lang, service=service)
        elif addition.get("admin_note"):
            text = get_message("service_addition_rejected_note", lang, service=service, note=html.escape(addition["admin_note"]))
        else:
            text = get_message("service_addition_rejected", lang, service=service)
        try:
            await bot.send_message(telegram_id, text, parse_mode="HTML")
        except Exception:
            return f"{'✅ Approuvé' if approve else '❌ Refusé'} : {reference} ({label}). Prestataire non prévenu (Telegram).", False
    return f"{'✅ Approuvé' if approve else '❌ Refusé'} : {reference} ({label}).", False


@router.callback_query(F.data.startswith("admin_addition_ok_") | F.data.startswith("admin_addition_no_"))
async def admin_answer_addition(callback: CallbackQuery):
    if refusal := await _access_refusal(callback.from_user.id):
        await callback.answer(refusal, show_alert=True)
        return
    approve = callback.data.startswith("admin_addition_ok_")
    addition_id = int(callback.data.rsplit("_", 1)[1])
    text, retry = await _decide_addition(callback.bot, callback.from_user.id, addition_id, approve)
    if retry:
        await callback.answer(text, show_alert=True)
        return
    await callback.message.edit_text(text)
    await callback.answer()


@router.callback_query(F.data.startswith("admin_addition_why_"))
async def admin_addition_ask_reason(callback: CallbackQuery, state: FSMContext):
    if refusal := await _access_refusal(callback.from_user.id):
        await callback.answer(refusal, show_alert=True)
        return
    addition_id = int(callback.data.rsplit("_", 1)[1])
    await state.set_state(AdminAdditionReason.note)
    await state.update_data(addition_reason_id=addition_id)
    await callback.message.answer(
        f"✍️ AJ-{addition_id:04d} : écris le motif du refus. Le prestataire le recevra tel quel, dans le message "
        "de refus (500 caractères au plus)."
    )
    await callback.answer()


@router.message(AdminAdditionReason.note)
async def admin_addition_reason_received(message: Message, state: FSMContext):
    status = await admin_status(message.from_user.id)
    if status is None:
        # Panne : on garde l'état, l'admin renvoie le même motif.
        await message.answer(get_message("money_backend_unavailable", "fr"))
        return
    if not status:
        await state.clear()
        return
    note = (message.text or "").strip()
    if not note:
        await message.answer("Écris le motif en texte.")
        return
    if len(note) > MAX_ADMIN_NOTE_LENGTH:
        await message.answer(ADDITION_REFUSALS["invalid_admin_note"])
        return
    addition_id = (await state.get_data())["addition_reason_id"]
    text, retry = await _decide_addition(message.bot, message.from_user.id, addition_id, False, note)
    if not retry:
        await state.clear()
    await message.answer(text)
