import asyncio
import os

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, Message, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv
from aiogram.exceptions import TelegramBadRequest

from messages import get_message
from db import init_db
# Phase 3 (voir V5_MIGRATION_PLAN.md) : tous les flows métier vivent
# maintenant dans telegram_bot/ (modules séparés, même process — pas encore
# des services à part, voir dp.include_router ci-dessous). Il ne reste dans
# main.py que le bootstrap (démarrage, /start, /app) et le code partagé entre
# ces modules (aucun pour l'instant).
from telegram_bot import admin
from telegram_bot import dashboard
from telegram_bot import mission as mission_flow
from telegram_bot import payment
from telegram_bot import registration
from telegram_bot.backend_client import get_user_language
from telegram_bot.keyboards import MINI_APP_URL, button_label, clavier_langue
from telegram_bot.webhook_server import run_webhook


load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN manquant dans le fichier .env")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
# Flows extraits (Phase 3) : routers séparés plutôt que des handlers directement
# sur `dp`. Voir telegram_bot/registration.py et telegram_bot/mission.py.
dp.include_router(registration.router)
dp.include_router(mission_flow.router)
dp.include_router(payment.router)
dp.include_router(admin.router)
dp.include_router(dashboard.router)


_original_edit_text = Message.edit_text


async def _safe_edit_text(self, text, *args, **kwargs):
    try:
        return await _original_edit_text(self, text, *args, **kwargs)
    except TelegramBadRequest as exc:
        if "message is not modified" in str(exc).lower():
            return None
        raise


Message.edit_text = _safe_edit_text


def clavier_mini_app(lang: str = "fr"):
    builder = InlineKeyboardBuilder()
    if MINI_APP_URL:
        builder.button(text=button_label("open_mini_app", lang), web_app=WebAppInfo(url=MINI_APP_URL))
    builder.adjust(1)
    return builder.as_markup()


@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        get_message("welcome", "fr"),
        parse_mode="HTML",
        reply_markup=clavier_langue(),
    )


@dp.message(Command("app"))
async def cmd_app(message: Message):
    lang = await get_user_language(message.from_user.id)
    if not MINI_APP_URL:
        await message.answer(
            "La Mini App est prête côté code, mais il manque encore MINI_APP_URL dans le fichier .env."
        )
        return
    await message.answer(
        "Ouvre Nexis Hub ici :",
        reply_markup=clavier_mini_app(lang),
    )


@dp.callback_query(
    F.data.in_(
        [
            "prest_dashboard",
            "prest_support",
        ]
    )
)
async def fonctionnalite_a_venir(callback: CallbackQuery):
    await callback.answer("Module prévu dans la suite du développement.", show_alert=True)


async def main():
    init_db()
    mode = os.getenv("BOT_RUN_MODE", "polling").strip().lower()
    if mode == "webhook":
        await run_webhook(bot, dp)
    else:
        # Defensive : si un webhook était enregistré lors d'une session
        # précédente (switch webhook -> polling), getUpdates échoue avec
        # TelegramConflictError tant que le webhook est actif.
        await bot.delete_webhook(drop_pending_updates=False)
        print("✅ NEXIS HUB Bot démarré (polling).")
        await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
