"""Stockage des étapes en cours (FSM aiogram) dans Redis.

Avant : `MemoryStorage`. Chaque redémarrage du bot (mise à jour, panne,
déploiement) effaçait en silence toutes les inscriptions, créations de mission,
devis et notations en cours ; le message suivant de l'utilisateur n'avait plus
d'étape associée et n'obtenait aucune réponse. Constaté en test réel le
2026-10-06 : un prestataire bloqué après l'envoi de sa pièce d'identité.

Redis fait déjà partie de la pile (broker Celery, `docker compose up -d`). Le bot
refuse de démarrer s'il ne le joint pas : démarrer quand même avec un stockage
en mémoire reviendrait à perdre de nouveau ces étapes sans que personne ne le
voie.
"""

import os
from datetime import timedelta

from aiogram.fsm.storage.redis import DefaultKeyBuilder, RedisStorage

DEFAULT_REDIS_URL = "redis://localhost:6379/0"

# Une étape abandonnée (inscription laissée en plan, devis jamais terminé)
# disparaît après ce délai. Assez long pour qu'un utilisateur reprenne le
# lendemain, assez court pour ne pas garder indéfiniment des numéros de
# téléphone et des photos de pièce d'identité saisis à moitié.
FSM_TTL = timedelta(days=3)


def redis_url() -> str:
    return os.getenv("REDIS_URL", DEFAULT_REDIS_URL)


def build_fsm_storage(url: str | None = None) -> RedisStorage:
    """Construit le stockage sans se connecter (la connexion est paresseuse) :
    importer `main` dans les tests ne demande donc pas de Redis."""
    return RedisStorage.from_url(
        url or redis_url(),
        # Préfixe distinct des clés Celery qui partagent la même base Redis.
        key_builder=DefaultKeyBuilder(prefix="nexis_fsm"),
        state_ttl=FSM_TTL,
        data_ttl=FSM_TTL,
    )


async def ensure_fsm_storage_ready(storage: RedisStorage) -> None:
    """Vérifie au démarrage que Redis répond, sinon lève une erreur claire."""
    try:
        await storage.redis.ping()
    except Exception as exc:
        raise RuntimeError(
            "Redis injoignable : le bot a besoin de Redis pour garder les étapes "
            "en cours (inscriptions, missions, devis) entre deux redémarrages. "
            f"Démarre-le (docker compose up -d redis) ou vérifie REDIS_URL. Détail : {exc}"
        ) from exc
