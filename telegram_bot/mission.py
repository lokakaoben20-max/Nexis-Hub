"""Flow mission / devis (Phase 3, second flow extrait — voir V5_MIGRATION_PLAN.md).

Couvre la création d'une demande par le client (choix du service jusqu'à la
confirmation et la diffusion aux prestataires matchés) et la réponse du prestataire
(acceptation, saisie du devis, envoi au client, ou passage). **S'arrête à l'envoi du
devis** : acceptation du devis, paiement, lifecycle et notation restent dans `main.py`
— la partie argent mérite son propre commit, séparé de celui-ci.

Même contrat que `telegram_bot/registration.py` : Router aiogram dédié, double
écriture backend + `db.py` maintenue, lecture backend-first.

`bot` n'est pas importé depuis `main.py` (ça réexécuterait tout le module) : aiogram 3
expose l'instance sur chaque événement via `message.bot` / `callback.bot`, ce qui est
aussi le pattern correct pour un handler vivant dans un router séparé.
"""

import html
import json

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from db import (
    create_mission,
    create_quote,
    find_matching_providers,
    get_mission_by_id,
    get_provider_by_telegram_id,
    reset_consecutive_ignored,
    update_consecutive_ignored,
)
from messages import get_message
from telegram_bot.backend_client import (
    _safe_backend_call,
    fetch_backend_profile,
    get_provider_language,
    get_state_language,
    get_user_language,
    persist_mission_creation,
    sync_provider_ignored_increment_to_backend,
    sync_provider_ignored_reset_to_backend,
    sync_quote_to_backend,
)
from telegram_bot.keyboards import (
    COMMUNES,
    CURRENCIES,
    CURRENCY_CALLBACKS,
    SERVICE_CALLBACKS,
    SERVICES,
    clavier_alerte_mission,
    clavier_client,
    clavier_communes,
    clavier_devis_client,
    clavier_devises,
    clavier_devises_devis,
    clavier_disponibilite,
    clavier_fin_explication,
    clavier_prestataire,
    clavier_recapitulatif,
    clavier_services,
    clavier_urgence,
)

router = Router()


class MissionRequest(StatesGroup):
    description = State()


class QuoteCreation(StatesGroup):
    amount = State()
    currency = State()
    delay = State()
    message = State()


BADGE_LABELS = {
    "partner": "🏆 Partenaire",
    "expert": "🥇 Expert",
    "premium": "⭐ Premium",
    "verified": "✅ Vérifié",
}

# Oui/Non par langue — utilisé dans le récapitulatif client et dans l'alerte
# envoyée au prestataire, qui doivent parler la même langue que leur destinataire.
YES_NO_LABELS = {"fr": ("Oui", "Non"), "ln": ("Iyo", "Te"), "en": ("Yes", "No")}


def yes_no_label(lang: str, value: bool) -> str:
    yes_label, no_label = YES_NO_LABELS.get(lang, YES_NO_LABELS["fr"])
    return yes_label if value else no_label


def media_list(data: dict, key: str) -> list[str]:
    value = data.get(key)
    if not value:
        return []
    if isinstance(value, list):
        return value
    try:
        loaded = json.loads(value)
        return loaded if isinstance(loaded, list) else [value]
    except (TypeError, json.JSONDecodeError):
        return [value]


def format_recap(data: dict) -> str:
    lang = data.get("language", "fr")
    service = SERVICES.get(data.get("service"), "Service")
    urgence = yes_no_label(lang, bool(data.get("urgent")))
    commune = data.get("commune", "Non précisée")
    currency = data.get("currency", "USD")
    description = html.escape(data.get("description", ""))
    photo_count = len(media_list(data, "photo_file_ids") or media_list(data, "photo_file_id"))
    voice_count = len(media_list(data, "voice_file_ids") or media_list(data, "voice_file_id"))
    photo = str(photo_count)
    voice = str(voice_count)

    base_summary = get_message(
        "mission_summary",
        lang,
        service=service,
        urgent=urgence,
        commune=commune,
        currency=currency,
        description=description,
    )
    if lang == "en":
        return base_summary.replace(
            f"Currency: <b>{currency}</b>\n",
            f"Currency: <b>{currency}</b>\nPhoto: <b>{photo}</b>\nVoice note: <b>{voice}</b>\n",
        )
    return base_summary.replace(
        f"Devise : <b>{currency}</b>\n",
        f"Devise : <b>{currency}</b>\nPhoto : <b>{photo}</b>\nNote vocale : <b>{voice}</b>\n",
    )


