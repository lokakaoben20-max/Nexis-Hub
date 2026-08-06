import logging
import os
from datetime import datetime, timedelta

from backend.app import crud
from backend.app.celery_app import celery_app
from backend.app.database import SessionLocal
from backend.app.models import BotMission, BotProvider, BotUser
from backend.app.notify import send_telegram_message
from messages import get_message

ADMIN_TELEGRAM_ID = os.getenv("ADMIN_TELEGRAM_ID")

logger = logging.getLogger(__name__)


@celery_app.task(name="backend.app.tasks.check_expired_quotes")
def check_expired_quotes() -> int:
    """Devis `pending` depuis plus de 24h → `expired` (crud.expire_stale_quotes)."""
    db = SessionLocal()
    try:
        expired = crud.expire_stale_quotes(db)
        return len(expired)
    finally:
        db.close()


@celery_app.task(name="backend.app.tasks.release_auto_confirmed_missions")
def release_auto_confirmed_missions() -> int:
    """Auto-libère l'escrow des missions en `awaiting_confirmation` depuis 24h+.

    Réutilise `crud.release_payment` (même chemin que l'endpoint manuel
    `/api/missions/{id}/release`) plutôt que de dupliquer la logique.
    """
    db = SessionLocal()
    try:
        stale = crud.find_missions_awaiting_confirmation_since(db)
        released = 0
        for stale_mission in stale:
            try:
                mission = crud.release_payment(db, stale_mission.mission_id)
            except ValueError:
                # Garde-fou déjà défendu par crud.release_payment (ex: pas
                # d'escrow payé) — ne devrait pas arriver pour une mission
                # trouvée via find_missions_awaiting_confirmation_since, mais
                # une tâche périodique ne doit jamais s'arrêter sur une ligne.
                logger.warning("Auto-libération impossible pour la mission %s", stale_mission.mission_id)
                continue
            released += 1

            user = db.get(BotUser, mission.telegram_id)
            if user is not None:
                send_telegram_message(
                    user.telegram_id,
                    get_message("payment_released_client", user.language, mission_id=mission.mission_id),
                )

            if mission.provider_telegram_id is not None:
                provider = db.get(BotProvider, mission.provider_telegram_id)
                if provider is not None:
                    send_telegram_message(
                        provider.telegram_id,
                        get_message(
                            "payment_released_provider",
                            provider.language,
                            mission_id=mission.mission_id,
                            net=f"{mission.net_provider:.2f}",
                            currency=mission.currency,
                        ),
                    )
        return released
    finally:
        db.close()


@celery_app.task(name="backend.app.tasks.send_provider_reminders")
def send_provider_reminders() -> int:
    """Relance les prestataires matchés si une mission reste `pending` (sans
    devis) après 10 min, puis après 20 min.

    Version simplifiée : re-notifie les mêmes prestataires que la diffusion
    initiale (`find_matching_providers`), sans suivi individuel par
    prestataire ni réattribution séquentielle — voir V5_MIGRATION_PLAN.md
    Phase 2 pour le choix de scope.
    """
    db = SessionLocal()
    try:
        tiers = crud.find_missions_needing_reminder(db)
        sent = 0
        for missions, message_key in (
            (tiers["first"], "mission_reminder_10min_provider"),
            (tiers["second"], "mission_reminder_20min_provider"),
        ):
            for mission in missions:
                providers = crud.find_matching_providers(db, mission.service, mission.commune)
                for provider in providers:
                    send_telegram_message(
                        provider.telegram_id,
                        get_message(
                            message_key,
                            provider.language,
                            mission_id=mission.mission_id,
                            service=mission.service,
                            commune=mission.commune,
                        ),
                    )
                    sent += 1
        return sent
    finally:
        db.close()


@celery_app.task(name="backend.app.tasks.send_daily_analytics")
def send_daily_analytics() -> bool:
    """Rapport quotidien à `ADMIN_TELEGRAM_ID` : missions créées/terminées,
    volume et commission des dernières 24h, groupés par devise.

    Agrégé depuis `BotMission` (qui porte déjà `total_client`/
    `commission_amount` par mission) plutôt que `BotTransaction`, qui n'a pas
    de timestamp — évite une migration supplémentaire pour ce seul rapport.
    """
    if not ADMIN_TELEGRAM_ID:
        logger.warning("ADMIN_TELEGRAM_ID manquant : analytics quotidiennes non envoyées")
        return False

    db = SessionLocal()
    try:
        since = datetime.utcnow() - timedelta(hours=24)
        missions_created = (
            db.query(BotMission).filter(BotMission.created_at >= since).count()
        )
        completed_today = (
            db.query(BotMission)
            .filter(BotMission.status == "completed", BotMission.status_changed_at >= since)
            .all()
        )

        totals_by_currency: dict[str, dict[str, float]] = {}
        for mission in completed_today:
            totals = totals_by_currency.setdefault(mission.currency, {"volume": 0.0, "commission": 0.0})
            totals["volume"] += mission.total_client
            totals["commission"] += mission.commission_amount

        breakdown = "\n".join(
            f"{currency} — Volume : {totals['volume']:.2f} | Commission : {totals['commission']:.2f}"
            for currency, totals in totals_by_currency.items()
        ) or "Aucune mission terminée."

        send_telegram_message(
            int(ADMIN_TELEGRAM_ID),
            get_message(
                "daily_analytics_admin_report",
                "fr",
                date=datetime.utcnow().strftime("%Y-%m-%d"),
                missions_created=missions_created,
                missions_completed=len(completed_today),
                breakdown=breakdown,
            ),
        )
        return True
    finally:
        db.close()
