"""Flow inscription/profil (Phase 3, pilote — voir V5_MIGRATION_PLAN.md).

Handlers déplacés depuis `main.py`, sur un `Router` aiogram dédié plutôt qu'un import
direct de `dp` (le pattern standard pour répartir des handlers entre fichiers sans
état partagé implicite). `main.py` fait `dp.include_router(router)` après avoir défini
tout ce dont ce module a besoin en retour — voir le commentaire à cet endroit.

Double écriture maintenue (backend V5 + `db.py`) pour toutes les écritures : le flow
mission/matching (`find_matching_providers`) et la Mini App lisent encore `db.py` pour
le statut/les services/la langue du prestataire. Couper l'écriture locale ici les
ferait lire une donnée périmée — ce sera fait quand ce flow sera migré à son tour.
Lecture déjà backend-first (héritée de la Phase 1), sauf pour `profil_prestataire` et
`modifier_services_prestataire`, corrigés dans cette extraction (voir commentaires).
"""

import html
import json
import os

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove
from dotenv import load_dotenv

from db import (
    create_provider,
    get_provider_by_telegram_id,
    get_user_by_telegram_id,
    reset_consecutive_ignored,
    update_provider_language,
    update_provider_services,
    update_provider_status,
    update_provider_verification_documents,
    update_user_language,
    update_user_name,
)
from messages import get_message
from telegram_bot.backend_client import (
    _safe_backend_call,
    fetch_backend_profile,
    get_provider_language,
    get_state_language,
    get_user_language,
    load_profile_from_backend,
    persist_client_registration,
    sync_provider_ignored_reset_to_backend,
    sync_provider_language_to_backend,
    sync_provider_services_to_backend,
    sync_provider_status_to_backend,
    sync_provider_to_backend,
    sync_user_language_to_backend,
    sync_user_name_to_backend,
)
from telegram_bot.keyboards import (
    COMMUNES,
    SERVICES,
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
ADMIN_TELEGRAM_ID = os.getenv("ADMIN_TELEGRAM_ID")

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


@router.callback_query(F.data == "lang_fr")
async def langue_fr(callback: CallbackQuery, state: FSMContext):
    await state.update_data(language="fr")
    update_user_language(callback.from_user.id, "fr")
    update_provider_language(callback.from_user.id, "fr")
    await _safe_backend_call(sync_user_language_to_backend(callback.from_user.id, "fr"))
    await _safe_backend_call(sync_provider_language_to_backend(callback.from_user.id, "fr"))
    await callback.message.edit_text(
        f"🇫🇷 Vous avez choisi le <b>Français</b>.\n\n{get_message('choose_profile', 'fr')}",
        parse_mode="HTML",
        reply_markup=clavier_profil("fr"),
    )
    await callback.answer()


@router.callback_query(F.data == "lang_ln")
async def langue_ln(callback: CallbackQuery, state: FSMContext):
    await state.update_data(language="ln")
    update_user_language(callback.from_user.id, "ln")
    update_provider_language(callback.from_user.id, "ln")
    await _safe_backend_call(sync_user_language_to_backend(callback.from_user.id, "ln"))
    await _safe_backend_call(sync_provider_language_to_backend(callback.from_user.id, "ln"))
    await callback.message.edit_text(
        f"🇨🇩 Oponi <b>Lingala</b>.\n\n{get_message('choose_profile', 'ln')}",
        parse_mode="HTML",
        reply_markup=clavier_profil("ln"),
    )
    await callback.answer()


@router.callback_query(F.data == "lang_en")
async def langue_en(callback: CallbackQuery, state: FSMContext):
    await state.update_data(language="en")
    update_user_language(callback.from_user.id, "en")
    update_provider_language(callback.from_user.id, "en")
    await _safe_backend_call(sync_user_language_to_backend(callback.from_user.id, "en"))
    await _safe_backend_call(sync_provider_language_to_backend(callback.from_user.id, "en"))
    await callback.message.edit_text(
        f"🇬🇧 You chose <b>English</b>.\n\n{get_message('choose_profile', 'en')}",
        parse_mode="HTML",
        reply_markup=clavier_profil("en"),
    )
    await callback.answer()


@router.callback_query(F.data == "profil_client")
async def profil_client(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user = get_user_by_telegram_id(callback.from_user.id)
    lang = data.get("language") or (user["language"] if user else "fr")
    if user is None:
        await state.set_state(ClientRegistration.phone)
        await state.update_data(language=lang)
        await callback.message.answer(
            get_message("ask_client_phone", lang),
            reply_markup=clavier_contact(lang),
        )
        await callback.answer()
        return

    await state.clear()
    prenom = html.escape(callback.from_user.first_name or "Client")
    await callback.message.edit_text(
        get_message("client_menu", lang, prenom=prenom),
        parse_mode="HTML",
        reply_markup=clavier_client(lang),
    )
    await callback.answer()


@router.message(ClientRegistration.phone)
async def enregistrer_client(message: Message, state: FSMContext):
    phone_number = message.contact.phone_number if message.contact else (message.text or "").strip()
    lang = await get_state_language(state)
    if not phone_number:
        await message.answer(get_message("phone_required", lang))
        return

    data = await state.get_data()
    await persist_client_registration(
        telegram_id=message.from_user.id,
        first_name=message.from_user.first_name or "",
        phone_number=phone_number,
        language=data.get("language", "fr"),
    )
    await state.clear()
    prenom = html.escape(message.from_user.first_name or "Client")
    lang = data.get("language", "fr")
    await message.answer(
        get_message("client_registered", lang),
        reply_markup=ReplyKeyboardRemove(),
    )
    await message.answer(
        get_message("client_menu", lang, prenom=prenom),
        parse_mode="HTML",
        reply_markup=clavier_client(lang),
    )


@router.callback_query(F.data == "profil_prestataire")
async def profil_prestataire(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    provider = get_provider_by_telegram_id(callback.from_user.id)
    lang = data.get("language") or await get_provider_language(callback.from_user.id)
    if provider is None:
        await state.set_state(ProviderRegistration.phone)
        await state.update_data(language=lang)
        await callback.message.answer(
            get_message("ask_provider_phone", lang),
            reply_markup=clavier_contact(lang),
        )
        await callback.answer()
        return

    backend_profile = await fetch_backend_profile(callback.from_user.id)
    provider_data = (backend_profile or {}).get("provider") if backend_profile else None

    await state.clear()
    prenom = html.escape((provider_data or {}).get("full_name") or provider["full_name"] or callback.from_user.first_name or "Prestataire")
    status = (provider_data or {}).get("status") or provider["status"]
    statut = "🟢 Disponible" if status == "available" else "🔴 Indisponible"
    # `badge`/`average_rating`/`total_missions` : réellement calculés côté backend
    # (backend/app/crud.py._recompute_provider_stats, depuis avis/missions), contrairement
    # au `rating` legacy de db.py, jamais alimenté (V5_MIGRATION_PLAN.md, audit du
    # 2026-08-03). Ce menu affichait un 0 figé quand le backend n'a jamais été consulté ;
    # il affiche maintenant la vraie valeur dès que le backend répond.
    if provider_data:
        badge = provider_data.get("badge") or provider["badge"]
        note = provider_data.get("average_rating", provider["rating"])
        missions = provider_data.get("total_missions", provider["total_missions"])
    else:
        badge = provider["badge"]
        note = provider["rating"]
        missions = provider["total_missions"]
    await callback.message.edit_text(
        get_message(
            "provider_menu",
            lang,
            prenom=prenom,
            badge=badge,
            note=f"{note:.1f}",
            missions=missions,
            statut=statut,
        ),
        parse_mode="HTML",
        reply_markup=clavier_prestataire(lang),
    )
    await callback.answer()


@router.message(ProviderRegistration.phone)
async def enregistrer_tel_prestataire(message: Message, state: FSMContext):
    phone_number = message.contact.phone_number if message.contact else (message.text or "").strip()
    lang = await get_state_language(state)
    if not phone_number:
        await message.answer(get_message("phone_required", lang))
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
        await message.answer("Veuillez envoyer un nom complet valide.")
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
    commune_callback = callback.data.replace("provider_", "", 1)
    commune = next((label for label, data in COMMUNES if data == commune_callback), "Autre commune")
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
    data = await state.get_data()
    lang = data.get("language", "fr")

    provider = create_provider(
        telegram_id=callback.from_user.id,
        phone_number=data["provider_phone"],
        full_name=data["provider_full_name"],
        services=data["provider_services"],
        communes=data["provider_communes"],
        language=lang,
    )
    # Vérification obligatoire (V5_MIGRATION_PLAN.md) : create_provider pose
    # status="available" par défaut — on le fait repasser à "pending_verification"
    # tout de suite après, avant que quiconque puisse voir ce prestataire matchable.
    # find_matching_providers (db.py) ne filtre que sur status='available', donc ce
    # seul champ suffit à le rendre invisible du matching sans toucher la requête.
    provider = update_provider_status(callback.from_user.id, "pending_verification")

    portfolio_file_ids = data.get("provider_portfolio_file_ids", [])
    provider = update_provider_verification_documents(
        callback.from_user.id,
        data["provider_id_document_file_id"],
        data["provider_selfie_file_id"],
        portfolio_file_ids,
    )
    await _safe_backend_call(
        sync_provider_to_backend(
            telegram_id=callback.from_user.id,
            full_name=data["provider_full_name"],
            phone_number=data["provider_phone"],
            services=data["provider_services"],
            communes=data["provider_communes"],
            language=lang,
            id_document_file_id=data["provider_id_document_file_id"],
            selfie_file_id=data["provider_selfie_file_id"],
            portfolio_file_ids=portfolio_file_ids,
        )
    )
    await _safe_backend_call(sync_provider_status_to_backend(callback.from_user.id, "pending_verification"))

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


async def _notifier_admin_nouveau_prestataire(callback: CallbackQuery, provider, id_document_file_id: str, selfie_file_id: str, portfolio_file_ids: list[str]) -> None:
    """Push proactif vers l'admin — nouveau pattern pour le bot synchrone (main.py
    n'en avait aucun), mais déjà éprouvé côté Celery
    (backend/app/tasks.py:send_daily_analytics). Erreurs réseau/Telegram avalées :
    un push raté ne doit jamais faire échouer l'inscription elle-même, l'admin peut
    toujours retrouver le prestataire via la liste `admin_providers`.
    """
    if not ADMIN_TELEGRAM_ID:
        return
    try:
        admin_id = int(ADMIN_TELEGRAM_ID)
        summary = (
            f"🆕 <b>Nouveau prestataire en attente de validation</b>\n\n"
            f"Nom : <b>{html.escape(provider['full_name'])}</b>\n"
            f"Téléphone : <b>{html.escape(provider['phone_number'] or '')}</b>\n"
            f"Services : {html.escape(', '.join(json.loads(provider['services'] or '[]')))}\n"
            f"Communes : {html.escape(', '.join(json.loads(provider['communes'] or '[]')))}"
        )
        await callback.bot.send_message(admin_id, summary, parse_mode="HTML")
        await callback.bot.send_photo(admin_id, id_document_file_id, caption="Pièce d'identité")
        await callback.bot.send_photo(admin_id, selfie_file_id, caption="Selfie")
        for photo_file_id in portfolio_file_ids:
            await callback.bot.send_photo(admin_id, photo_file_id, caption="Portfolio")
        await callback.bot.send_message(
            admin_id,
            "Approuver ce prestataire ?",
            reply_markup=clavier_admin_new_provider(provider["id"]),
        )
    except Exception:
        pass


@router.callback_query(F.data == "prest_dispo")
async def disponibilite_prestataire(callback: CallbackQuery):
    provider = get_provider_by_telegram_id(callback.from_user.id)
    lang = await get_provider_language(callback.from_user.id)
    if provider is None:
        await callback.answer(get_message("provider_profile_required", lang), show_alert=True)
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


@router.callback_query(F.data.in_(["provider_status_available", "provider_status_offline"]))
async def changer_disponibilite(callback: CallbackQuery):
    status = "available" if callback.data == "provider_status_available" else "offline"
    update_provider_status(callback.from_user.id, status)
    await _safe_backend_call(sync_provider_status_to_backend(callback.from_user.id, status))
    if status == "available":
        reset_consecutive_ignored(callback.from_user.id)
        await _safe_backend_call(sync_provider_ignored_reset_to_backend(callback.from_user.id))
    provider_lang = await get_provider_language(callback.from_user.id)
    status_label = get_message(
        "provider_status_available" if status == "available" else "provider_status_offline",
        provider_lang,
    )
    await callback.message.edit_text(
        get_message("provider_availability_updated", provider_lang, status=status_label),
        parse_mode="HTML",
        reply_markup=clavier_disponibilite(status, provider_lang),
    )
    await callback.answer(get_message("toast_status_updated", provider_lang))


@router.callback_query(F.data == "prest_edit_services")
async def modifier_services_prestataire(callback: CallbackQuery, state: FSMContext):
    provider = get_provider_by_telegram_id(callback.from_user.id)
    lang = await get_provider_language(callback.from_user.id)
    if provider is None:
        await callback.answer(get_message("provider_profile_required", lang), show_alert=True)
        return

    # Backend-first (comme afficher_profil_prestataire) : la liste de services
    # affichée pour édition doit refléter le dernier état connu, backend ou local.
    backend_profile = await fetch_backend_profile(callback.from_user.id)
    provider_data = (backend_profile or {}).get("provider") if backend_profile else None
    if provider_data and provider_data.get("services") is not None:
        selected_services = provider_data["services"]
    else:
        try:
            selected_services = json.loads(provider["services"] or "[]")
        except json.JSONDecodeError:
            selected_services = []

    await state.set_state(ProviderServicesEdit.services)
    await state.update_data(provider_services_edit=selected_services)
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
    lang = await get_provider_language(callback.from_user.id)
    await callback.message.edit_reply_markup(reply_markup=clavier_modifier_services(selected, lang))
    await callback.answer()


@router.callback_query(ProviderServicesEdit.services, F.data == "edit_services_done")
async def enregistrer_services_modifies(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected = data.get("provider_services_edit", [])
    provider_lang = await get_provider_language(callback.from_user.id)
    if not selected:
        await callback.answer(get_message("provider_select_service", provider_lang), show_alert=True)
        return

    update_provider_services(callback.from_user.id, selected)
    await _safe_backend_call(sync_provider_services_to_backend(callback.from_user.id, selected))
    await state.clear()
    service_labels = [SERVICES.get(service, service) for service in selected]
    await callback.message.edit_text(
        get_message("provider_services_updated", provider_lang)
        + "\n\n"
        + "\n".join(f"• {label}" for label in service_labels),
        parse_mode="HTML",
        reply_markup=clavier_prestataire(provider_lang),
    )
    await callback.answer(get_message("toast_services_saved", provider_lang))


@router.callback_query(F.data == "client_profil")
async def afficher_profil_client(callback: CallbackQuery):
    user = get_user_by_telegram_id(callback.from_user.id)
    profile_data = await load_profile_from_backend(callback.from_user.id, fallback_user=user)

    if user is None and not profile_data.get("client"):
        await callback.answer("Client introuvable.", show_alert=True)
        return

    client_profile = profile_data.get("client") or {}
    display_name = client_profile.get("first_name") or (user["first_name"] if user else "Client")
    display_phone = client_profile.get("phone_number") or (user["phone_number"] if user else "Non renseigné")
    total_missions = len(profile_data.get("client_missions", [])) if profile_data else (user["total_missions"] if user else 0)

    lang = await get_user_language(callback.from_user.id)
    lang_labels = {"fr": "Français", "ln": "Lingala", "en": "English"}
    lang_label = lang_labels.get(client_profile.get("language") or (user["language"] if user else "fr"), "Français")

    await callback.message.edit_text(
        get_message(
            "profile_title",
            lang,
            name=html.escape(display_name or "Client"),
            phone=html.escape(display_phone or "Non renseigné"),
            lang_label=lang_label,
            missions=total_missions,
        ),
        parse_mode="HTML",
        reply_markup=clavier_client(lang),
    )
    await callback.answer()


@router.callback_query(F.data == "prest_profil")
async def afficher_profil_prestataire(callback: CallbackQuery):
    provider = get_provider_by_telegram_id(callback.from_user.id)
    backend_profile = await fetch_backend_profile(callback.from_user.id)
    provider_data = (backend_profile or {}).get("provider") if backend_profile else None
    lang = await get_provider_language(callback.from_user.id)

    if provider is None and not provider_data:
        await callback.answer(get_message("provider_not_found", lang), show_alert=True)
        return

    display_name = provider_data.get("full_name") if provider_data else provider.get("full_name") if provider else get_message("provider_default_name", lang)
    display_phone = provider_data.get("phone_number") if provider_data else provider.get("phone_number") if provider else get_message("not_provided", lang)
    display_status = provider_data.get("status") if provider_data else provider.get("status") if provider else "available"
    display_services = ", ".join(provider_data.get("services", [])) if provider_data else ""
    status_labels = {
        "available": get_message("provider_status_available", lang),
        "offline": get_message("provider_status_offline", lang),
        "paused": get_message("provider_status_paused", lang),
    }
    status_label = status_labels.get(display_status, display_status)

    text = get_message(
        "provider_profile_title",
        lang,
        name=html.escape(display_name or get_message("provider_default_name", lang)),
        phone=html.escape(display_phone or get_message("not_provided", lang)),
        status=html.escape(status_label),
    )
    if display_services:
        text += "\n" + get_message("provider_profile_services", lang, services=html.escape(display_services))

    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=clavier_prestataire(lang),
    )
    await callback.answer()


@router.callback_query(F.data == "client_parametres")
async def afficher_parametres_client(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    lang = await get_user_language(callback.from_user.id)
    await callback.message.edit_text(
        get_message("settings_title", lang),
        parse_mode="HTML",
        reply_markup=clavier_parametres_client(lang),
    )
    await callback.answer()


@router.callback_query(F.data == "client_menu_from_settings")
async def retour_menu_client(callback: CallbackQuery):
    lang = await get_user_language(callback.from_user.id)
    prenom = html.escape(callback.from_user.first_name or "Client")
    await callback.message.edit_text(
        get_message("client_menu", lang, prenom=prenom),
        parse_mode="HTML",
        reply_markup=clavier_client(lang),
    )
    await callback.answer()


@router.callback_query(F.data == "client_settings_language")
async def demander_nouvelle_langue(callback: CallbackQuery):
    lang = await get_user_language(callback.from_user.id)
    await callback.message.edit_text(
        get_message("settings_language_prompt", lang),
        parse_mode="HTML",
        reply_markup=clavier_langue_parametres(lang),
    )
    await callback.answer()


async def _appliquer_nouvelle_langue(callback: CallbackQuery, new_lang: str):
    update_user_language(callback.from_user.id, new_lang)
    await _safe_backend_call(sync_user_language_to_backend(callback.from_user.id, new_lang))
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
    lang = await get_user_language(callback.from_user.id)
    await state.set_state(ClientSettings.name)
    await callback.message.edit_text(
        get_message("settings_name_prompt", lang),
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(ClientSettings.name)
async def nouveau_nom_recu(message: Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id)
    new_name = (message.text or "").strip()
    if not new_name:
        await message.answer(get_message("settings_name_prompt", lang), parse_mode="HTML")
        return

    await state.clear()
    update_user_name(message.from_user.id, new_name)
    await _safe_backend_call(sync_user_name_to_backend(message.from_user.id, new_name))
    await message.answer(
        get_message("settings_name_updated", lang, name=html.escape(new_name)),
        parse_mode="HTML",
        reply_markup=clavier_client(lang),
    )