def provider_trust_line(provider) -> str:
    if not provider["total_missions"]:
        return "🆕 Nouveau prestataire sur Nexis Hub"

    line = f"⭐ {provider['rating']:.1f}/5 ({provider['total_missions']} missions, {provider['success_rate']:.0f}% de réussite)"
    badge_label = BADGE_LABELS.get(provider["badge"])
    if badge_label:
        line += f" · {badge_label}"
    if provider["is_verified"]:
        line += " · ✅ Vérifié"
    return line


# ── Création de la demande (client) ────────────────────────────────────────


@router.callback_query(F.data == "client_demande")
async def client_demande(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = data.get("language") or await get_user_language(callback.from_user.id)
    await state.clear()
    await state.update_data(language=lang)
    await callback.message.edit_text(
        get_message("choose_service", lang),
        parse_mode="HTML",
        reply_markup=clavier_services(lang),
    )
    await callback.answer()


@router.callback_query(F.data.in_(SERVICE_CALLBACKS))
async def service_selectionne(callback: CallbackQuery, state: FSMContext):
    await state.update_data(service=callback.data)
    lang = await get_state_language(state)
    service_choisi = SERVICES.get(callback.data, "Service")
    await callback.message.edit_text(
        get_message("is_urgent", lang, service=service_choisi),
        parse_mode="HTML",
        reply_markup=clavier_urgence(lang),
    )
    await callback.answer()


@router.callback_query(F.data.in_(["urgent_oui", "urgent_non"]))
async def urgence_selectionnee(callback: CallbackQuery, state: FSMContext):
    await state.update_data(urgent=callback.data == "urgent_oui")
    lang = await get_state_language(state)
    await callback.message.edit_text(
        get_message("choose_commune", lang),
        parse_mode="HTML",
        reply_markup=clavier_communes(lang),
    )
    await callback.answer()


@router.callback_query(F.data == "back_communes")
async def retour_communes(callback: CallbackQuery):
    lang = await get_user_language(callback.from_user.id)
    await callback.message.edit_text(
        get_message("choose_commune", lang),
        parse_mode="HTML",
        reply_markup=clavier_communes(lang),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("commune_"))
async def commune_selectionnee(callback: CallbackQuery, state: FSMContext):
    commune = next((label for label, data in COMMUNES if data == callback.data), "Autre commune")
    await state.update_data(commune=commune)
    lang = await get_state_language(state)
    await callback.message.edit_text(
        get_message("choose_currency", lang),
        parse_mode="HTML",
        reply_markup=clavier_devises(lang),
    )
    await callback.answer()


@router.callback_query(F.data.in_(CURRENCY_CALLBACKS))
async def devise_selectionnee(callback: CallbackQuery, state: FSMContext):
    await state.update_data(currency=CURRENCIES[callback.data])
    lang = await get_state_language(state)
    await state.set_state(MissionRequest.description)
    await state.update_data(description_parts=[], photo_file_ids=[], voice_file_ids=[])
    await callback.message.edit_text(
        get_message("describe_problem", lang),
        parse_mode="HTML",
        reply_markup=clavier_fin_explication(lang),
    )
    await callback.answer()


@router.message(MissionRequest.description)
async def description_recue(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("language", "fr")
    description_parts = data.get("description_parts", [])
    photo_file_ids = data.get("photo_file_ids", [])
    voice_file_ids = data.get("voice_file_ids", [])

    if message.voice:
        voice_file_ids.append(message.voice.file_id)
        feedback = get_message("media_voice_added", lang, count=len(voice_file_ids))
    elif message.photo:
        photo_file_ids.append(message.photo[-1].file_id)
        feedback = get_message("media_photo_added", lang, count=len(photo_file_ids))
    elif message.text:
        description_parts.append(message.text.strip())
        feedback = get_message("media_text_added", lang)
    else:
        await message.answer(
            get_message("media_invalid", lang),
            reply_markup=clavier_fin_explication(lang),
        )
        return

    await state.update_data(
        description_parts=description_parts,
        photo_file_ids=photo_file_ids,
        voice_file_ids=voice_file_ids,
        description="\n".join(description_parts) if description_parts else "Explication envoyée en média par le client.",
        photo_file_id=json.dumps(photo_file_ids) if photo_file_ids else None,
        voice_file_id=json.dumps(voice_file_ids) if voice_file_ids else None,
    )
    await message.answer(
        f"{feedback}\n\n{get_message('media_more_or_finish', lang)}",
        reply_markup=clavier_fin_explication(lang),
    )


@router.callback_query(MissionRequest.description, F.data == "mission_media_done")
async def explication_terminee(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    description_parts = data.get("description_parts", [])
    photo_file_ids = data.get("photo_file_ids", [])
    voice_file_ids = data.get("voice_file_ids", [])

    if not description_parts and not photo_file_ids and not voice_file_ids:
        await callback.answer(
            get_message("media_required_alert", data.get("language", "fr")),
            show_alert=True,
        )
        return

    await state.update_data(
        description="\n".join(description_parts) if description_parts else "Explication envoyée en média par le client.",
        photo_file_id=json.dumps(photo_file_ids) if photo_file_ids else None,
        voice_file_id=json.dumps(voice_file_ids) if voice_file_ids else None,
    )
    data = await state.get_data()
    await state.clear()
    await state.update_data(**data)
    await callback.message.edit_text(
        format_recap(data),
        parse_mode="HTML",
        reply_markup=clavier_recapitulatif(data.get("language", "fr")),
    )
    await callback.answer()


@router.callback_query(F.data == "mission_confirmer")
async def mission_confirmer(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    mission_id = create_mission(callback.from_user.id, data)
    await persist_mission_creation(callback.from_user.id, mission_id, data)
    matching_providers = find_matching_providers(data["service"], data["commune"])

    photo_file_ids = media_list(data, "photo_file_ids") or media_list(data, "photo_file_id")
    voice_file_ids = media_list(data, "voice_file_ids") or media_list(data, "voice_file_id")

    for provider in matching_providers[:3]:
        # Chaque prestataire est alerté dans SA langue. L'ancienne version figeait
        # "fr" ici, donc un prestataire lingala ou anglophone recevait l'alerte en
        # français — corrigé en extrayant ce flow (voir le skill textes-utilisateur).
        provider_lang = await get_provider_language(provider["telegram_id"])
        await callback.bot.send_message(
            provider["telegram_id"],
            get_message(
                "new_mission_alert",
                provider_lang,
                mission_id=mission_id,
                service=SERVICES.get(data["service"], data["service"]),
                commune=html.escape(data["commune"]),
                urgent=yes_no_label(provider_lang, bool(data.get("urgent"))),
            )
            + f"\n\n{html.escape(data['description'])}",
            parse_mode="HTML",
            reply_markup=clavier_alerte_mission(mission_id),
        )
        for photo_file_id in photo_file_ids:
            await callback.bot.send_photo(
                provider["telegram_id"],
                photo_file_id,
                caption=get_message("mission_photo_caption", provider_lang, mission_id=mission_id),
            )
        for voice_file_id in voice_file_ids:
            await callback.bot.send_voice(
                provider["telegram_id"],
                voice_file_id,
                caption=get_message("mission_voice_caption", provider_lang, mission_id=mission_id),
            )

    await state.clear()
    client_lang = data.get("language", "fr")
    matching_text = (
        get_message("matching_providers_notified", client_lang, count=len(matching_providers[:3]))
        if matching_providers
        else get_message("matching_no_providers", client_lang)
    )
    await callback.message.edit_text(
        get_message(
            "mission_saved",
            client_lang,
            mission_id=mission_id,
            matching_text=matching_text,
        ),
        parse_mode="HTML",
        reply_markup=clavier_client(client_lang),
    )
    await callback.answer(get_message("toast_request_confirmed", client_lang))


@router.callback_query(F.data == "mission_annuler")
async def mission_annuler(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    lang = await get_user_language(callback.from_user.id)
    await callback.message.edit_text(
        get_message("request_cancelled", lang),
        reply_markup=clavier_client(lang),
    )
    await callback.answer(get_message("toast_request_cancelled", lang))


# ── Réponse du prestataire : devis ─────────────────────────────────────────


@router.callback_query(F.data.startswith("provider_accept_"))
async def accepter_mission_prestataire(callback: CallbackQuery, state: FSMContext):
    mission_id = int(callback.data.replace("provider_accept_", "", 1))
    mission = get_mission_by_id(mission_id)
    provider_lang = await get_provider_language(callback.from_user.id)
    if mission is None:
        await callback.answer(get_message("provider_mission_not_found", provider_lang), show_alert=True)
        return

    await state.clear()
    await state.set_state(QuoteCreation.amount)
    await state.update_data(quote_mission_id=mission_id)
    await callback.message.edit_text(
        get_message("quote_amount_prompt", provider_lang, mission_id=mission_id),
        parse_mode="HTML",
    )
    await callback.answer(get_message("toast_mission_accepted", provider_lang))


@router.message(QuoteCreation.amount)
async def devis_montant_recu(message: Message, state: FSMContext):
    lang = await get_provider_language(message.from_user.id)
    raw_amount = (message.text or "").replace(",", ".").strip()
    try:
        amount = float(raw_amount)
    except ValueError:
        await message.answer(get_message("quote_amount_invalid", lang))
        return

    if amount <= 0:
        await message.answer(get_message("quote_amount_positive", lang))
        return

    await state.update_data(quote_amount=amount)
    await state.set_state(QuoteCreation.currency)
    await message.answer(
        get_message("quote_currency_prompt", lang),
        reply_markup=clavier_devises_devis(),
    )


@router.callback_query(QuoteCreation.currency, F.data.in_(["quote_currency_usd", "quote_currency_cdf"]))
async def devis_devise_recue(callback: CallbackQuery, state: FSMContext):
    lang = await get_provider_language(callback.from_user.id)
    currency = "USD" if callback.data == "quote_currency_usd" else "CDF"
    await state.update_data(quote_currency=currency)
    await state.set_state(QuoteCreation.delay)
    await callback.message.edit_text(
        get_message("quote_delay_prompt", lang),
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(QuoteCreation.delay)
async def devis_delai_recu(message: Message, state: FSMContext):
    lang = await get_provider_language(message.from_user.id)
    raw_delay = (message.text or "").strip()
    if not raw_delay.isdigit():
        await message.answer(get_message("quote_delay_invalid", lang))
        return

    delay_hours = int(raw_delay)
    if delay_hours <= 0:
        await message.answer(get_message("quote_delay_positive", lang))
        return

    await state.update_data(quote_delay_hours=delay_hours)
    await state.set_state(QuoteCreation.message)
    await message.answer(
        get_message("quote_message_prompt", lang),
        parse_mode="HTML",
    )


@router.message(QuoteCreation.message)
async def devis_message_recu(message: Message, state: FSMContext):
    data = await state.get_data()
    provider = get_provider_by_telegram_id(message.from_user.id)
    mission = get_mission_by_id(data["quote_mission_id"])
    provider_lang = await get_provider_language(message.from_user.id)

    if provider is None or mission is None:
        await state.clear()
        await message.answer(get_message("quote_create_failed", provider_lang))
        return

    quote_message = (message.text or "").strip()
    if quote_message == "-":
        quote_message = ""

    quote_id = create_quote(
        mission_id=data["quote_mission_id"],
        provider_telegram_id=message.from_user.id,
        amount=data["quote_amount"],
        currency=data["quote_currency"],
        delay_hours=data["quote_delay_hours"],
        message=quote_message,
    )
    reset_consecutive_ignored(message.from_user.id)
    await _safe_backend_call(sync_provider_ignored_reset_to_backend(message.from_user.id))

    backend_quote = await _safe_backend_call(
        sync_quote_to_backend(
            mission_id=data["quote_mission_id"],
            provider_telegram_id=message.from_user.id,
            amount=data["quote_amount"],
            currency=data["quote_currency"],
            delay_hours=data["quote_delay_hours"],
            message=quote_message,
        )
    )
    backend_quote_id = backend_quote["quote"]["id"] if backend_quote else None

    # Lecture backend-first pour l'affichage (nom + ligne de confiance) :
    # total_missions/success_rate/badge sont réellement recalculés côté
    # backend (crud._recompute_provider_stats), contrairement à db.py où ces
    # colonnes ne sont jamais écrites. `rating` (db.py comme backend) reste
    # toujours à 0 des deux côtés — le champ réellement alimenté est
    # `average_rating`, d'où le mapping explicite ci-dessous. Repli local
    # identique à avant si le backend ne répond pas.
    backend_profile = await fetch_backend_profile(message.from_user.id)
    provider_data = (backend_profile or {}).get("provider") if backend_profile else None
    display_full_name = provider_data.get("full_name") if provider_data else provider["full_name"]
    if provider_data:
        trust_source = {
            "rating": provider_data.get("average_rating", 0) or 0,
            "total_missions": provider_data.get("total_missions", 0) or 0,
            "success_rate": provider_data.get("success_rate", 0) or 0,
            "badge": provider_data.get("badge"),
            "is_verified": provider_data.get("is_verified", False),
        }
    else:
        trust_source = provider

    client_lang = await get_user_language(mission["client_telegram_id"])
    await message.bot.send_message(
        mission["client_telegram_id"],
        get_message(
            "new_quote_received_client",
            client_lang,
            mission_id=data["quote_mission_id"],
            prestataire=html.escape(display_full_name),
            trust_line=provider_trust_line(trust_source),
            amount=data["quote_amount"],
            currency=data["quote_currency"],
            delay=data["quote_delay_hours"],
            message=html.escape(quote_message) if quote_message else get_message("quote_no_message", client_lang),
        ),
        parse_mode="HTML",
        reply_markup=clavier_devis_client(quote_id, backend_quote_id),
    )

    await state.clear()
    await message.answer(
        get_message("quote_sent", provider_lang, reference=f"DV-{quote_id:04d}"),
        parse_mode="HTML",
        reply_markup=clavier_prestataire(provider_lang),
    )


@router.callback_query(F.data.startswith("provider_skip_"))
async def passer_mission_prestataire(callback: CallbackQuery):
    mission_id = callback.data.replace("provider_skip_", "", 1)
    provider_lang = await get_provider_language(callback.from_user.id)
    await callback.message.edit_text(
        get_message("provider_mission_skipped", provider_lang, mission_id=int(mission_id)),
        parse_mode="HTML",
    )

    provider = update_consecutive_ignored(callback.from_user.id)
    await _safe_backend_call(sync_provider_ignored_increment_to_backend(callback.from_user.id))
    if provider is not None and provider["status"] == "paused" and provider["consecutive_ignored"] == 3:
        await callback.bot.send_message(
            callback.from_user.id,
            get_message("provider_paused_message", provider_lang),
            parse_mode="HTML",
            reply_markup=clavier_disponibilite("paused", provider_lang),
        )

    await callback.answer(get_message("toast_mission_skipped", provider_lang))
