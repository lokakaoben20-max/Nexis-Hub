"""Ce que le service WhatsApp garde dans Redis, partagé entre ses instances.

- **Messages reçus** : chaque message (wamid) est traité une fois. Meta
  renvoie un webhook tant qu'il n'a pas reçu de réponse 2xx ; un renvoi
  d'un message déjà traité est écarté ici, sur toutes les instances. C'est
  un filtre rapide : la garantie qu'une écriture n'agit qu'une fois est dans
  le backend (clé d'idempotence = wamid, table `idempotency_keys`).
  États : absent (à traiter), `en_cours` (2 min, au cas où l'instance
  meurt), `fait` (7 jours, seul l'identifiant, jamais le contenu).
- **Étape de conversation** de chaque personne : un petit JSON (étape,
  langue choisie, prénom pendant l'inscription), effacé après 24 h sans
  message. Aucune donnée d'argent : perdu, la personne recommence l'étape.
- **Verrou par personne** : deux messages de la même personne ne sont
  jamais traités en même temps (leur ordre compte). Le second attend que
  Meta le renvoie.

Redis injoignable : l'erreur remonte, le webhook répond une erreur et Meta
renverra. Jamais de traitement sans registre.
"""

from __future__ import annotations

import json
from datetime import timedelta
from enum import Enum

from redis.asyncio import Redis

PREFIX = "nexis_wa"
PROCESSING_TTL = timedelta(minutes=2)
DONE_TTL = timedelta(days=7)
CONVERSATION_TTL = timedelta(hours=24)
LOCK_TTL = timedelta(seconds=60)

PROCESSING = "en_cours"
DONE = "fait"


class Claim(Enum):
    ACQUIRED = "acquired"
    DONE = "done"
    BUSY = "busy"


class Store:
    def __init__(self, redis: Redis, prefix: str = PREFIX) -> None:
        self._redis = redis
        self._prefix = prefix

    def _key(self, kind: str, ident: str) -> str:
        return f"{self._prefix}:{kind}:{ident}"

    async def ping(self) -> None:
        await self._redis.ping()

    # --- Messages reçus -------------------------------------------------------

    async def claim(self, message_id: str) -> Claim:
        key = self._key("msg", message_id)
        if await self._redis.set(key, PROCESSING, nx=True, ex=PROCESSING_TTL):
            return Claim.ACQUIRED
        state = await self._redis.get(key)
        if isinstance(state, bytes):
            state = state.decode()
        if state == DONE:
            return Claim.DONE
        if state is None and await self._redis.set(key, PROCESSING, nx=True, ex=PROCESSING_TTL):
            return Claim.ACQUIRED
        return Claim.BUSY

    async def complete(self, message_id: str) -> None:
        await self._redis.set(self._key("msg", message_id), DONE, ex=DONE_TTL)

    async def release(self, message_id: str) -> None:
        await self._redis.delete(self._key("msg", message_id))

    # --- Verrou par personne -----------------------------------------------------

    async def lock(self, bsuid: str, token: str) -> bool:
        return bool(await self._redis.set(self._key("lock", bsuid), token, nx=True, ex=LOCK_TTL))

    async def unlock(self, bsuid: str, token: str) -> None:
        # N'efface que son propre verrou (un verrou expiré a pu être repris).
        await self._redis.eval(
            "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) end return 0",
            1,
            self._key("lock", bsuid),
            token,
        )

    # --- Étape de conversation ----------------------------------------------------

    async def conversation(self, bsuid: str) -> dict:
        raw = await self._redis.get(self._key("conv", bsuid))
        if raw is None:
            return {}
        try:
            value = json.loads(raw)
        except ValueError:
            return {}
        return value if isinstance(value, dict) else {}

    async def save_conversation(self, bsuid: str, state: dict) -> None:
        key = self._key("conv", bsuid)
        if state:
            await self._redis.set(key, json.dumps(state, ensure_ascii=False), ex=CONVERSATION_TTL)
        else:
            await self._redis.delete(key)
