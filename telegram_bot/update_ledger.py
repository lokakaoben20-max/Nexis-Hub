"""Registre des updates Telegram reçues par webhook : chacune traitée une fois.

En webhook, Telegram renvoie une update tant qu'il n'a pas reçu de réponse
2xx (erreur, coupure, délai de 60 s dépassé). Le serveur ne répond donc
qu'**après** avoir traité l'update (voir `webhook_server.py`), et ce registre
empêche qu'un renvoi la traite une seconde fois, y compris quand plusieurs
instances du bot tournent derrière le même webhook.

Un état par update, dans Redis (partagé entre instances) :

- absente      : jamais vue, ou traitement échoué (clé effacée) → à traiter ;
- `en_cours`   : une instance la traite. Durée de vie `PROCESSING_TTL` : si
                 l'instance meurt au milieu, la clé expire et le renvoi
                 suivant de Telegram est traité ;
- `fait`       : traitée. Gardée `DONE_TTL`, la durée pendant laquelle
                 Telegram peut encore la renvoyer.

Redis injoignable : l'erreur remonte, le serveur répond 500, Telegram
renverra. Jamais de traitement sans registre.
"""

from __future__ import annotations

from datetime import timedelta
from enum import Enum

from redis.asyncio import Redis

KEY_PREFIX = "nexis_update"
# Au-delà des 60 s d'attente de Telegram, avec une marge.
PROCESSING_TTL = timedelta(seconds=120)
# Telegram garde une update non acquittée 24 h.
DONE_TTL = timedelta(hours=25)

PROCESSING = "en_cours"
DONE = "fait"


class Claim(Enum):
    ACQUIRED = "acquired"  # à traiter par cet appelant
    DONE = "done"  # déjà traitée : répondre 200 sans rien refaire
    BUSY = "busy"  # en cours ailleurs : répondre une erreur, Telegram renverra


class UpdateLedger:
    def __init__(self, redis: Redis, bot_id: int) -> None:
        self._redis = redis
        self._bot_id = bot_id

    def _key(self, update_id: int) -> str:
        return f"{KEY_PREFIX}:{self._bot_id}:{update_id}"

    async def claim(self, update_id: int) -> Claim:
        key = self._key(update_id)
        if await self._redis.set(key, PROCESSING, nx=True, ex=PROCESSING_TTL):
            return Claim.ACQUIRED
        state = await self._redis.get(key)
        if isinstance(state, bytes):
            state = state.decode()
        if state == DONE:
            return Claim.DONE
        if state is None:
            # Expirée entre les deux lectures : on retente une fois.
            if await self._redis.set(key, PROCESSING, nx=True, ex=PROCESSING_TTL):
                return Claim.ACQUIRED
        return Claim.BUSY

    async def ping(self) -> None:
        await self._redis.ping()

    async def complete(self, update_id: int) -> None:
        await self._redis.set(self._key(update_id), DONE, ex=DONE_TTL)

    async def release(self, update_id: int) -> None:
        """Traitement échoué : la clé disparaît pour que le renvoi soit traité."""
        await self._redis.delete(self._key(update_id))
