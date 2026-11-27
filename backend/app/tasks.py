"""Tâches périodiques du backend. Le calendrier et le verrou qui empêche
deux exécutions simultanées sont dans `taches.py`."""

import logging
from datetime import datetime, timedelta

from backend.app import app_auth, app_sessions, crud, evenements, idempotency, ledger, mobile_money, notifications, reconciliation
from backend.app.database import SessionLocal
from backend.app.models import BotMission, Payout


logger = logging.getLogger(__name__)


def check_expired_quotes() -> int:
    """Devis `pending` depuis plus de 24h → `expired` (crud.expire_stale_quotes)."""
    db = SessionLocal()
    try:
        expired = crud.expire_stale_quotes(db)
        return len(expired)
    finally:
        db.close()


def release_auto_confirmed_missions() -> int:
    """Auto-libère l'escrow des missions en `awaiting_confirmation` dont
    l'échéance `release_after` (48 h après la fin) est passée.

    Passe par `ledger.auto_release`, qui revérifie tout sous verrou : une
    mission passée en litige entre la recherche et la libération n'est pas
    payée (ses fonds sont gelés). Le client et le prestataire sont prévenus
    par des notifications écrites avec la libération.
    """
    db = SessionLocal()
    try:
        stale = crud.find_missions_due_for_auto_release(db)
        released = 0
        for stale_mission in stale:
            try:
                ledger.auto_release(db, stale_mission.mission_id)
            except ledger.MoneyError as error:
                # Litige ouvert, déjà réglée ou pas payée entre-temps : refus
                # attendu. Une tâche périodique ne s'arrête jamais sur une ligne.
                db.rollback()
                logger.warning("Auto-libération refusée pour la mission %s : %s", stale_mission.mission_id, error.code)
                continue
            released += 1
        return released
    finally:
        db.close()


# Relance d'un litige toujours sans décision : une alerte au dépassement du
# délai de réponse de 48 h, puis une par jour tant que personne n'a tranché.
OVERDUE_DISPUTE_REALERT = timedelta(hours=24)


def alert_overdue_disputes(now: datetime | None = None) -> int:
    """Prévient l'admin des litiges sans décision après le délai de réponse.

    Ne déplace jamais d'argent : un litige en retard reste gelé jusqu'à une
    décision humaine. L'alerte est écrite dans la même transaction que
    l'heure de relance (`dispute_overdue_alerted_at`) : elle ne peut ni se
    perdre ni partir deux fois. Sans admin enregistré, rien n'est noté et une
    erreur est journalisée à chaque passage.
    """
    now = now or ledger._utcnow()
    db = SessionLocal()
    try:
        overdue = crud.find_overdue_disputes(db, now, OVERDUE_DISPUTE_REALERT)
        if not overdue:
            return 0
        if not notifications.admin_account_ids(db):
            logger.error("%s litige(s) en retard, mais aucun admin n'est enregistré (python -m backend.app.admins)", len(overdue))
            return 0
        alerted = 0
        for mission in overdue:
            contested = any(decision.contested_at is not None for decision in ledger.dispute_decisions(db, mission.mission_id))
            evenements.dispute_overdue(db, mission, now, contested)
            mission.dispute_overdue_alerted_at = now
            db.commit()
            alerted += 1
        return alerted
    finally:
        db.close()


def execute_due_dispute_decisions(now: datetime | None = None) -> int:
    """Exécute les décisions de litige non contestées dont le délai de
    contestation de 3 jours est passé ; le client et le prestataire sont
    prévenus dans la même transaction.

    Passe par `ledger.execute_dispute_decision`, qui revérifie tout sous le
    verrou de la mission : une contestation enregistrée entre la recherche et
    l'exécution gagne, et une décision n'est jamais exécutée deux fois."""
    now = now or ledger._utcnow()
    db = SessionLocal()
    try:
        executed = 0
        for due in crud.find_dispute_decisions_due(db, now):
            decision_id = due.id
            try:
                ledger.execute_dispute_decision(db, decision_id, now=now)
            except ledger.MoneyError as error:
                db.rollback()
                logger.warning("Décision de litige %s non exécutée : %s", decision_id, error.code)
                continue
            executed += 1
        return executed
    finally:
        db.close()


def expire_settlement_offers(now: datetime | None = None) -> int:
    """Note expirées les propositions d'accord amiable restées sans réponse
    48 h ; le client est prévenu une fois, dans la même transaction. Ne
    déplace jamais d'argent : le litige continue, l'argent reste bloqué."""
    now = now or ledger._utcnow()
    db = SessionLocal()
    try:
        expired = 0
        for due in crud.find_settlement_offers_expired(db, now):
            if ledger.expire_dispute_settlement(db, due.id, now=now):
                expired += 1
        return expired
    finally:
        db.close()


