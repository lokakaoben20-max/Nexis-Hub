"""Surveillance de l'adresse publique du webhook : alerte les admins quand
Internet n'arrive plus jusqu'au bot.

Le 2026-11-15, le tunnel Cloudflare du PC est resté sans connexion après une
coupure, alors que son service Windows affichait « Running ». Plus rien
n'arrivait : ni les messages du bot, ni la Mini App (même adresse). Personne
ne l'a su avant de voir une vieille page sur un téléphone.

Ce que fait la surveillance, à chaque tour (`WEBHOOK_WATCH_INTERVAL_SECONDS`) :

- elle envoie, **par l'adresse publique**, une requête au webhook sans le
  secret. Seul ce serveur répond alors exactement 401 « Unauthorized » ;
  toute autre réponse (530 de Cloudflare, délai dépassé, autre serveur)
  prouve que le chemin Internet → tunnel → bot est coupé. Rien n'est
  traité : le secret est vérifié avant tout (voir `webhook_server.py`) ;
- elle vérifie chez Telegram que le webhook enregistré est bien le nôtre.

Après `FAILURES_BEFORE_ALERT` échecs de suite, les admins (liste du backend)
reçoivent une alerte dans leur langue ; au retour, un message « rétabli »
avec la durée de la coupure. L'envoi passe par l'API Telegram, qui reste
joignable quand le tunnel est coupé.

Plusieurs instances du bot (production) : l'état « alerte envoyée » est
dans Redis (`SET NX` à la coupure, `GETDEL` au retour), donc une seule
alerte et un seul « rétabli » par coupure, quel que soit le nombre
d'instances. Une erreur de la surveillance n'arrête jamais le bot.
"""

from __future__ import annotations

import asyncio
import html
import logging
import os
import time

import httpx
from aiogram import Bot
from redis.asyncio import Redis

from messages import get_message
from telegram_bot import backend_client

logger = logging.getLogger(__name__)

KEY_PREFIX = "nexis_webhook_watch"
FAILURES_BEFORE_ALERT = 2
PROBE_TIMEOUT_SECONDS = 15.0
DEFAULT_INTERVAL_SECONDS = 120


def interval_seconds() -> int:
    """0 désactive la surveillance (déconseillé hors tests)."""
    raw = os.getenv("WEBHOOK_WATCH_INTERVAL_SECONDS", str(DEFAULT_INTERVAL_SECONDS)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"WEBHOOK_WATCH_INTERVAL_SECONDS doit être un nombre de secondes (reçu {raw!r}).") from exc
    if value < 0:
        raise RuntimeError("WEBHOOK_WATCH_INTERVAL_SECONDS ne peut pas être négatif.")
    return value


async def probe_public_url(url: str, http: httpx.AsyncClient) -> str | None:
    """None si la requête publique arrive bien jusqu'à ce bot, sinon la raison."""
    try:
        response = await http.post(url, json={}, timeout=PROBE_TIMEOUT_SECONDS)
    except httpx.TimeoutException:
        return "délai dépassé"
    except httpx.HTTPError as exc:
        return f"connexion impossible ({type(exc).__name__})"
    if response.status_code == 401 and response.text.strip() == "Unauthorized":
        return None
    return f"réponse HTTP {response.status_code}"


async def check_registration(bot: Bot, expected_url: str) -> str | None:
    """None si Telegram envoie bien les updates à notre adresse."""
    try:
        info = await bot.get_webhook_info()
    except Exception as exc:
        # Telegram injoignable : ce n'est pas notre adresse publique qui est en
        # cause, et l'alerte ne pourrait de toute façon pas partir.
        logger.warning("Surveillance webhook : getWebhookInfo impossible (%s)", type(exc).__name__)
        return None
    if info.url != expected_url:
        return f"webhook enregistré ailleurs ({info.url or 'aucun'})"
    return None


class WebhookWatch:
    def __init__(self, bot: Bot, redis: Redis, public_url: str, http: httpx.AsyncClient) -> None:
        self.bot = bot
        self.redis = redis
        self.public_url = public_url
        self.http = http
        self.failures = 0

    @property
    def _key(self) -> str:
        return f"{KEY_PREFIX}:{self.bot.id}:down_since"

    async def check_once(self) -> None:
        reason = await probe_public_url(self.public_url, self.http)
        if reason is None:
            reason = await check_registration(self.bot, self.public_url)
        if reason is None:
            self.failures = 0
            await self._recovered()
            return
        self.failures += 1
        logger.warning("Surveillance webhook : %s injoignable (%s), échec %s", self.public_url, reason, self.failures)
        if self.failures >= FAILURES_BEFORE_ALERT:
            await self._down(reason)

    async def _down(self, reason: str) -> None:
        now = int(time.time())
        if not await self.redis.set(self._key, now, nx=True):
            return  # alerte déjà envoyée pour cette coupure (ici ou par une autre instance)
        logger.error("Surveillance webhook : coupure de %s (%s), alerte aux admins", self.public_url, reason)
        await self._notify_admins("admin_webhook_down", url=self.public_url, raison=reason)

    async def _recovered(self) -> None:
        since = await self.redis.getdel(self._key)
        if since is None:
            return
        minutes = max(1, round((time.time() - int(since)) / 60))
        logger.info("Surveillance webhook : %s de nouveau joignable (coupure ~%s min)", self.public_url, minutes)
        await self._notify_admins("admin_webhook_recovered", url=self.public_url, minutes=minutes)

    async def _notify_admins(self, key: str, **values) -> None:
        admins = await backend_client.admin_telegram_ids()
        if not admins:
            logger.error("Surveillance webhook : aucun admin à prévenir (backend injoignable ou aucun admin nommé)")
            return
        safe = {name: html.escape(str(value)) for name, value in values.items()}
        for admin_id in admins:
            try:
                lang = await backend_client.get_language(admin_id)
                await self.bot.send_message(admin_id, get_message(key, lang, **safe))
            except Exception:
                logger.warning("Surveillance webhook : alerte non envoyée à un admin", exc_info=True)

    async def run(self, every: int) -> None:
        while True:
            await asyncio.sleep(every)
            try:
                await self.check_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Surveillance webhook : tour en échec, on continue")


async def watch_forever(bot: Bot, redis: Redis, public_url: str) -> None:
    every = interval_seconds()
    if every == 0:
        logger.warning("Surveillance du webhook désactivée (WEBHOOK_WATCH_INTERVAL_SECONDS=0)")
        return
    async with httpx.AsyncClient(follow_redirects=False) as http:
        await WebhookWatch(bot, redis, public_url, http).run(every)
