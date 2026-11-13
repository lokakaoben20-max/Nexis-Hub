"""Flow inscription/profil : client, prestataire, disponibilité, services,
réglages (langue, prénom).

Router aiogram dédié, inclus par `main.py`. Les profils n'existent que dans le
backend : chaque lecture et chaque écriture passe par les routes /api/me/*,
au nom de la personne qui écrit. Backend injoignable ou refus : la personne
le voit, rien n'est gardé de côté pour être recopié plus tard.
"""

import html
import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove
from dotenv import load_dotenv

from messages import get_message
from telegram_bot import backend_client, catalogue
from telegram_bot.backend_client import (
    BackendUnavailable,
    MoneyRefused,
    get_language,
    get_state_language,
    money_failure_text,
)
from telegram_bot.keyboards import (
    clavier_admin_new_provider,
    clavier_client,
    clavier_communes_prestataire,
    clavier_contact,
    clavier_disponibilite,
    clavier_langue_parametres,
    clavier_modifier_services,
    clavier_parametres_client,
    clavier_portfolio_prestataire,
    clavier_prestataire,
    clavier_profil,
    clavier_services_prestataire,
)

load_dotenv()
logger = logging.getLogger(__name__)

router = Router()


class ClientRegistration(StatesGroup):
    phone = State()


class ProviderRegistration(StatesGroup):
    phone = State()
    full_name = State()
    services = State()
    communes = State()
    # Vérification obligatoire à l'inscription (V5_MIGRATION_PLAN.md) : le
    # prestataire ne devient pas "available" en sortant de ces trois états, il passe
    # par "pending_verification" jusqu'à validation admin — voir
    # terminer_inscription_prestataire / recevoir_portfolio.
    id_document = State()
    selfie = State()
    portfolio = State()


class ProviderServicesEdit(StatesGroup):
    services = State()


class ClientSettings(StatesGroup):
    name = State()


async def _unavailable(callback: CallbackQuery, lang: str, error: Exception | None = None) -> None:
    """Le backend n'a pas répondu (ou a refusé) : rien n'a changé, la personne
    réessaie."""
    text = money_failure_text(0, error, lang, "service_unavailable") if error else get_message("service_unavailable", lang)
    await callback.answer(text, show_alert=True)


async def _choisir_langue(callback: CallbackQuery, state: FSMContext, lang: str, intro: str):
    """Choix de langue à l'écran d'accueil.

    La langue est gardée dans l'étape en cours, puis envoyée avec
    l'inscription. Une personne déjà connue du backend (compte existant) voit
    sa langue changée tout de suite ; une personne inconnue n'a encore rien
    à changer (`account_not_found`).
    """
    try:
        await backend_client.set_my_language(callback.from_user.id, lang)
    except MoneyRefused as error:
        if error.code != "account_not_found":
            await _unavailable(callback, lang, error)
            return
    except BackendUnavailable:
        await _unavailable(callback, lang)
        return
    await state.update_data(language=lang)
    await callback.message.edit_text(
        intro,
        parse_mode="HTML",
        reply_markup=clavier_profil(lang),
    )
    await callback.answer()


@router.callback_query(F.data == "lang_fr")
async def langue_fr(callback: CallbackQuery, state: FSMContext):
    await _choisir_langue(callback, state, "fr", f"🇫🇷 Vous avez choisi le <b>Français</b>.\n\n{get_message('choose_profile', 'fr')}")


@router.callback_query(F.data == "lang_ln")
async def langue_ln(callback: CallbackQuery, state: FSMContext):
    await _choisir_langue(callback, state, "ln", f"🇨🇩 Oponi <b>Lingala</b>.\n\n{get_message('choose_profile', 'ln')}")


@router.callback_query(F.data == "lang_en")
async def langue_en(callback: CallbackQuery, state: FSMContext):
    await _choisir_langue(callback, state, "en", f"🇬🇧 You chose <b>English</b>.\n\n{get_message('choose_profile', 'en')}")


