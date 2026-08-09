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
l'amiable — voir `db.resolve_dispute_*`), validation des propositions de
service, et vérification/suspension des prestataires (V5_MIGRATION_PLAN.md,
vérification obligatoire).

`is_admin`/`ADMIN_TELEGRAM_ID` sont dupliqués ici plutôt que réimportés depuis
`main.py`, comme `telegram_bot/registration.py` le fait déjà pour la
notification admin à l'inscription — même limitation, pas une régression.
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
    get_admin_stats,
    get_all_providers,
    get_all_users,
    get_disputed_missions,
    get_pending_service_requests,
    get_provider_by_id,
    get_recent_missions,
    get_service_request_by_id,
    resolve_dispute_refund_client,
    resolve_dispute_release_provider,
    resolve_dispute_split,
    set_provider_suspended,
    set_provider_verified,
    update_provider_status,
    update_service_request_status,
)
from messages import get_message
from telegram_bot.backend_client import (
    _safe_backend_call,
    get_provider_language,
    get_user_language,
    sync_mission_status_to_backend,
    sync_provider_status_to_backend,
    sync_provider_suspended_to_backend,
    sync_provider_unsuspended_to_backend,
    sync_provider_verified_to_backend,
)
from telegram_bot.keyboards import (
    SERVICES,
    clavier_admin_dispute,
    clavier_admin_menu,
    clavier_admin_provider,
    clavier_admin_service_request,
)

load_dotenv()
ADMIN_TELEGRAM_ID = os.getenv("ADMIN_TELEGRAM_ID")

router = Router()


def is_admin(telegram_id: int) -> bool:
    if not ADMIN_TELEGRAM_ID:
        return True
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
            reply_markup=clavier_admin_provider(provider["id"]),
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


@router.callback_query(F.data.startswith("admin_dispute_refund_"))
async def admin_litige_rembourser(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Accès admin refusé.", show_alert=True)
        return

    mission_id = int(callback.data.replace("admin_dispute_refund_", "", 1))
    try:
        mission = resolve_dispute_refund_client(mission_id)
    except ValueError as error:
        await callback.answer(str(error), show_alert=True)
        return

    await _safe_backend_call(
        sync_mission_status_to_backend(
            mission_id, "cancelled", payment_status="refunded", refund_amount=mission["total_client"]
        )
    )
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
    try:
        mission = resolve_dispute_release_provider(mission_id)
    except ValueError as error:
        await callback.answer(str(error), show_alert=True)
        return

    await _safe_backend_call(sync_mission_status_to_backend(mission_id, "completed", payment_status="released"))
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
                net=f"{mission['net_provider']:.2f}",
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
        f"🤝 Litige NXH-{mission_id:04d} : quel pourcentage du montant escrow va au prestataire ?\n\n"
        "Envoie un nombre entre 0 et 100 (le reste est remboursé au client). Exemple : 50"
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

    try:
        mission = resolve_dispute_split(mission_id, percentage)
    except ValueError as error:
        await message.answer(str(error))
        await state.clear()
        return
    await state.clear()

    client_refund = round(mission["total_client"] - mission["net_provider"], 2)
    await _safe_backend_call(
        sync_mission_status_to_backend(
            mission_id,
            "completed",
            payment_status="released",
            refund_amount=client_refund if client_refund > 0 else None,
            # Sans ça, le backend créditerait le prestataire de son net_provider
            # ORIGINAL (posé au paiement escrow, avant tout litige) au lieu de
            # sa part réduite après partage — sur-crédit trouvé en revue.
            net_provider=mission["net_provider"],
        )
    )
    await message.answer(
        f"🤝 Litige NXH-{mission_id:04d} résolu : {mission['net_provider']:.2f} {mission['currency']} au "
        f"prestataire, {client_refund:.2f} {mission['currency']} remboursés au client."
    )

    client_lang = await get_user_language(mission["client_telegram_id"])
    await message.bot.send_message(
        mission["client_telegram_id"],
        get_message(
            "dispute_resolved_split_client",
            client_lang,
            mission_id=mission_id,
            refund=f"{client_refund:.2f}",
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
                net=f"{mission['net_provider']:.2f}",
                currency=mission["currency"],
            ),
            parse_mode="HTML",
        )


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


@router.callback_query(F.data.startswith("admin_accept_service_"))
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
    await callback.bot.send_message(
        request["provider_telegram_id"],
        "✅ <b>Votre proposition de service a été acceptée par Nexis.</b>\n\n"
        f"Service : <b>{html.escape(request['service_name'])}</b>\n\n"
        "Merci. Nexis pourra l'ajouter au catalogue des services proposés.",
        parse_mode="HTML",
    )
    await callback.answer("Service accepté")


@router.callback_query(F.data.startswith("admin_verify_provider_"))
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
    await callback.bot.send_message(
        request["provider_telegram_id"],
        "❌ <b>Votre proposition de service a été examinée.</b>\n\n"
        f"Service : <b>{html.escape(request['service_name'])}</b>\n\n"
        "Pour le moment, Nexis ne peut pas prendre en charge ce service.",
        parse_mode="HTML",
    )
    await callback.answer("Service refusé")
