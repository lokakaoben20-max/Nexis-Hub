"""Serveur webhook Telegram (mode dual, voir `main.py`).

Alternative à `dp.start_polling(bot)` : un serveur `aiohttp` reçoit les
updates poussées par Telegram sur `WEBHOOK_URL` au lieu de les demander en
boucle via `getUpdates`. Nécessaire pour lever la contrainte long-polling
(un seul process peut consommer `getUpdates` avec un token donné à la fois)
qui bloque tout découplage de `telegram_bot/` en process séparé — voir
`V5_MIGRATION_PLAN.md`, section "Phase 3 — Découplage du bot Telegram en
service séparé".

`bot`/`dp` sont reçus en paramètres, jamais importés depuis `main` : un
`from main import ...` recrée un second `Bot`/`Dispatcher` (voir la note
dans `telegram_bot/mission.py`).

Nécessite une URL HTTPS publique — un tunnel local (ngrok, Cloudflare
Tunnel) en attendant un vrai hébergement de production (aucun n'existe
encore, voir AGENTS.md). Le mode par défaut du bot reste le polling
classique (`main.py`, `BOT_RUN_MODE=polling`) ; ce module n'est utilisé que
si `BOT_RUN_MODE=webhook`.
"""

import asyncio
import os

from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from dotenv import load_dotenv

load_dotenv()

WEBHOOK_URL = os.getenv("WEBHOOK_URL")
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/webhook")
WEBHOOK_SECRET_TOKEN = os.getenv("WEBHOOK_SECRET_TOKEN")
WEBHOOK_LISTEN_HOST = os.getenv("WEBHOOK_LISTEN_HOST", "127.0.0.1")
WEBHOOK_LISTEN_PORT = int(os.getenv("WEBHOOK_LISTEN_PORT", "8002"))


def build_webhook_app(bot: Bot, dp: Dispatcher) -> web.Application:
    # Gardée ici (pas seulement dans run_webhook) : si un futur appelant
    # construit l'app directement sans passer par run_webhook, un secret
    # vide ferait retomber aiogram sur `verify_secret(...) -> True`
    # inconditionnellement — un webhook grand ouvert, sans erreur ni
    # avertissement (trouvaille security-reviewer).
    if not WEBHOOK_SECRET_TOKEN:
        raise RuntimeError(
            "WEBHOOK_SECRET_TOKEN manquant — sans lui n'importe qui connaissant "
            "l'URL du webhook peut injecter de faux updates. Génère-en un : "
            'python -c "import secrets; print(secrets.token_hex(32))"'
        )

    app = web.Application()
    SimpleRequestHandler(dispatcher=dp, bot=bot, secret_token=WEBHOOK_SECRET_TOKEN).register(
        app, path=WEBHOOK_PATH
    )
    setup_application(app, dp, bot=bot)

    async def health(request: web.Request) -> web.Response:
        return web.json_response({"status": "ok"})

    app.router.add_get("/health", health)
    return app


async def run_webhook(bot: Bot, dp: Dispatcher) -> None:
    if not WEBHOOK_URL:
        raise RuntimeError(
            "BOT_RUN_MODE=webhook mais WEBHOOK_URL manquant dans .env "
            "(URL publique du tunnel, sans le chemin)."
        )

    app = build_webhook_app(bot, dp)  # lève RuntimeError si WEBHOOK_SECRET_TOKEN manquant

    full_url = WEBHOOK_URL.rstrip("/") + WEBHOOK_PATH
    # Appelé à chaque démarrage sans vérifier si un webhook est déjà
    # enregistré : idempotent côté Telegram, et ça réenregistre de facto une
    # nouvelle URL de tunnel (ngrok en change à chaque relance) sans geste
    # supplémentaire.
    await bot.set_webhook(url=full_url, secret_token=WEBHOOK_SECRET_TOKEN, drop_pending_updates=True)
    print(f"✅ NEXIS HUB Bot démarré (webhook -> {full_url}).")

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, WEBHOOK_LISTEN_HOST, WEBHOOK_LISTEN_PORT)
    await site.start()
    print(f"   Serveur local à l'écoute sur http://{WEBHOOK_LISTEN_HOST}:{WEBHOOK_LISTEN_PORT}{WEBHOOK_PATH}")

    try:
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()
