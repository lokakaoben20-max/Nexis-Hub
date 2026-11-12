"""Enregistre l'adresse du webhook chez Telegram. Lancé une fois par
déploiement (et sur le PC quand l'adresse du tunnel change), jamais par le
serveur lui-même (voir `webhook_server.py`).

    python -m telegram_bot.webhook_setup

Les updates arrivées pendant une coupure sont conservées
(`drop_pending_updates=False`). Sans effet si l'adresse et le secret sont
déjà les bons : Telegram traite l'appel comme idempotent.
"""

import asyncio
import os

from aiogram import Bot
from dotenv import load_dotenv

import nexis_config
import nexis_logs
from telegram_bot import webhook_server


async def register(bot: Bot) -> str:
    url = webhook_server.expected_webhook_url()
    secret = webhook_server._require_secret()
    await bot.set_webhook(url=url, secret_token=secret, drop_pending_updates=False)
    info = await bot.get_webhook_info()
    if info.url != url:
        raise RuntimeError(f"Telegram a répondu avec une autre adresse : {info.url!r}")
    return url


async def _main() -> None:
    load_dotenv()
    nexis_config.verifier("bot")
    nexis_logs.configurer("bot")
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN manquant")
    bot = Bot(token=token)
    try:
        url = await register(bot)
        info = await bot.get_webhook_info()
        print(f"Webhook enregistré : {url} ({info.pending_update_count} update(s) en attente conservée(s)).")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(_main())
