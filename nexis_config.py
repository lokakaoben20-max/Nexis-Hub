"""Configuration de Nexis Hub : vérifiée au démarrage de chaque processus.

`APP_ENV` dit où l'on tourne :

- `developpement` (défaut, PC de Ben, tests) : rien n'est imposé, les valeurs
  par défaut du code s'appliquent ;
- `test` (environnement hébergé de test) et `production` : chaque processus
  refuse de démarrer s'il lui manque une variable, si un secret est trop
  court, ou si une valeur est incohérente. Aucune valeur par défaut ne
  s'applique en silence, surtout pour l'argent (frais, seuils de retrait).

Les messages d'erreur nomment les variables, jamais leur valeur.
"""

from __future__ import annotations

import os
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse

ENVIRONNEMENTS = ("developpement", "test", "production")
DEVISES = ("USD", "CDF")
LONGUEUR_MIN_SECRET = 32

# Réglages d'argent lus par backend/app/payment_gateway.py et mobile_money.py.
TAUX = ("COLLECTION_FEE_RATE", "PAYOUT_FEE_RATE")
MONTANTS_PAR_DEVISE = ("PAYOUT_FEE_FIXED", "PAYOUT_MINIMUM", "PAYOUT_AUTO_LIMIT")

ROLES = {
    "backend": ("DATABASE_URL", "BACKEND_API_KEY_TELEGRAM", "APP_CODE_HMAC_KEY", "BOT_TOKEN", "ADMIN_TELEGRAM_ID", "PAYMENT_GATEWAY"),
    "taches": ("DATABASE_URL", "BOT_TOKEN", "ADMIN_TELEGRAM_ID", "PAYMENT_GATEWAY"),
    "migration": ("DATABASE_URL",),
    "bot": ("BOT_TOKEN", "BACKEND_BASE_URL", "BACKEND_API_KEY_TELEGRAM", "REDIS_URL", "MINI_APP_URL", "ADMIN_TELEGRAM_ID", "BOT_RUN_MODE"),
    "miniapp": ("BOT_TOKEN", "BACKEND_BASE_URL", "BACKEND_API_KEY_TELEGRAM"),
}
SECRETS = ("BACKEND_API_KEY_TELEGRAM", "APP_CODE_HMAC_KEY", "WEBHOOK_SECRET_TOKEN")
ROLES_ARGENT = ("backend", "taches")


class ConfigurationInvalide(RuntimeError):
    pass


def environnement() -> str:
    valeur = os.getenv("APP_ENV", "developpement").strip() or "developpement"
    if valeur not in ENVIRONNEMENTS:
        raise ConfigurationInvalide(f"APP_ENV inconnu : attendu l'un de {', '.join(ENVIRONNEMENTS)}")
    return valeur


def _decimal(nom: str, erreurs: list[str], minimum: Decimal, maximum: Decimal | None = None) -> None:
    brut = os.getenv(nom, "").strip()
    if not brut:
        erreurs.append(f"{nom} manquant")
        return
    try:
        valeur = Decimal(brut)
    except InvalidOperation:
        erreurs.append(f"{nom} n'est pas un nombre")
        return
    if not valeur.is_finite() or valeur < minimum or (maximum is not None and valeur > maximum):
        erreurs.append(f"{nom} hors limites")


def problemes(role: str) -> list[str]:
    """Liste des problèmes pour ce rôle dans l'environnement courant (vide si
    tout va bien, toujours vide en développement)."""
    if role not in ROLES:
        raise ValueError(f"rôle inconnu : {role}")
    env = environnement()
    if env == "developpement":
        return []

    erreurs: list[str] = []
    requises = list(ROLES[role])
    if role == "bot" and os.getenv("BOT_RUN_MODE", "").strip() == "webhook":
        requises += ["WEBHOOK_URL", "WEBHOOK_SECRET_TOKEN"]
    for nom in requises:
        if not os.getenv(nom, "").strip():
            erreurs.append(f"{nom} manquant")

    for nom in SECRETS:
        valeur = os.getenv(nom, "").strip()
        if nom in requises and valeur and len(valeur) < LONGUEUR_MIN_SECRET:
            erreurs.append(f"{nom} trop court (au moins {LONGUEUR_MIN_SECRET} caractères)")

    url_base = os.getenv("DATABASE_URL", "").strip()
    if "DATABASE_URL" in requises and url_base and not url_base.startswith("postgresql"):
        erreurs.append("DATABASE_URL doit viser Postgres")

    admin = os.getenv("ADMIN_TELEGRAM_ID", "").strip()
    if "ADMIN_TELEGRAM_ID" in requises and admin and not admin.isdigit():
        erreurs.append("ADMIN_TELEGRAM_ID doit être un identifiant Telegram numérique")

    if role == "bot":
        mode = os.getenv("BOT_RUN_MODE", "").strip()
        if mode and mode != "webhook":
            # Hébergé, un seul mode : plusieurs instances, aucune ne fait de polling.
            erreurs.append("BOT_RUN_MODE doit valoir webhook hors développement")
    for nom in ("WEBHOOK_URL", "MINI_APP_URL"):
        valeur = os.getenv(nom, "").strip()
        if nom in requises and valeur and urlparse(valeur).scheme != "https":
            erreurs.append(f"{nom} doit être en https")

    if role in ROLES_ARGENT:
        passerelle = os.getenv("PAYMENT_GATEWAY", "").strip()
        if env == "production" and passerelle == "simulation":
            erreurs.append("PAYMENT_GATEWAY=simulation interdit en production")
        if env == "test" and passerelle and passerelle != "simulation":
            erreurs.append("PAYMENT_GATEWAY doit valoir simulation en test (jamais d'argent réel)")
        for nom in TAUX:
            _decimal(nom, erreurs, Decimal("0"), Decimal("0.2"))
        for prefixe in MONTANTS_PAR_DEVISE:
            for devise in DEVISES:
                _decimal(f"{prefixe}_{devise}", erreurs, Decimal("0"))
    return erreurs


def verifier(role: str) -> str:
    """À appeler au démarrage : lève ConfigurationInvalide avec tous les
    problèmes à la fois. Rend l'environnement."""
    erreurs = problemes(role)
    if erreurs:
        raise ConfigurationInvalide(
            f"Configuration invalide pour « {role} » ({environnement()}) : " + " ; ".join(erreurs)
        )
    return environnement()
