"""Acceptation des conditions dans le bot Telegram (CONCEPTION_ACCEPTATIONS.md).

Un filtre passe devant chaque message et chaque bouton : s'il manque à la
personne l'acceptation d'une version en vigueur, l'action demandée n'est pas
exécutée et l'écran d'acceptation s'affiche. Le backend décide seul de ce qui
manque ; injoignable, il bloque (on ne peut pas savoir si une acceptation
manque).

Tant qu'aucune version n'est publiée, le backend ne demande rien et le filtre
laisse tout passer.
"""

import time

from aiogram import BaseMiddleware, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from db import get_provider_by_telegram_id
from messages import get_message
from telegram_bot import backend_client
from telegram_bot.admin import is_admin
from telegram_bot.backend_client import BackendUnavailable, LegalRefused, get_user_language
from telegram_bot.keyboards import clavier_profil

router = Router()

CLIENT = "client"
PROVIDER = "provider"
ACCEPTED = "accepted"
REFUSED = "refused"

# Codes courts dans les boutons (callback_data limité à 64 octets).
DOCUMENT_CODES = {
    "conditions_generales": "cg",
    "donnees_transferts": "dt",
    "conditions_prestataires": "cp",
}
DOCUMENT_KEYS = {code: key for key, code in DOCUMENT_CODES.items()}
CALLBACK_PREFIX = "legal:"

# « Rien ne manque » est gardé 10 minutes par personne et par rôle : une
# nouvelle version est exigée au plus tard 10 minutes après son entrée en
# vigueur, sans interroger le backend à chaque bouton.
COMPLETE_CACHE_SECONDS = 600
_complete_until: dict[tuple[int, str], float] = {}


def forget(telegram_id: int) -> None:
    for role in (CLIENT, PROVIDER):
        _complete_until.pop((telegram_id, role), None)


def _is_complete_cached(telegram_id: int, role: str) -> bool:
    return _complete_until.get((telegram_id, role), 0.0) > time.monotonic()


def _remember_complete(telegram_id: int, role: str) -> None:
    _complete_until[(telegram_id, role)] = time.monotonic() + COMPLETE_CACHE_SECONDS


def _is_exempt(event) -> bool:
    """`/start`, le choix de la langue et les boutons d'acceptation passent :
    sans eux, personne ne pourrait arriver jusqu'à l'écran d'acceptation."""
    if isinstance(event, Message):
        return (event.text or "").split(maxsplit=1)[:1] == ["/start"]
    if isinstance(event, CallbackQuery):
        data = event.data or ""
        return data.startswith(("lang_", CALLBACK_PREFIX))
    return False


def _role_for(event, telegram_id: int) -> str:
    if isinstance(event, CallbackQuery) and event.data == "profil_prestataire":
        return PROVIDER
    return PROVIDER if get_provider_by_telegram_id(telegram_id) is not None else CLIENT


async def _language(state: FSMContext | None, telegram_id: int) -> str:
    if state is not None:
        language = (await state.get_data()).get("language")
        if language:
            return language
    return await get_user_language(telegram_id)


def _document_keyboard(document: dict, lang: str) -> InlineKeyboardMarkup:
    code = DOCUMENT_CODES[document["document_key"]]
    version = document["version"]
    builder = InlineKeyboardBuilder()
    builder.button(text=get_message("legal_button_read", lang), url=document["url"])
    builder.button(text=get_message("legal_button_accept", lang), callback_data=f"{CALLBACK_PREFIX}a:{code}:{version}")
    builder.button(text=get_message("legal_button_refuse", lang), callback_data=f"{CALLBACK_PREFIX}r:{code}:{version}")
    builder.adjust(1)
    return builder.as_markup()


def _document_text(document_key: str, lang: str) -> str:
    return get_message(f"legal_prompt_{document_key}", lang)


async def _reply(event, text: str, reply_markup=None) -> None:
    message = event.message if isinstance(event, CallbackQuery) else event
    await message.answer(text, parse_mode="HTML", reply_markup=reply_markup)
    if isinstance(event, CallbackQuery):
        await event.answer()


async def _show_document(event, document: dict, lang: str) -> None:
    await _reply(event, _document_text(document["document_key"], lang), _document_keyboard(document, lang))


class LegalGateMiddleware(BaseMiddleware):
    """À enregistrer en `outer_middleware` sur les messages et les boutons."""

    async def __call__(self, handler, event, data):
        user = data.get("event_from_user")
        if user is None or _is_exempt(event) or is_admin(user.id):
            return await handler(event, data)
        role = _role_for(event, user.id)
        if _is_complete_cached(user.id, role):
            return await handler(event, data)

        state: FSMContext | None = data.get("state")
        lang = await _language(state, user.id)
        try:
            status = await backend_client.fetch_legal_status(user.id, role)
        except BackendUnavailable:
            await _reply(event, get_message("legal_backend_unavailable", lang))
            return None
        if status["complete"]:
            _remember_complete(user.id, role)
            return await handler(event, data)
        if state is not None:
            # Le bouton « J'accepte » doit savoir quels documents enchaîner :
            # un futur prestataire n'est pas encore inscrit dans db.py.
            await state.update_data(legal_role=role)
        await _show_document(event, status["missing"][0], lang)
        return None


def _parse(callback_data: str) -> tuple[str, str, str] | None:
    parts = callback_data[len(CALLBACK_PREFIX):].split(":", 2)
    if len(parts) != 3 or parts[0] not in ("a", "r") or parts[1] not in DOCUMENT_KEYS or not parts[2]:
        return None
    return (ACCEPTED if parts[0] == "a" else REFUSED), DOCUMENT_KEYS[parts[1]], parts[2]


@router.callback_query(F.data.startswith(CALLBACK_PREFIX))
async def legal_decision(callback: CallbackQuery, state: FSMContext):
    parsed = _parse(callback.data or "")
    telegram_id = callback.from_user.id
    lang = await _language(state, telegram_id)
    if parsed is None:
        await callback.answer()
        return
    decision, document_key, version = parsed
    data = await state.get_data()
    role = data.get("legal_role") or _role_for(callback, telegram_id)
    if document_key == "conditions_prestataires":
        role = PROVIDER

    try:
        await backend_client.record_legal_decision(telegram_id, document_key, version, decision, lang)
    except BackendUnavailable:
        await callback.answer(get_message("legal_backend_unavailable", lang), show_alert=True)
        return
    except LegalRefused as error:
        if error.code != "terms_version_outdated":
            await callback.answer(get_message("legal_backend_unavailable", lang), show_alert=True)
            return
        # Une nouvelle version est entrée en vigueur pendant la lecture : on
        # montre celle-ci, c'est elle qu'il faut accepter.
        await _show_next(callback, telegram_id, role, lang, get_message("legal_version_changed", lang))
        return
    forget(telegram_id)

    if decision == REFUSED:
        await _reply(callback, get_message("legal_refused", lang))
        return
    await _show_next(callback, telegram_id, role, lang)


async def _show_next(callback: CallbackQuery, telegram_id: int, role: str, lang: str, notice: str | None = None) -> None:
    try:
        status = await backend_client.fetch_legal_status(telegram_id, role)
    except BackendUnavailable:
        await _reply(callback, get_message("legal_backend_unavailable", lang))
        return
    if status["missing"]:
        if notice:
            await callback.message.answer(notice, parse_mode="HTML")
        await _show_document(callback, status["missing"][0], lang)
        return
    _remember_complete(telegram_id, role)
    await _reply(callback, get_message("legal_all_accepted", lang), clavier_profil(lang))
