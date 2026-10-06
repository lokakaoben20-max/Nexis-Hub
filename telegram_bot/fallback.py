"""Réponse aux messages et boutons qu'aucun handler ne prend.

Avant, aiogram les ignorait en silence : un utilisateur qui tape du texte là où
le bot attend un bouton, ou qui appuie sur le bouton d'un ancien message, ne
recevait rien et croyait le bot en panne (constaté en test réel le 2026-10-06).

Ce router doit être inclus en DERNIER dans `main.py` : aiogram essaie les
routers dans l'ordre d'inclusion, ceux-ci ne reçoivent donc que ce qui n'a
trouvé preneur nulle part ailleurs.
"""

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.types import CallbackQuery, Message

from db import get_user_by_telegram_id
from messages import get_message
from telegram_bot.backend_client import get_provider_language, get_user_language

router = Router()


async def _language_of(telegram_id: int) -> str:
    """Langue client si la personne est inscrite comme client, sinon langue
    prestataire (qui retombe elle-même sur "fr" pour un inconnu)."""
    if get_user_by_telegram_id(telegram_id) is not None:
        return await get_user_language(telegram_id)
    return await get_provider_language(telegram_id)


# Conversations privées seulement : dans un groupe, répondre à chaque message
# qui ne s'adresse pas au bot serait du bruit.
@router.message(F.chat.type == ChatType.PRIVATE)
async def message_inattendu(message: Message):
    lang = await _language_of(message.from_user.id)
    await message.answer(get_message("unexpected_message", lang))


@router.callback_query()
async def bouton_inactif(callback: CallbackQuery):
    lang = await _language_of(callback.from_user.id)
    await callback.answer(get_message("inactive_button", lang), show_alert=True)
