"""Tâches planifiées du backend : quand elles tournent, et jamais deux fois en même temps.

Remplace Celery (worker + beat). L'alerte « Nouvel appareil », seul envoi
qui passait par `.delay()`, est une boîte d'envoi en base (`Device.alert_due_at`)
vidée chaque minute par la tâche `alertes-nouvel-appareil` : elle ne se perd
pas si un courtier tombe. Une seule définition du
calendrier, ici, sert partout :

- en production, Cloud Scheduler lance `python -m backend.app.taches lancer <nom>`
  (une exécution de tâche Cloud Run) aux heures de `CALENDRIER`, dont il lit
  l'expression cron (`Frequence.cron`) ;
- sur le PC, `python -m backend.app.taches planificateur` fait la même chose
  dans un seul processus.

Une tâche ne tourne jamais deux fois en même temps, même si deux
planificateurs ou deux exécutions se chevauchent : verrou consultatif
Postgres (`pg_try_advisory_lock`) tenu pendant toute l'exécution, libéré par
Postgres lui-même si le processus meurt. Une exécution qui trouve le verrou
pris s'arrête sans rien faire : la suivante passera. Les tâches d'argent
sont en plus idempotentes (elles relisent l'état sous verrou du registre).
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import sys
import threading
import time
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

import nexis_config
import nexis_logs
from backend.app import database, tasks

logger = logging.getLogger("nexis.taches")


@dataclass(frozen=True)
class Frequence:
    """Fréquence en UTC : toutes les `toutes_les_minutes` minutes, ou chaque
    jour à `heure`:`minute`, ou chaque heure à `minute` (heure=None)."""

    toutes_les_minutes: int | None = None
    heure: int | None = None
    minute: int = 0

    def __post_init__(self) -> None:
        if self.toutes_les_minutes is not None:
            if not (1 <= self.toutes_les_minutes <= 59 and 60 % self.toutes_les_minutes == 0):
                raise ValueError("toutes_les_minutes doit diviser 60")
            if self.heure is not None or self.minute:
                raise ValueError("toutes_les_minutes exclut heure et minute")
        if self.heure is not None and not 0 <= self.heure <= 23:
            raise ValueError("heure entre 0 et 23")
        if not 0 <= self.minute <= 59:
            raise ValueError("minute entre 0 et 59")

    @property
    def cron(self) -> str:
        """Expression cron (UTC) donnée à Cloud Scheduler."""
        if self.toutes_les_minutes is not None:
            return f"*/{self.toutes_les_minutes} * * * *"
        if self.heure is None:
            return f"{self.minute} * * * *"
        return f"{self.minute} {self.heure} * * *"

    def est_due(self, instant: datetime) -> bool:
        """Vrai pendant la minute (UTC) où la tâche doit partir."""
        instant = instant.astimezone(timezone.utc)
        if self.toutes_les_minutes is not None:
            return instant.minute % self.toutes_les_minutes == 0
        if self.heure is not None and instant.hour != self.heure:
            return False
        return instant.minute == self.minute


@dataclass(frozen=True)
class Tache:
    fonction: Callable[[], object]
    frequence: Frequence


# Mêmes fréquences que l'ancien `celery_app.beat_schedule`, plus l'alerte
# « Nouvel appareil » (boîte d'envoi, chaque minute).
CALENDRIER: dict[str, Tache] = {
    "relances-prestataires": Tache(tasks.send_provider_reminders, Frequence(toutes_les_minutes=10)),
    "devis-expires": Tache(tasks.check_expired_quotes, Frequence(minute=0)),
    "liberations-automatiques": Tache(tasks.release_auto_confirmed_missions, Frequence(minute=0)),
    "litiges-en-retard": Tache(tasks.alert_overdue_disputes, Frequence(minute=15)),
    "decisions-litiges": Tache(tasks.execute_due_dispute_decisions, Frequence(toutes_les_minutes=10)),
    "verification-mobile-money": Tache(tasks.check_pending_mobile_money, Frequence(toutes_les_minutes=2)),
    "rapprochement-quotidien": Tache(tasks.send_daily_reconciliation, Frequence(heure=6, minute=0)),
    "analytics-quotidiennes": Tache(tasks.send_daily_analytics, Frequence(heure=8, minute=0)),
    "alertes-nouvel-appareil": Tache(tasks.send_pending_device_alerts, Frequence(toutes_les_minutes=1)),
    "purge-nonces": Tache(tasks.purge_request_nonces, Frequence(minute=30)),
}


def cle_de_verrou(nom: str) -> int:
    """Clé stable sur 63 bits (le `hash()` de Python change à chaque processus)."""
    return int.from_bytes(hashlib.sha256(f"nexis.taches.{nom}".encode()).digest()[:8], "big") >> 1


# SQLite (PC, tests) : un seul processus écrit, un verrou local suffit.
_verrous_locaux: dict[str, threading.Lock] = {}
_verrous_locaux_garde = threading.Lock()


@contextmanager
def verrou(nom: str):
    """Rend True si ce processus tient le verrou de la tâche, False sinon."""
    engine = database.engine
    if engine.dialect.name == "postgresql":
        cle = cle_de_verrou(nom)
        # Connexion dédiée, en autocommit : le verrou appartient à la session
        # Postgres, sans transaction ouverte pendant toute la tâche.
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connexion:
            obtenu = bool(connexion.execute(text("SELECT pg_try_advisory_lock(:cle)"), {"cle": cle}).scalar())
            try:
                yield obtenu
            finally:
                if obtenu:
                    connexion.execute(text("SELECT pg_advisory_unlock(:cle)"), {"cle": cle})
        return
    with _verrous_locaux_garde:
        local = _verrous_locaux.setdefault(nom, threading.Lock())
    obtenu = local.acquire(blocking=False)
    try:
        yield obtenu
    finally:
        if obtenu:
            local.release()


def lancer(nom: str) -> str:
    """Exécute une tâche une fois. Rend "faite" ou "deja_en_cours" ; une
    erreur de la tâche remonte (code de sortie non nul, alerte)."""
    tache = CALENDRIER[nom]
    with verrou(nom) as obtenu:
        if not obtenu:
            logger.info("tâche %s déjà en cours ailleurs : rien à faire", nom)
            return "deja_en_cours"
        debut = time.monotonic()
        resultat = tache.fonction()
        logger.info("tâche %s faite en %.1f s (résultat : %s)", nom, time.monotonic() - debut, resultat)
        return "faite"


def taches_dues(instant: datetime) -> list[str]:
    return [nom for nom, tache in CALENDRIER.items() if tache.frequence.est_due(instant)]


def planificateur(arret: threading.Event | None = None, horloge: Callable[[], datetime] | None = None) -> None:
    """Boucle du PC : à chaque nouvelle minute, lance les tâches dues. Une
    tâche en échec est journalisée et n'arrête pas les autres."""
    arret = arret or threading.Event()
    horloge = horloge or (lambda: datetime.now(timezone.utc))
    derniere_minute = None
    while not arret.is_set():
        minute = horloge().replace(second=0, microsecond=0)
        if minute != derniere_minute:
            derniere_minute = minute
            for nom in taches_dues(minute):
                try:
                    lancer(nom)
                except Exception:
                    logger.exception("tâche %s en échec", nom)
        prochaine = minute + timedelta(minutes=1)
        arret.wait(max(0.5, (prochaine - horloge()).total_seconds()))


def main(argv: list[str] | None = None) -> int:
    nexis_logs.configurer("taches")
    parser = argparse.ArgumentParser(prog="python -m backend.app.taches")
    commandes = parser.add_subparsers(dest="commande", required=True)
    commande_lancer = commandes.add_parser("lancer", help="exécute une tâche une fois")
    commande_lancer.add_argument("nom", choices=sorted(CALENDRIER))
    commandes.add_parser("planificateur", help="boucle locale (PC)")
    commandes.add_parser("calendrier", help="affiche les tâches et leur expression cron (UTC)")
    args = parser.parse_args(argv)

    if args.commande != "calendrier":
        # Hors développement, une configuration incomplète empêche de lancer.
        nexis_config.verifier("taches")
    if args.commande == "calendrier":
        for nom, tache in CALENDRIER.items():
            print(f"{nom}\t{tache.frequence.cron}")
        return 0
    if args.commande == "planificateur":
        try:
            planificateur()
        except KeyboardInterrupt:
            pass
        return 0
    try:
        lancer(args.nom)
    except Exception:
        logger.exception("tâche %s en échec", args.nom)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
