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

from messages import get_message
from telegram_bot.backend_client import get_language

router = Router()


# Conversations privées seulement : dans un groupe, répondre à chaque message
# qui ne s'adresse pas au bot serait du bruit.
@router.message(F.chat.type == ChatType.PRIVATE)
async def message_inattendu(message: Message):
    lang = await get_language(message.from_user)
    await message.answer(get_message("unexpected_message", lang))


@router.callback_query()
async def bouton_inactif(callback: CallbackQuery):
    lang = await get_language(callback.from_user)
    await callback.answer(get_message("inactive_button", lang), show_alert=True)