@router.callback_query(F.data == "profil_client")
async def profil_client(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    me = await backend_client.my_profile(callback.from_user.id)
    lang = data.get("language") or (me or {}).get("language") or backend_client.telegram_language(callback.from_user)
    if me is None:
        await _unavailable(callback, lang)
        return
    if me["client"] is None:
        await state.set_state(ClientRegistration.phone)
        await state.update_data(language=lang)
        await callback.message.answer(
            get_message("ask_client_phone", lang),
            reply_markup=clavier_contact(lang),
        )
        await callback.answer()
        return

    await state.clear()
    prenom = html.escape(me["client"].get("first_name") or callback.from_user.first_name or "Client")
    await callback.message.edit_text(
        get_message("client_menu", lang, prenom=prenom),
        parse_mode="HTML",
        reply_markup=clavier_client(lang),
    )
    await callback.answer()


async def _numero_partage(message: Message, lang: str) -> str | None:
    """Numéro de téléphone prouvé par Telegram, ou None après avoir réexpliqué.

    Seul le bouton « Partager mon numéro » est accepté (décision de Ben,
    docs/ARCHITECTURE_WHATSAPP.md) : Telegram envoie alors le numéro vérifié du
    compte. Un numéro tapé à la main, ou la fiche contact de quelqu'un d'autre
    (trombone > Contact), ne prouve rien et est refusé.
    """
    contact = message.contact
    if contact is None:
        await message.answer(get_message("phone_required", lang), reply_markup=clavier_contact(lang))
        return None
    if contact.user_id != message.from_user.id:
        await message.answer(get_message("phone_contact_not_own", lang), reply_markup=clavier_contact(lang))
        return None
    return contact.phone_number


@router.message(ClientRegistration.phone)
async def enregistrer_client(message: Message, state: FSMContext):
    lang = await get_state_language(state)
    phone_number = await _numero_partage(message, lang)
    if phone_number is None:
        return

    try:
        me = await backend_client.save_client_profile(
            message.from_user.id,
            first_name=message.from_user.first_name or "Client",
            phone_number=phone_number,
            language=lang,
            # Numéro reçu par « Partager mon numéro », contact de l'expéditeur.
            phone_verified=True,
        )
    except (BackendUnavailable, MoneyRefused) as error:
        # Rien n'est enregistré : l'étape reste ouverte, la personne renvoie
        # son numéro.
        await message.answer(money_failure_text(0, error, lang, "service_unavailable"), reply_markup=clavier_contact(lang))
        return
    await state.clear()
    prenom = html.escape(me["client"]["first_name"])
    await message.answer(
        get_message("client_registered", lang),
        reply_markup=ReplyKeyboardRemove(),
    )
    await message.answer(
        get_message("client_menu", lang, prenom=prenom),
        parse_mode="HTML",
        reply_markup=clavier_client(lang),
    )


def _provider_menu_text(provider: dict, lang: str) -> str:
    statut = "🟢 Disponible" if provider["status"] == "available" else "🔴 Indisponible"
    return get_message(
        "provider_menu",
        lang,
        prenom=html.escape(provider["full_name"] or "Prestataire"),
        badge=provider["badge"],
        note=f"{provider['average_rating'] or 0:.1f}",
        missions=provider["total_missions"] or 0,
        statut=statut,
    )


@router.callback_query(F.data == "profil_prestataire")
async def profil_prestataire(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    me = await backend_client.my_profile(callback.from_user.id)
    lang = data.get("language") or (me or {}).get("language") or backend_client.telegram_language(callback.from_user)
    if me is None:
        await _unavailable(callback, lang)
        return
    if me["provider"] is None:
        await state.set_state(ProviderRegistration.phone)
        await state.update_data(language=lang)
        await callback.message.answer(
            get_message("ask_provider_phone", lang),
            reply_markup=clavier_contact(lang),
        )
        await callback.answer()
        return

    await state.clear()
    await callback.message.edit_text(
        _provider_menu_text(me["provider"], lang),
        parse_mode="HTML",
        reply_markup=clavier_prestataire(lang),
    )
    await callback.answer()


@router.message(ProviderRegistration.phone)
async def enregistrer_tel_prestataire(message: Message, state: FSMContext):
    lang = await get_state_language(state)
    phone_number = await _numero_partage(message, lang)
    if phone_number is None:
        return

    await state.update_data(provider_phone=phone_number)
    await state.set_state(ProviderRegistration.full_name)
    await message.answer(
        get_message("provider_phone_saved", lang),
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(ProviderRegistration.full_name)
async def enregistrer_nom_prestataire(message: Message, state: FSMContext):
    full_name = (message.text or "").strip()
    if len(full_name) < 2:
        await message.answer(get_message("provider_full_name_invalid", await get_state_language(state)))
        return

    await state.update_data(provider_full_name=full_name, provider_services=[])
    lang = await get_state_language(state)
    await state.set_state(ProviderRegistration.services)
    await message.answer(
        get_message("provider_choose_services", lang),
        reply_markup=clavier_services_prestataire(),
    )


@router.callback_query(ProviderRegistration.services, F.data.startswith("provider_service_"))
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


@router.callback_query(ProviderRegistration.services, F.data == "provider_services_done")
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


@router.callback_query(ProviderRegistration.communes, F.data.startswith("provider_commune_"))
async def choisir_commune_prestataire(callback: CallbackQuery, state: FSMContext):
    commune = catalogue.commune_from_callback(callback.data.replace("provider_", "", 1))
    if commune is None:
        # Bouton d'une commune qui n'est plus au catalogue.
        await callback.answer()
        return
    data = await state.get_data()
    selected = data.get("provider_communes", [])

    if commune in selected:
        selected.remove(commune)
    else:
        selected.append(commune)

    await state.update_data(provider_communes=selected)
    await callback.message.edit_reply_markup(reply_markup=clavier_communes_prestataire(selected))
    await callback.answer()


@router.callback_query(ProviderRegistration.communes, F.data == "provider_communes_done")
async def terminer_inscription_prestataire(callback: CallbackQuery, state: FSMContext):
    """Ne crée plus le prestataire ici — le profil est constitué mais incomplet tant
    que la pièce d'identité et le selfie n'ont pas été soumis (vérification
    obligatoire, V5_MIGRATION_PLAN.md). La création réelle se fait dans
    `finaliser_inscription_prestataire`, une fois tous les documents reçus.
    """
    data = await state.get_data()
    if not data.get("provider_communes"):
        await callback.answer(get_message("choose_one_commune", data.get("language", "fr")), show_alert=True)
        return

    lang = data.get("language", "fr")
    await state.set_state(ProviderRegistration.id_document)
    await callback.message.edit_text(
        get_message("provider_id_document_prompt", lang),
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(ProviderRegistration.id_document)
async def recevoir_document_identite(message: Message, state: FSMContext):
    lang = await get_state_language(state)
    if not message.photo:
        await message.answer(get_message("provider_id_document_invalid", lang))
        return

    await state.update_data(provider_id_document_file_id=message.photo[-1].file_id)
    await state.set_state(ProviderRegistration.selfie)
    await message.answer(get_message("provider_selfie_prompt", lang), parse_mode="HTML")


@router.message(ProviderRegistration.selfie)
async def recevoir_selfie(message: Message, state: FSMContext):
    lang = await get_state_language(state)
    if not message.photo:
        await message.answer(get_message("provider_selfie_invalid", lang))
        return

    await state.update_data(provider_selfie_file_id=message.photo[-1].file_id, provider_portfolio_file_ids=[])
    await state.set_state(ProviderRegistration.portfolio)
    await message.answer(
        get_message("provider_portfolio_prompt", lang),
        parse_mode="HTML",
        reply_markup=clavier_portfolio_prestataire(lang),
    )


@router.message(ProviderRegistration.portfolio)
async def recevoir_portfolio(message: Message, state: FSMContext):
    lang = await get_state_language(state)
    if not message.photo:
        await message.answer(
            get_message("provider_portfolio_invalid", lang),
            reply_markup=clavier_portfolio_prestataire(lang),
        )
        return

    data = await state.get_data()
    portfolio = data.get("provider_portfolio_file_ids", [])
    portfolio.append(message.photo[-1].file_id)
    await state.update_data(provider_portfolio_file_ids=portfolio)
    await message.answer(
        get_message("provider_portfolio_added", lang, count=len(portfolio)),
        reply_markup=clavier_portfolio_prestataire(lang),
    )


@router.callback_query(ProviderRegistration.portfolio, F.data == "provider_portfolio_done")
async def finaliser_inscription_prestataire(callback: CallbackQuery, state: FSMContext):
    """Inscription complète (pièce d'identité, selfie, réalisations) envoyée
    au backend, qui met le prestataire en attente de vérification : invisible
    des clients tant que l'équipe ne l'a pas validé."""
    data = await state.get_data()
    lang = data.get("language", "fr")
    portfolio_file_ids = data.get("provider_portfolio_file_ids", [])
    try:
        me = await backend_client.save_provider_profile(
            callback.from_user.id,
            {
                "full_name": data["provider_full_name"],
                "phone_number": data["provider_phone"],
                "services": data["provider_services"],
                "communes": data["provider_communes"],
                "language": lang,
                "id_document_file_id": data["provider_id_document_file_id"],
                "selfie_file_id": data["provider_selfie_file_id"],
                "portfolio_file_ids": portfolio_file_ids,
                # Numéro reçu par « Partager mon numéro » (enregistrer_tel_prestataire).
                "phone_verified": True,
            },
        )
    except BackendUnavailable:
        # Rien n'est enregistré : l'étape reste ouverte, le même bouton réessaie.
        await _unavailable(callback, lang)
        return
    except MoneyRefused as error:
        await state.clear()
        await callback.message.edit_text(money_failure_text(0, error, lang), reply_markup=clavier_profil(lang))
        await callback.answer()
        return
    provider = me["provider"]

    await state.clear()
    await callback.message.edit_text(
        get_message(
            "provider_registered",
            lang,
            status=provider["status"],
            badge=provider["badge"],
        ),
        parse_mode="HTML",
        reply_markup=clavier_prestataire(lang),
    )
    await callback.answer(get_message("toast_registration_complete", lang))

    await _notifier_admin_nouveau_prestataire(callback, provider, data["provider_id_document_file_id"], data["provider_selfie_file_id"], portfolio_file_ids)


async def _notifier_admin_nouveau_prestataire(callback: CallbackQuery, provider: dict, id_document_file_id: str, selfie_file_id: str, portfolio_file_ids: list[str]) -> None:
    """Prévient chaque admin (liste tenue par le backend) qu'un prestataire
    attend sa vérification. Un envoi raté ne fait jamais échouer l'inscription,
    et n'empêche pas les autres admins d'être prévenus : le prestataire reste
    de toute façon dans la liste des prestataires en attente.
    """
    for admin_id in await backend_client.admin_telegram_ids():
        try:
            await _envoyer_dossier_prestataire(callback, admin_id, provider, id_document_file_id, selfie_file_id, portfolio_file_ids)
        except Exception:
            logger.warning("Dossier du nouveau prestataire non envoyé à un admin", exc_info=True)


async def _envoyer_dossier_prestataire(callback: CallbackQuery, admin_id: int, provider: dict, id_document_file_id: str, selfie_file_id: str, portfolio_file_ids: list[str]) -> None:
    # Langue de l'admin, pas celle du prestataire : c'est l'admin qui lit.
    admin_lang = await get_language(admin_id)
    summary = get_message(
        "admin_new_provider_summary",
        admin_lang,
        nom=html.escape(provider["full_name"]),
        telephone=html.escape(provider["phone_number"] or ""),
        services=html.escape(", ".join(provider["services"])),
        communes=html.escape(", ".join(provider["communes"])),
    )
    await callback.bot.send_message(admin_id, summary, parse_mode="HTML")
    await callback.bot.send_photo(admin_id, id_document_file_id, caption=get_message("admin_new_provider_id_caption", admin_lang))
    await callback.bot.send_photo(admin_id, selfie_file_id, caption=get_message("admin_new_provider_selfie_caption", admin_lang))
    for photo_file_id in portfolio_file_ids:
        await callback.bot.send_photo(admin_id, photo_file_id, caption=get_message("admin_new_provider_portfolio_caption", admin_lang))
    await callback.bot.send_message(
        admin_id,
        get_message("admin_new_provider_approve_prompt", admin_lang),
        reply_markup=clavier_admin_new_provider(provider["account_id"]),
    )


async def _my_provider(callback: CallbackQuery) -> tuple[dict | None, str]:
    """Profil prestataire de la personne, ou None après lui avoir dit
    pourquoi (pas de profil, service indisponible)."""
    me = await backend_client.my_profile(callback.from_user.id)
    if me is None:
        lang = backend_client.telegram_language(callback.from_user)
        await _unavailable(callback, lang)
        return None, lang
    lang = me["language"]
    if me["provider"] is None:
        await callback.answer(get_message("provider_profile_required", lang), show_alert=True)
        return None, lang
    return me["provider"], lang


@router.callback_query(F.data == "prest_dispo")
async def disponibilite_prestataire(callback: CallbackQuery):
    provider, lang = await _my_provider(callback)
    if provider is None:
        return

    status_label = get_message(
        "provider_status_available" if provider["status"] == "available" else "provider_status_offline",
        lang,
    )
    await callback.message.edit_text(
        get_message("provider_availability_title", lang, status=status_label),
        parse_mode="HTML",
        reply_markup=clavier_disponibilite(provider["status"], lang),
    )
    await callback.answer()


# Refus du backend quand le prestataire change sa disponibilité.
AVAILABILITY_REFUSALS = {
    "provider_not_verified": "provider_status_locked",
    "provider_suspended": "provider_suspended_notice",
    "provider_not_found": "provider_profile_required",
}


@router.callback_query(F.data.in_(["provider_status_available", "provider_status_offline"]))
async def changer_disponibilite(callback: CallbackQuery):
    """Disponible ou hors ligne : le backend décide (prestataire vérifié et
    non suspendu seulement ; quitter la pause remet les refus à zéro)."""
    status = "available" if callback.data == "provider_status_available" else "offline"
    lang = await get_language(callback.from_user)
    try:
        me = await backend_client.set_my_availability(callback.from_user.id, status)
    except MoneyRefused as error:
        key = AVAILABILITY_REFUSALS.get(error.code)
        await callback.answer(get_message(key, lang) if key else money_failure_text(0, error, lang), show_alert=True)
        return
    except BackendUnavailable:
        await _unavailable(callback, lang)
        return
    status = me["provider"]["status"]
    status_label = get_message(
        "provider_status_available" if status == "available" else "provider_status_offline",
        lang,
    )
    await callback.message.edit_text(
        get_message("provider_availability_updated", lang, status=status_label),
        parse_mode="HTML",
        reply_markup=clavier_disponibilite(status, lang),
    )
    await callback.answer(get_message("toast_status_updated", lang))


@router.callback_query(F.data == "prest_edit_services")
async def modifier_services_prestataire(callback: CallbackQuery, state: FSMContext):
    provider, lang = await _my_provider(callback)
    if provider is None:
        return

    selected_services = list(provider["services"])
    await state.set_state(ProviderServicesEdit.services)
    await state.update_data(provider_services_edit=selected_services, language=lang)
    await callback.message.edit_text(
        get_message("provider_edit_services", lang),
        parse_mode="HTML",
        reply_markup=clavier_modifier_services(selected_services, lang),
    )
    await callback.answer()


@router.callback_query(ProviderServicesEdit.services, F.data.startswith("edit_service_"))
async def choisir_service_modification(callback: CallbackQuery, state: FSMContext):
    service_key = callback.data.replace("edit_service_", "", 1)
    data = await state.get_data()
    selected = data.get("provider_services_edit", [])

    if service_key in selected:
        selected.remove(service_key)
    else:
        selected.append(service_key)

    await state.update_data(provider_services_edit=selected)
    lang = data.get("language", "fr")
    await callback.message.edit_reply_markup(reply_markup=clavier_modifier_services(selected, lang))
    await callback.answer()


@router.callback_query(ProviderServicesEdit.services, F.data == "edit_services_done")
async def enregistrer_services_modifies(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected = data.get("provider_services_edit", [])
    lang = data.get("language", "fr")
    if not selected:
        await callback.answer(get_message("provider_select_service", lang), show_alert=True)
        return

    try:
        me = await backend_client.set_my_services(callback.from_user.id, selected)
    except BackendUnavailable:
        # La sélection reste à l'écran : le même bouton réessaie.
        await _unavailable(callback, lang)
        return
    except MoneyRefused as error:
        await _unavailable(callback, lang, error)
        return
    await state.clear()
    service_labels = [catalogue.service_label(service, lang) for service in me["provider"]["services"]]
    await callback.message.edit_text(
        get_message("provider_services_updated", lang)
        + "\n\n"
        + "\n".join(f"• {label}" for label in service_labels),
        parse_mode="HTML",
        reply_markup=clavier_prestataire(lang),
    )
    await callback.answer(get_message("toast_services_saved", lang))


@router.callback_query(F.data == "client_profil")
async def afficher_profil_client(callback: CallbackQuery):
    me = await backend_client.my_profile(callback.from_user.id)
    if me is None:
        await _unavailable(callback, backend_client.telegram_language(callback.from_user))
        return
    lang = me["language"]
    client = me["client"]
    if client is None:
        await callback.answer(get_message("client_not_found", lang), show_alert=True)
        return

    lang_labels = {"fr": "Français", "ln": "Lingala", "en": "English"}
    await callback.message.edit_text(
        get_message(
            "profile_title",
            lang,
            name=html.escape(client["first_name"] or "Client"),
            phone=html.escape(client["phone_number"] or get_message("not_provided", lang)),
            lang_label=lang_labels.get(lang, "Français"),
            missions=client["total_missions"],
        ),
        parse_mode="HTML",
        reply_markup=clavier_client(lang),
    )
    await callback.answer()


@router.callback_query(F.data == "prest_profil")
async def afficher_profil_prestataire(callback: CallbackQuery):
    provider, lang = await _my_provider(callback)
    if provider is None:
        return

    status_labels = {
        "available": get_message("provider_status_available", lang),
        "offline": get_message("provider_status_offline", lang),
        "paused": get_message("provider_status_paused", lang),
    }
    status_label = status_labels.get(provider["status"], provider["status"])
    services = ", ".join(catalogue.service_label(service, lang) for service in provider["services"])

    text = get_message(
        "provider_profile_title",
        lang,
        name=html.escape(provider["full_name"] or get_message("provider_default_name", lang)),
        phone=html.escape(provider["phone_number"] or get_message("not_provided", lang)),
        status=html.escape(status_label),
    )
    if services:
        text += "\n" + get_message("provider_profile_services", lang, services=html.escape(services))

    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=clavier_prestataire(lang),
    )
    await callback.answer()


@router.callback_query(F.data == "client_parametres")
async def afficher_parametres_client(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    lang = await get_language(callback.from_user)
    await callback.message.edit_text(
        get_message("settings_title", lang),
        parse_mode="HTML",
        reply_markup=clavier_parametres_client(lang),
    )
    await callback.answer()


@router.callback_query(F.data == "client_menu_from_settings")
async def retour_menu_client(callback: CallbackQuery):
    lang = await get_language(callback.from_user)
    prenom = html.escape(callback.from_user.first_name or "Client")
    await callback.message.edit_text(
        get_message("client_menu", lang, prenom=prenom),
        parse_mode="HTML",
        reply_markup=clavier_client(lang),
    )
    await callback.answer()


@router.callback_query(F.data == "client_settings_language")
async def demander_nouvelle_langue(callback: CallbackQuery):
    lang = await get_language(callback.from_user)
    await callback.message.edit_text(
        get_message("settings_language_prompt", lang),
        parse_mode="HTML",
        reply_markup=clavier_langue_parametres(lang),
    )
    await callback.answer()


async def _appliquer_nouvelle_langue(callback: CallbackQuery, new_lang: str):
    try:
        await backend_client.set_my_language(callback.from_user.id, new_lang)
    except (BackendUnavailable, MoneyRefused) as error:
        await _unavailable(callback, await get_language(callback.from_user), error)
        return
    prenom = html.escape(callback.from_user.first_name or "Client")
    await callback.message.edit_text(
        f"{get_message('settings_language_updated', new_lang)}\n\n"
        f"{get_message('client_menu', new_lang, prenom=prenom)}",
        parse_mode="HTML",
        reply_markup=clavier_client(new_lang),
    )
    await callback.answer()


@router.callback_query(F.data == "settings_lang_fr")
async def modifier_langue_fr(callback: CallbackQuery):
    await _appliquer_nouvelle_langue(callback, "fr")


@router.callback_query(F.data == "settings_lang_ln")
async def modifier_langue_ln(callback: CallbackQuery):
    await _appliquer_nouvelle_langue(callback, "ln")


@router.callback_query(F.data == "settings_lang_en")
async def modifier_langue_en(callback: CallbackQuery):
    await _appliquer_nouvelle_langue(callback, "en")


@router.callback_query(F.data == "client_settings_name")
async def demander_nouveau_nom(callback: CallbackQuery, state: FSMContext):
    lang = await get_language(callback.from_user)
    await state.set_state(ClientSettings.name)
    await callback.message.edit_text(
        get_message("settings_name_prompt", lang),
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(ClientSettings.name)
async def nouveau_nom_recu(message: Message, state: FSMContext):
    lang = await get_language(message.from_user)
    new_name = (message.text or "").strip()
    if not new_name:
        await message.answer(get_message("settings_name_prompt", lang), parse_mode="HTML")
        return

    try:
        me = await backend_client.set_my_name(message.from_user.id, new_name)
    except (BackendUnavailable, MoneyRefused) as error:
        # L'étape reste ouverte : la personne renvoie son prénom.
        await message.answer(money_failure_text(0, error, lang, "service_unavailable"))
        return
    await state.clear()
    await message.answer(
        get_message("settings_name_updated", lang, name=html.escape(me["client"]["first_name"])),
        parse_mode="HTML",
        reply_markup=clavier_client(lang),
    )
