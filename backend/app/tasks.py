import logging
import os
from datetime import datetime, timedelta

from backend.app import crud, ledger, mobile_money
from backend.app.celery_app import celery_app
from backend.app.database import SessionLocal
from backend.app.models import BotMission, BotProvider, BotUser, NexisAccount, PaymentIntent, Payout
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

    Passe par `ledger.auto_release`, qui revérifie tout sous verrou : une
    mission passée en litige entre la recherche et la libération n'est pas
    payée (ses fonds sont gelés).
    """
    db = SessionLocal()
    try:
        stale = crud.find_missions_awaiting_confirmation_since(db)
        released = 0
        for stale_mission in stale:
            try:
                mission = ledger.auto_release(db, stale_mission.mission_id)
            except ledger.MoneyError as error:
                # Litige ouvert, déjà réglée ou pas payée entre-temps : refus
                # attendu. Une tâche périodique ne s'arrête jamais sur une ligne.
                db.rollback()
                logger.warning("Auto-libération refusée pour la mission %s : %s", stale_mission.mission_id, error.code)
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


# --- Mobile Money réel (CONCEPTION_MOBILE_MONEY.md) --------------------------------
# Une confirmation de l'agrégateur arrive par webhook ou par la vérification
# de secours ci-dessous. Seul celui qui fait changer le statut prévient les
# personnes concernées : jamais deux notifications pour un même paiement.


def _language(db, telegram_id: int) -> str:
    account_id = ledger.account_id_for(db, ledger.TELEGRAM, telegram_id)
    account = db.get(NexisAccount, account_id) if account_id else None
    return account.language if account is not None else "fr"


def _alert_admin(text: str) -> None:
    if ADMIN_TELEGRAM_ID:
        send_telegram_message(int(ADMIN_TELEGRAM_ID), text)


def refresh_and_notify_intent(db, intent_id: int) -> str:
    before = db.get(PaymentIntent, intent_id).status
    intent = mobile_money.refresh_intent(db, intent_id)
    if intent.status != before:
        _notify_intent(db, intent)
    return intent.status


def _notify_intent(db, intent: PaymentIntent) -> None:
    request = intent.funding_request
    client_id, provider_id = request["client_telegram_id"], request["provider_telegram_id"]
    client_lang = _language(db, client_id)
    if intent.status == "succeeded":
        funding = ledger.mission_money_state(db, intent.mission_id)["funding"]
        send_telegram_message(
            client_id,
            get_message(
                "payment_mobile_confirmed_client", client_lang,
                mission_id=intent.mission_id, ref=funding["reference"], total=float(funding["total"]), currency=intent.currency,
            ),
        )
        provider_lang = _language(db, provider_id)
        send_telegram_message(
            provider_id,
            get_message(
                "payment_confirmed_provider_notify", provider_lang,
                mission_id=intent.mission_id, brut=float(funding["total"]), commission=float(funding["commission"]),
                net=float(funding["net"]), currency=intent.currency,
            ),
            reply_markup={"inline_keyboard": [[{
                "text": get_message("button_start_mission", provider_lang),
                "callback_data": f"mission_start_{intent.mission_id}",
            }]]},
        )
    elif intent.status in ("failed", "expired"):
        send_telegram_message(client_id, get_message("payment_mobile_failed_client", client_lang, mission_id=intent.mission_id))
    elif intent.status == "overpaid":
        send_telegram_message(
            client_id,
            get_message("payment_overpaid_client", client_lang, mission_id=intent.mission_id, amount=f"{intent.amount:.2f}", currency=intent.currency),
        )
        _alert_admin(f"⚠️ Paiement en trop crédité au wallet : intention {intent.id}, mission NXH-{intent.mission_id:04d}, {intent.amount} {intent.currency}.")
    elif intent.status == "mismatch":
        _alert_admin(f"⚠️ Montant reçu différent : intention {intent.id}, mission NXH-{intent.mission_id:04d} ({intent.failure_reason}). Rien n'a été payé.")


def refresh_and_notify_payout(db, payout_id: int) -> str:
    before = db.get(Payout, payout_id).status
    payout = mobile_money.refresh_payout(db, payout_id)
    if payout.status != before:
        notify_payout(db, payout)
    return payout.status


def notify_payout(db, payout: Payout) -> None:
    lang = _language(db, payout.requested_by_telegram_id)
    if payout.status == "succeeded":
        key = "payout_succeeded"
    elif payout.status in ("failed", "rejected"):
        key = "payout_returned"
    else:
        return
    send_telegram_message(
        payout.requested_by_telegram_id,
        get_message(key, lang, amount=f"{payout.amount - payout.fee:.2f}", gross=f"{payout.amount:.2f}", currency=payout.currency),
    )


@celery_app.task(name="backend.app.tasks.check_pending_mobile_money")
def check_pending_mobile_money() -> int:
    """Vérification de secours : relit chez l'agrégateur les paiements et
    retraits en attente (webhook perdu, retard). Les intentions expirées sont
    relues 24 h de plus : un paiement confirmé en retard n'est jamais ignoré."""
    db = SessionLocal()
    try:
        now = mobile_money._utcnow()
        intents = (
            db.query(PaymentIntent.id)
            .filter(
                (PaymentIntent.status == "pending")
                | ((PaymentIntent.status == "expired") & (PaymentIntent.expires_at > now - timedelta(hours=24)))
            )
            .all()
        )
        payouts = db.query(Payout.id).filter(Payout.status == "processing").all()
        for (intent_id,) in intents:
            refresh_and_notify_intent(db, intent_id)
        for (payout_id,) in payouts:
            refresh_and_notify_payout(db, payout_id)
        return len(intents) + len(payouts)
    finally:
        db.close()
