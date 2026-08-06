import logging
import os

import httpx
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

logger = logging.getLogger(__name__)


def send_telegram_message(telegram_id: int, text: str) -> None:
    """Envoie un message Telegram depuis un worker Celery.

    Un worker Celery est un process séparé, sans boucle asyncio/aiogram comme
    `main.py` — plutôt que d'y instancier un `aiogram.Bot` pour un seul appel
    synchrone, on appelle directement l'API HTTP Telegram (`httpx.post`).

    Ne lève jamais : une notification ratée ne doit pas faire échouer la tâche
    Celery qui l'a déclenchée (même philosophie que `_safe_backend_call` dans
    `main.py` pour les appels bot → backend).
    """
    if not BOT_TOKEN:
        logger.warning("BOT_TOKEN manquant : notification Telegram ignorée (%s)", telegram_id)
        return
    try:
        response = httpx.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": telegram_id, "text": text, "parse_mode": "HTML"},
            timeout=5.0,
        )
        response.raise_for_status()
    except httpx.HTTPError:
        logger.exception("Échec d'envoi de notification Telegram à %s", telegram_id)
