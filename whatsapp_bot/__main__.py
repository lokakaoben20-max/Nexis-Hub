"""Lancer le service WhatsApp : `python -m whatsapp_bot`.

En local, avec le faux serveur Meta (`python -m whatsapp_bot.fake_meta`),
voir la procédure en tête de `whatsapp_bot/fake_meta.py`.
"""

from __future__ import annotations

import uvicorn
from dotenv import load_dotenv
from redis.asyncio import Redis

import nexis_logs
from whatsapp_bot import config
from whatsapp_bot.app import Service, build_app
from whatsapp_bot.backend import Backend
from whatsapp_bot.conversation import Conversation, Links
from whatsapp_bot.meta import CloudApi
from whatsapp_bot.store import Store


def create_app():
    settings = config.load()
    service = Service(
        app_secret=settings.app_secret,
        verify_token=settings.verify_token,
        phone_number_id=settings.phone_number_id,
        store=Store(Redis.from_url(settings.redis_url)),
        messenger=CloudApi(settings.graph_url, settings.phone_number_id, settings.access_token),
        conversation=Conversation(
            Backend(settings.backend_url, settings.backend_key),
            Links(telegram_bot=settings.telegram_bot_link, mini_app=settings.mini_app_url, public_site=settings.public_site),
        ),
    )
    return build_app(service), settings


def main() -> None:
    load_dotenv()
    nexis_logs.configurer("whatsapp")
    app, settings = create_app()
    uvicorn.run(
        app,
        host=settings.listen_host,
        port=settings.listen_port,
        proxy_headers=True,
        server_header=False,
        timeout_graceful_shutdown=8,
        log_config=None,
    )


if __name__ == "__main__":
    main()
