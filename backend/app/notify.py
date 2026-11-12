import logging
import os

import httpx
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

logger = logging.getLogger(__name__)


def send_telegram_message(telegram_id: int, text: str, reply_markup: dict | None = None) -> bool:
    """Envoie un message Telegram depuis le backend (API HTTP Telegram, appel
    synchrone : pas de boucle aiogram ici).

    Ne lève jamais : une notification ratée ne doit pas faire échouer
    l'opération qui l'a déclenchée (même philosophie que `_safe_backend_call`
    dans `main.py` pour les appels bot → backend). Renvoie False si le
    message n'est pas parti.
    """
    return _send("sendMessage", telegram_id, {"text": text}, reply_markup)


def send_telegram_photo(telegram_id: int, file_id: str, caption: str, reply_markup: dict | None = None) -> bool:
    """Photo déjà connue de Telegram (`file_id` reçu par le bot), avec sa
    légende. Mêmes règles que `send_telegram_message`."""
    return _send("sendPhoto", telegram_id, {"photo": file_id, "caption": caption}, reply_markup)


def _send(method: str, telegram_id: int, content: dict, reply_markup: dict | None) -> bool:
    if not BOT_TOKEN:
        logger.warning("BOT_TOKEN manquant : notification Telegram ignorée (%s)", telegram_id)
        return False
    try:
        response = httpx.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/{method}",
            json={"chat_id": telegram_id, **content, "parse_mode": "HTML", **({"reply_markup": reply_markup} if reply_markup else {})},
            timeout=5.0,
        )
        response.raise_for_status()
    except httpx.HTTPError:
        logger.exception("Échec d'envoi de notification Telegram à %s (%s)", telegram_id, method)
        return False
    return True
