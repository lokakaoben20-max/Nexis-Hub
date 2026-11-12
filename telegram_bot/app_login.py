"""Connexion à l'application mobile Nexis par Telegram (étape 1, PR 2).

Plan : app-mobile/plan-etape1-connexion-api-2026-11-07.md, section 5.2.

L'app ouvre `t.me/<bot>?start=app_<jeton>`. Le bot demande « Partager mon
numéro », vérifie que le contact est bien celui de l'expéditeur
(`registration._numero_partage`), puis le backend :
- vérifie le jeton (usage unique, 10 minutes) et que le numéro est celui tapé
  dans l'app ;
- prouve ce numéro sur le compte Nexis de ce Telegram (créé s'il n'existe pas) ;
- rend le code que le bot affiche ici.

Toutes les règles sont dans le backend (`backend/app/app_auth.py`) : le bot ne
décide de rien et ne garde rien, sauf le jeton le temps de l'étape.
"""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from messages import get_message
from telegram_bot import backend_client
from telegram_bot.keyboards import clavier_contact
from telegram_bot.registration import _numero_partage

START_PREFIX = "app_"
NOT_ME_PREFIX = "app_not_me_"

router = Router()

# Refus du backend -> message montré à la personne. Tout autre refus, ou un
# backend injoignable : « momentanément indisponible », et aucun code.
_REFUSALS = {
    "link_invalid": "app_login_link_invalid",
    "phone_mismatch": "app_login_phone_mismatch",
    "invalid_phone": "app_login_phone_mismatch",
    "phone_conflict": "app_login_phone_conflict",
}


class AppLogin(StatesGroup):
    contact = State()


def is_app_login_start(args: str | None) -> bool:
    return bool(args) and args.startswith(START_PREFIX)


async def start_app_login(message: Message, state: FSMContext, args: str) -> None:
    """Appelé par /start quand le paramètre vient de l'application."""
    lang = await backend_client.get_user_language(message.from_user.id)
    await state.clear()
    await state.set_state(AppLogin.contact)
    await state.update_data(app_login_token=args[len(START_PREFIX):], language=lang)
    await message.answer(get_message("app_login_share_phone", lang), reply_markup=clavier_contact(lang))


@router.message(AppLogin.contact)
async def contact_pour_app(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = data.get("language", "fr")
    phone_number = await _numero_partage(message, lang)
    if phone_number is None:
        return
    await state.clear()
    try:
        body = await backend_client.app_login_telegram_contact(
            message.from_user.id, data.get("app_login_token", ""), phone_number
        )
    except backend_client.MoneyRefused as refusal:
        key = _REFUSALS.get(refusal.code, "app_login_unavailable")
        await message.answer(get_message(key, lang), reply_markup=ReplyKeyboardRemove())
        return
    except backend_client.BackendUnavailable:
        await message.answer(get_message("app_login_unavailable", lang), reply_markup=ReplyKeyboardRemove())
        return
    await message.answer(
        get_message("app_login_code", lang, code=body["code"]),
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.callback_query(F.data.startswith(NOT_ME_PREFIX))
async def pas_moi(callback: CallbackQuery) -> None:
    """Bouton « Ce n'est pas moi » sous l'alerte « Nouvel appareil » (envoyée
    par le backend). Le backend coupe le téléphone s'il est bien sur le compte
    de cette personne."""
    lang = await backend_client.get_user_language(callback.from_user.id)
    raw_id = callback.data[len(NOT_ME_PREFIX):]
    if not raw_id.isdigit():
        await callback.answer()
        return
    try:
        await backend_client.app_device_not_me(callback.from_user.id, int(raw_id))
    except backend_client.MoneyRefused:
        await callback.message.answer(get_message("app_not_me_unknown", lang))
        await callback.answer()
        return
    except backend_client.BackendUnavailable:
        # Rien n'est coupé : le bouton reste, la personne peut réessayer.
        await callback.message.answer(get_message("app_not_me_retry", lang))
        await callback.answer()
        return
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(get_message("app_not_me_done", lang))
    await callback.answer()