def send_provider_reminders() -> int:
    """Relance les prestataires prévenus d'une mission restée `pending` (sans
    devis) après 10 min, puis après 20 min (`crud.find_missions_needing_reminder`
    écrit les relances avec le palier). Rend le nombre de missions relancées."""
    db = SessionLocal()
    try:
        tiers = crud.find_missions_needing_reminder(db)
        return len(tiers["first"]) + len(tiers["second"])
    finally:
        db.close()


def send_daily_analytics(now: datetime | None = None) -> bool:
    """Rapport quotidien aux admins : missions créées/terminées,
    volume et commission des dernières 24h, groupés par devise.

    Agrégé depuis `BotMission` (qui porte déjà `total_client`/
    `commission_amount` par mission) plutôt que `BotTransaction`, qui n'a pas
    de timestamp — évite une migration supplémentaire pour ce seul rapport.
    """
    now = now or datetime.utcnow()
    db = SessionLocal()
    try:
        if not notifications.admin_account_ids(db):
            logger.warning("Aucun admin enregistré : analytics quotidiennes non envoyées")
            return False
        since = now - timedelta(hours=24)
        missions_created = db.query(BotMission).filter(BotMission.created_at >= since).count()
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

        date = now.strftime("%Y-%m-%d")
        notifications.enqueue_admins(
            db,
            event_key=f"admin_daily_analytics:{date}",
            message_key="daily_analytics_admin_report",
            params={
                "date": date,
                "missions_created": missions_created,
                "missions_completed": len(completed_today),
                "breakdown": breakdown,
            },
        )
        db.commit()
        return True
    finally:
        db.close()


# --- Mobile Money réel (CONCEPTION_MOBILE_MONEY.md) --------------------------------
# Une confirmation de l'agrégateur arrive par webhook ou par la vérification
# de secours ci-dessous. `mobile_money` écrit les notifications avec le
# changement de statut : jamais deux pour un même paiement.


def check_pending_mobile_money() -> int:
    """Vérification de secours : relit chez l'agrégateur les paiements
    (`mobile_money.intents_to_refresh`) et retraits en attente (webhook perdu,
    retard)."""
    db = SessionLocal()
    try:
        intent_ids = mobile_money.intents_to_refresh(db, mobile_money._utcnow())
        payout_ids = [payout_id for (payout_id,) in db.query(Payout.id).filter(Payout.status == "processing")]
        for intent_id in intent_ids:
            mobile_money.refresh_intent(db, intent_id)
        for payout_id in payout_ids:
            mobile_money.refresh_payout(db, payout_id)
        return len(intent_ids) + len(payout_ids)
    finally:
        db.close()


def send_daily_reconciliation(now: datetime | None = None) -> bool:
    """Rapprochement interne quotidien (backend/app/reconciliation.py), envoyé
    à l'admin même sans écart : un rapport qui n'arrive pas se remarque."""
    db = SessionLocal()
    try:
        report = reconciliation.reconcile(db)
        if not report.ok:
            logger.warning("Rapprochement : %d écart(s) : %s", len(report.anomalies), report.anomalies)
        notifications.enqueue_admins(
            db,
            event_key=f"admin_reconciliation:{(now or report.generated_at):%Y%m%d}",
            # Texte brut : échappé à l'envoi (un motif peut contenir « < »).
            params={"text": reconciliation.format_admin_report(report)},
        )
        db.commit()
        return report.ok
    finally:
        db.close()


# --- Notifications (backend/app/notifications.py) --------------------------------


def send_notifications() -> dict:
    """Envoie les notifications dues (et reprend les envois interrompus).
    Tourne chaque minute ; le backend envoie aussi juste après chaque demande
    qui en a créé."""
    report = notifications.send_due()
    return report.__dict__


def purge_request_nonces() -> int:
    """Efface les nonces des demandes signées de plus de 24 heures."""
    db = SessionLocal()
    try:
        return app_sessions.purge_request_nonces(db)
    finally:
        db.close()


def purge_login_failures() -> int:
    """Efface les codes de connexion faux de plus d'une heure (le blocage
    d'un numéro n'en lit que 25 minutes)."""
    db = SessionLocal()
    try:
        return app_auth.purge_login_failures(db)
    finally:
        db.close()


def purge_idempotency_keys() -> int:
    """Efface les clés d'idempotence de plus de 30 jours (idempotency.RETENTION)."""
    db = SessionLocal()
    try:
        return idempotency.purge(db)
    finally:
        db.close()
