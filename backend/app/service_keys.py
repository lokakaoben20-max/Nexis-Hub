"""Clés de service du backend : une par canal (étape 1 du plan WhatsApp,
/mnt/project-files/whatsapp/plan-implementation-whatsapp-2026-11-07.md).

La clé envoyée dans `X-API-Key` dit **quel canal** appelle. Un canal ne peut
donc agir qu'en son propre nom : le service WhatsApp ne peut jamais se
présenter comme le bot Telegram, ni l'inverse.

- `BACKEND_API_KEY_TELEGRAM` : bot Telegram et Mini App (même canal, Telegram).
- `BACKEND_API_KEY_WHATSAPP` : service WhatsApp. Facultative tant que ce
  service ne tourne pas ; sans elle, aucun appel WhatsApp n'est accepté.

Règles vérifiées au démarrage (`check_configuration`), qui refuse de démarrer
plutôt que de tourner avec une configuration douteuse :

- l'ancienne clé unique `BACKEND_API_KEY` ne doit plus exister (sinon un
  oubli de mise à jour du `.env` passerait inaperçu) ;
- la clé Telegram est obligatoire ;
- chaque clé fait au moins 32 caractères, et deux canaux n'ont jamais la
  même clé.
"""

from __future__ import annotations

import hmac
import os

from backend.app import ledger

LEGACY_KEY_VARIABLE = "BACKEND_API_KEY"
MIN_KEY_LENGTH = 32

# Canal -> variable d'environnement de sa clé.
KEY_VARIABLES = {
    ledger.TELEGRAM: "BACKEND_API_KEY_TELEGRAM",
    ledger.WHATSAPP: "BACKEND_API_KEY_WHATSAPP",
}
REQUIRED_CHANNELS = (ledger.TELEGRAM,)


class ConfigurationError(RuntimeError):
    """Configuration des clés refusée : le backend ne démarre pas."""


def configured_keys() -> dict[str, str]:
    """Clés lues à chaque appel (un changement du `.env` ne demande que le
    redémarrage du processus, rien n'est gardé en double)."""
    keys = {}
    for channel, variable in KEY_VARIABLES.items():
        value = os.getenv(variable, "").strip()
        if value:
            keys[channel] = value
    return keys


def check_configuration() -> None:
    if os.getenv(LEGACY_KEY_VARIABLE, "").strip():
        raise ConfigurationError(
            f"{LEGACY_KEY_VARIABLE} n'est plus utilisée : renomme-la en "
            f"{KEY_VARIABLES[ledger.TELEGRAM]} dans le .env (même valeur côté bot et backend), "
            "puis supprime l'ancienne ligne."
        )
    keys = configured_keys()
    for channel in REQUIRED_CHANNELS:
        if channel not in keys:
            raise ConfigurationError(f"{KEY_VARIABLES[channel]} manquante dans le .env")
    for channel, value in keys.items():
        if len(value) < MIN_KEY_LENGTH:
            raise ConfigurationError(f"{KEY_VARIABLES[channel]} trop courte ({MIN_KEY_LENGTH} caractères au moins)")
    if len(set(keys.values())) != len(keys):
        raise ConfigurationError("Deux canaux ont la même clé de service : chaque canal doit avoir la sienne")


def channel_for_key(presented: str | None) -> str | None:
    """Canal à qui appartient la clé présentée, ou None. Toutes les clés sont
    comparées en temps constant, sans s'arrêter à la première."""
    if not presented:
        return None
    found = None
    for channel, value in configured_keys().items():
        if hmac.compare_digest(presented.encode(), value.encode()):
            found = channel
    return found
