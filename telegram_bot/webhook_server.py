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

Nécessite une URL HTTPS publique stable (tunnel Cloudflare sur le PC,
répartiteur de charge en production). Le mode par défaut du bot reste le
polling classique (`main.py`, `BOT_RUN_MODE=polling`) ; ce module n'est
utilisé que si `BOT_RUN_MODE=webhook`.

Aucun message perdu, aucun traité deux fois :

- l'update est traitée **avant** la réponse à Telegram. Une erreur répond
  500 et Telegram la renvoie ; une instance arrêtée au milieu n'a rien
  acquitté. (Le réglage par défaut d'aiogram répond « reçu » puis traite en
  arrière-plan : une instance arrêtée juste après perdait l'update.) ;
- `update_ledger.UpdateLedger` (Redis) écarte les renvois d'une update déjà
  traitée ou en cours, même sur une autre instance ;
- l'adresse du webhook n'est **jamais** enregistrée au démarrage du serveur :
  c'est `python -m telegram_bot.webhook_setup`, lancé une fois au
  déploiement, sans effacer les updates en attente. Plusieurs instances qui
  démarrent ne se disputent plus l'enregistrement, et un redémarrage ne jette
  plus les messages reçus pendant la coupure ;
- à l'arrêt (SIGTERM, déploiement), le serveur cesse d'accepter et laisse
  finir les updates en cours.
"""

import asyncio
import logging
import os
import secrets
import signal

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from dotenv import load_dotenv

from telegram_bot.update_ledger import Claim, UpdateLedger

load_dotenv()

logger = logging.getLogger(__name__)

WEBHOOK_URL = os.getenv("WEBHOOK_URL")
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/webhook")
WEBHOOK_SECRET_TOKEN = os.getenv("WEBHOOK_SECRET_TOKEN")
WEBHOOK_LISTEN_HOST = os.getenv("WEBHOOK_LISTEN_HOST", "127.0.0.1")
WEBHOOK_LISTEN_PORT = int(os.getenv("WEBHOOK_LISTEN_PORT", "8002"))
# Temps laissé aux updates en cours quand le serveur s'arrête.
SHUTDOWN_GRACE_SECONDS = 8


def expected_webhook_url() -> str:
    if not WEBHOOK_URL:
        raise RuntimeError(
            "BOT_RUN_MODE=webhook mais WEBHOOK_URL manquant dans .env "
            "(URL publique du tunnel, sans le chemin)."
        )
    return WEBHOOK_URL.rstrip("/") + WEBHOOK_PATH


def _require_secret() -> str:
    # Sans secret, aiogram accepterait toute requête : un webhook grand
    # ouvert, sans erreur ni avertissement (trouvaille security-reviewer).
    if not WEBHOOK_SECRET_TOKEN:
        raise RuntimeError(
            "WEBHOOK_SECRET_TOKEN manquant — sans lui n'importe qui connaissant "
            "l'URL du webhook peut injecter de faux updates. Génère-en un : "
            'python -c "import secrets; print(secrets.token_hex(32))"'
        )
    return WEBHOOK_SECRET_TOKEN


class ExactlyOnceRequestHandler(SimpleRequestHandler):
    """Traite l'update avant de répondre, une seule fois (voir en tête)."""

    def __init__(self, dispatcher: Dispatcher, bot: Bot, secret_token: str, ledger: UpdateLedger) -> None:
        super().__init__(dispatcher=dispatcher, bot=bot, handle_in_background=False, secret_token=secret_token)
        self.ledger = ledger

    def verify_secret(self, telegram_secret_token: str, bot: Bot) -> bool:
        # Jamais « vrai par défaut » : le secret est obligatoire ici.
        return bool(self.secret_token) and secrets.compare_digest(telegram_secret_token, self.secret_token)

    async def handle(self, request: web.Request) -> web.Response:
        bot = await self.resolve_bot(request)
        # Le secret est vérifié AVANT de toucher au registre : sans lui,
        # n'importe qui pourrait marquer des numéros d'update comme traités.
        if not self.verify_secret(request.headers.get("X-Telegram-Bot-Api-Secret-Token", ""), bot):
            return web.Response(body="Unauthorized", status=401)
        try:
            update = await request.json(loads=bot.session.json_loads)
            update_id = int(update["update_id"])
        except (ValueError, KeyError, TypeError):
            return web.Response(body="Bad Request", status=400)

        claim = await self.ledger.claim(update_id)
        if claim is Claim.DONE:
            return web.json_response({})
        if claim is Claim.BUSY:
            # Traitée en ce moment par une autre instance : Telegram renverra,
            # et la trouvera alors traitée.
            return web.Response(body="Busy", status=503)

        try:
            result = await self.dispatcher.feed_raw_update(bot=bot, update=update, **self.data)
        except BaseException:
            await self.ledger.release(update_id)
            logger.exception("Update %s : échec du traitement, Telegram la renverra", update_id)
            raise
        await self.ledger.complete(update_id)
        return web.Response(body=self._build_response_writer(bot=bot, result=result))

    __call__ = handle


def ledger_for(bot: Bot, dp: Dispatcher) -> UpdateLedger:
    storage = dp.storage
    if not isinstance(storage, RedisStorage):
        raise RuntimeError("Le webhook exige le stockage Redis du bot (registre des updates partagé entre instances).")
    return UpdateLedger(storage.redis, bot.id)


def build_webhook_app(bot: Bot, dp: Dispatcher, ledger: UpdateLedger | None = None) -> web.Application:
    secret = _require_secret()
    app = web.Application()
    ExactlyOnceRequestHandler(
        dispatcher=dp, bot=bot, secret_token=secret, ledger=ledger or ledger_for(bot, dp)
    ).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    async def health(request: web.Request) -> web.Response:
        return web.json_response({"status": "ok"})

    app.router.add_get("/health", health)
    return app


async def ensure_webhook_registered(bot: Bot) -> None:
    """Refuse de démarrer si Telegram n'envoie pas les updates ici : sinon le
    bot tournerait sans jamais rien recevoir, sans que personne ne le voie."""
    expected = expected_webhook_url()
    info = await bot.get_webhook_info()
    if info.url != expected:
        raise RuntimeError(
            f"Le webhook enregistré chez Telegram ({info.url or 'aucun'}) n'est pas {expected}. "
            "Enregistre-le une fois : python -m telegram_bot.webhook_setup"
        )


async def run_webhook(bot: Bot, dp: Dispatcher) -> None:
    expected_webhook_url()
    app = build_webhook_app(bot, dp)  # lève RuntimeError si WEBHOOK_SECRET_TOKEN manquant
    await ensure_webhook_registered(bot)

    runner = web.AppRunner(app, shutdown_timeout=SHUTDOWN_GRACE_SECONDS)
    await runner.setup()
    site = web.TCPSite(runner, WEBHOOK_LISTEN_HOST, WEBHOOK_LISTEN_PORT)
    await site.start()
    print(f"✅ NEXIS HUB Bot démarré (webhook -> {expected_webhook_url()}).")
    print(f"   Serveur local à l'écoute sur http://{WEBHOOK_LISTEN_HOST}:{WEBHOOK_LISTEN_PORT}{WEBHOOK_PATH}")

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:  # Windows : Ctrl+C lève KeyboardInterrupt
            pass
    try:
        await stop.wait()
    finally:
        # Ferme l'écoute puis attend les updates en cours (shutdown_timeout).
        await runner.cleanup()
