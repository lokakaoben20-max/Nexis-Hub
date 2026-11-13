"""Journaux de Nexis Hub : une ligne JSON par événement, données sensibles masquées.

Chaque processus appelle `configurer(service)` au démarrage : JSON hors
développement, lignes lisibles sur le PC, masquées dans les deux cas. La supervision (Cloud Logging) lit le JSON tel quel : niveau,
service, message, exception.

Le masquage s'applique à tout ce qui passe par `logging`, y compris les
bibliothèques : httpx journalise l'adresse de chaque requête, et l'adresse
de l'API Telegram contient le jeton du bot. Sont masqués :

- les jetons de bot Telegram (`123456:AA...`), y compris dans les adresses ;
- les numéros de téléphone (internationaux, 243…, et locaux 0XXXXXXXXX) ;
- les valeurs des en-têtes et paramètres de secret (`X-API-Key`,
  `secret_token`, `Authorization`, `password`).

Règle complémentaire, qu'aucun masquage ne remplace : ne jamais journaliser
le texte d'un message d'utilisateur ni le contenu d'une pièce d'identité.
"""

from __future__ import annotations

import json
import logging
import re
import sys
from datetime import datetime, timezone

MASQUE = "***"

_MOTIFS = (
    # Jeton de bot Telegram : identifiant numérique, deux-points, 35 caractères.
    (re.compile(r"\d{6,12}:[A-Za-z0-9_-]{30,}"), "<jeton-bot>"),
    # En-têtes, paramètres et champs de secret.
    (
        re.compile(
            r"(?i)((?:x-api-key|authorization|secret_token|secret|password|mot_de_passe|api_key|token)"
            r"[\"']?\s*[:=]\s*[\"']?)(?:bearer\s+)?[^\s\"'&,;}]+"
        ),
        r"\1" + MASQUE,
    ),
    # Téléphones : format international (+…), 243… sans le +, et format local
    # congolais (0 suivi de 9 chiffres). Les identifiants Telegram (suites de
    # chiffres sans 0 ni + en tête) restent lisibles : ils servent au support.
    (re.compile(r"\+\d(?:[\s.-]?\d){7,14}"), "<numéro>"),
    (re.compile(r"(?<![\d.])(?:243|0)(?:[\s.-]?\d){9}(?![\d.])"), "<numéro>"),
)


def masquer(texte: str) -> str:
    for motif, remplacement in _MOTIFS:
        texte = motif.sub(remplacement, texte)
    return texte


class FormatJson(logging.Formatter):
    def __init__(self, service: str) -> None:
        super().__init__()
        self.service = service

    def format(self, record: logging.LogRecord) -> str:
        entree = {
            "horodatage": datetime.fromtimestamp(record.created, timezone.utc).isoformat(timespec="milliseconds"),
            "severity": record.levelname,  # nom lu par Cloud Logging
            "service": self.service,
            "journal": record.name,
            "message": masquer(record.getMessage()),
        }
        if record.exc_info:
            entree["exception"] = masquer(self.formatException(record.exc_info))
        return json.dumps(entree, ensure_ascii=False)


class FormatLisible(logging.Formatter):
    """Sur le PC : une ligne lisible, masquée elle aussi."""

    def __init__(self) -> None:
        super().__init__("%(asctime)s %(levelname)s %(name)s : %(message)s")

    def format(self, record: logging.LogRecord) -> str:
        return masquer(super().format(record))


def configurer(service: str, niveau: int = logging.INFO, json_: bool | None = None) -> None:
    """Remplace la configuration de `logging` : JSON masqué sur la sortie
    standard hors développement, lignes lisibles masquées sur le PC.
    Idempotent."""
    if json_ is None:
        import nexis_config

        json_ = nexis_config.environnement() != "developpement"
    gestionnaire = logging.StreamHandler(sys.stdout)
    gestionnaire.setFormatter(FormatJson(service) if json_ else FormatLisible())
    gestionnaire._nexis = True  # type: ignore[attr-defined]
    racine = logging.getLogger()
    # Remplace seulement notre propre sortie : celles d'autrui (capture des
    # tests) restent en place.
    racine.handlers[:] = [h for h in racine.handlers if not getattr(h, "_nexis", False)] + [gestionnaire]
    racine.setLevel(niveau)
    # uvicorn installe ses propres sorties : on les ramène sur la racine.
    for nom in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        journal = logging.getLogger(nom)
        journal.handlers[:] = []
        journal.propagate = True
