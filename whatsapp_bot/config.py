"""Réglages du service WhatsApp, lus et vérifiés au démarrage.

Le service refuse de démarrer sans ses secrets, **même en développement** :
un webhook sans secret d'application accepterait n'importe quel faux
message. Les messages d'erreur nomment les variables, jamais leur valeur.

| Variable | Rôle |
| --- | --- |
| `WHATSAPP_APP_SECRET` | Secret de l'application Meta : vérifie la signature des webhooks |
| `WHATSAPP_VERIFY_TOKEN` | Jeton choisi par Nexis, demandé par Meta une fois pour valider l'adresse du webhook |
| `WHATSAPP_ACCESS_TOKEN` | Jeton d'un utilisateur système Meta : envoie les messages |
| `WHATSAPP_PHONE_NUMBER_ID` | Identifiant du numéro WhatsApp de Nexis chez Meta (pas un secret) |
| `WHATSAPP_GRAPH_URL` | Adresse de l'API de Meta (défaut : https://graph.facebook.com/v23.0) ; le faux serveur Meta en local |
| `BACKEND_BASE_URL`, `BACKEND_API_KEY_WHATSAPP` | Le backend, et la clé du canal WhatsApp |
| `REDIS_URL` | Messages déjà traités et étape de chaque conversation |
| `NEXIS_BOT_USERNAME`, `MINI_APP_URL` | Liens montrés à qui veut devenir prestataire (Telegram, Mini App) |
| `WHATSAPP_LISTEN_HOST`, `WHATSAPP_LISTEN_PORT` | Écoute locale (défaut 127.0.0.1:8003) |
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlparse

DEFAULT_GRAPH_URL = "https://graph.facebook.com/v23.0"
MIN_SECRET_LENGTH = 32


class ConfigurationError(RuntimeError):
    """Réglage manquant ou douteux : le service ne démarre pas."""


@dataclass(frozen=True)
class Settings:
    app_secret: str
    verify_token: str
    access_token: str
    phone_number_id: str
    graph_url: str
    backend_url: str
    backend_key: str
    redis_url: str
    telegram_bot_username: str | None
    mini_app_url: str | None
    listen_host: str = "127.0.0.1"
    listen_port: int = 8003

    @property
    def telegram_bot_link(self) -> str | None:
        return f"https://t.me/{self.telegram_bot_username}" if self.telegram_bot_username else None

    @property
    def public_site(self) -> str | None:
        """Domaine public de la Mini App (pages de lecture des conditions)."""
        parts = urlparse(self.mini_app_url or "")
        return f"https://{parts.netloc}" if parts.scheme == "https" and parts.netloc else None


def _get(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def load() -> Settings:
    """Tous les problèmes d'un coup, pour ne pas corriger le `.env` en dix
    allers-retours."""
    import nexis_config

    env = nexis_config.environnement()
    errors: list[str] = []
    required = (
        "WHATSAPP_APP_SECRET",
        "WHATSAPP_VERIFY_TOKEN",
        "WHATSAPP_ACCESS_TOKEN",
        "WHATSAPP_PHONE_NUMBER_ID",
        "BACKEND_API_KEY_WHATSAPP",
    )
    for name in required:
        if not _get(name):
            errors.append(f"{name} manquant")
    for name in ("WHATSAPP_VERIFY_TOKEN", "BACKEND_API_KEY_WHATSAPP"):
        value = _get(name)
        if value and len(value) < MIN_SECRET_LENGTH:
            errors.append(f"{name} trop court (au moins {MIN_SECRET_LENGTH} caractères)")
    if env != "developpement":
        for name in ("BACKEND_BASE_URL", "REDIS_URL", "NEXIS_BOT_USERNAME", "MINI_APP_URL"):
            if not _get(name):
                errors.append(f"{name} manquant")
        graph = _get("WHATSAPP_GRAPH_URL", DEFAULT_GRAPH_URL)
        if urlparse(graph).scheme != "https":
            # Hors du PC, jamais le faux serveur Meta ni une adresse en clair.
            errors.append("WHATSAPP_GRAPH_URL doit être en https")
    username = _get("NEXIS_BOT_USERNAME").lstrip("@")
    if username and not username.replace("_", "").isalnum():
        errors.append("NEXIS_BOT_USERNAME invalide")
    port = _get("WHATSAPP_LISTEN_PORT", "8003")
    if not port.isdigit():
        errors.append("WHATSAPP_LISTEN_PORT n'est pas un nombre")
    if errors:
        raise ConfigurationError(f"Configuration WhatsApp invalide ({env}) : " + " ; ".join(errors))
    return Settings(
        app_secret=_get("WHATSAPP_APP_SECRET"),
        verify_token=_get("WHATSAPP_VERIFY_TOKEN"),
        access_token=_get("WHATSAPP_ACCESS_TOKEN"),
        phone_number_id=_get("WHATSAPP_PHONE_NUMBER_ID"),
        graph_url=_get("WHATSAPP_GRAPH_URL", DEFAULT_GRAPH_URL).rstrip("/"),
        backend_url=_get("BACKEND_BASE_URL", "http://127.0.0.1:8000").rstrip("/"),
        backend_key=_get("BACKEND_API_KEY_WHATSAPP"),
        redis_url=_get("REDIS_URL", "redis://localhost:6379/0"),
        telegram_bot_username=username or None,
        mini_app_url=_get("MINI_APP_URL") or None,
        listen_host=_get("WHATSAPP_LISTEN_HOST", "127.0.0.1"),
        listen_port=int(port),
    )
