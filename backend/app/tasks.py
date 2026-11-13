"""Tâches périodiques du backend. Le calendrier et le verrou qui empêche
deux exécutions simultanées sont dans `taches.py`."""

import html
import logging
import os
from datetime import datetime, timedelta

from backend.app import app_sessions, crud, idempotency, ledger, mobile_money, profils, reconciliation
from backend.app.database import SessionLocal
from backend.app.models import BotMission, Device, NexisAccount, PaymentIntent, Payout
from backend.app.notify import send_telegram_message
from backend.app.presence import provider_arrival_keyboard
from messages import get_message

ADMIN_TELEGRAM_ID = os.getenv("ADMIN_TELEGRAM_ID")

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
    payée (ses fonds sont gelés).
    """
    db = SessionLocal()
    try:
        stale = crud.find_missions_due_for_auto_release(db)
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

            client_account_id = mission.client_account_id or ledger.account_id_for(db, ledger.TELEGRAM, mission.telegram_id)
            if profils.client_profile(db, client_account_id) is not None:
                send_telegram_message(
                    mission.telegram_id,
                    get_message(
                        "payment_released_client", profils.language_of(db, client_account_id), mission_id=mission.mission_id
                    ),
                )

            if mission.provider_telegram_id is not None:
                provider_account_id = mission.provider_account_id or ledger.account_id_for(
                    db, ledger.TELEGRAM, mission.provider_telegram_id
                )
                if profils.provider_profile(db, provider_account_id) is not None:
                    send_telegram_message(
                        mission.provider_telegram_id,
                        get_message(
                            "payment_released_provider",
                            profils.language_of(db, provider_account_id),
                            mission_id=mission.mission_id,
                            net=f"{mission.net_provider:.2f}",
                            currency=mission.currency,
                        ),
                    )
        return released
    finally:
        db.close()


# Relance d'un litige toujours sans décision : une alerte au dépassement du
# délai de réponse de 48 h, puis une par jour tant que personne n'a tranché.
OVERDUE_DISPUTE_REALERT = timedelta(hours=24)


def alert_overdue_disputes(now: datetime | None = None) -> int:
    """Prévient l'admin des litiges sans décision après le délai de réponse.

    Ne déplace jamais d'argent : un litige en retard reste gelé jusqu'à une
    décision humaine. L'alerte n'est notée envoyée que si Telegram l'a
    acceptée, sinon la tâche suivante réessaie. Sans admin configuré, rien
    n'est noté et une erreur est journalisée à chaque passage.
    """
    now = now or ledger._utcnow()
    db = SessionLocal()
    try:
        overdue = crud.find_overdue_disputes(db, now, OVERDUE_DISPUTE_REALERT)
        if not overdue:
            return 0
        if not ADMIN_TELEGRAM_ID:
            logger.error("%s litige(s) en retard, mais ADMIN_TELEGRAM_ID n'est pas configuré", len(overdue))
            return 0
        alerted = 0
        for mission in overdue:
            late_hours = int((now - mission.dispute_deadline).total_seconds() // 3600)
            contested = any(decision.contested_at is not None for decision in ledger.dispute_decisions(db, mission.mission_id))
            if contested:
                text = (
                    f"⏰ Décision contestée sans révision : mission NXH-{mission.mission_id:04d}. Le délai de réponse "
                    f"(échéance {mission.dispute_deadline:%d/%m %H:%M} UTC) est dépassé de {late_hours} h. "
                    "La révision doit venir d'une autre personne de Nexis Hub que celle de la première décision. "
                    "L'argent reste bloqué jusque-là."
                )
            else:
                text = (
                    f"⏰ Litige sans décision : mission NXH-{mission.mission_id:04d}. Le délai de réponse "
                    f"(échéance {mission.dispute_deadline:%d/%m %H:%M} UTC) est dépassé de {late_hours} h. "
                    "L'argent reste bloqué tant que personne n'a tranché."
                )
            if send_telegram_message(int(ADMIN_TELEGRAM_ID), text):
                mission.dispute_overdue_alerted_at = now
                db.commit()
                alerted += 1
        return alerted
    finally:
        db.close()


def execute_due_dispute_decisions(now: datetime | None = None) -> int:
    """Exécute les décisions de litige non contestées dont le délai de
    contestation de 3 jours est passé, puis prévient le client et le
    prestataire.

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
                mission = ledger.execute_dispute_decision(db, decision_id, now=now)
            except ledger.MoneyError as error:
                db.rollback()
                logger.warning("Décision de litige %s non exécutée : %s", decision_id, error.code)
                continue
            executed += 1
            notify_dispute_settled(db, mission)
        return executed
    finally:
        db.close()


# Heure montrée au client et au prestataire : Kinshasa (UTC+1, sans heure
# d'été). Les colonnes sont en UTC naïf.
KINSHASA_OFFSET = timedelta(hours=1)


def _kinshasa_time(value: datetime) -> str:
    return f"{value + KINSHASA_OFFSET:%d/%m/%Y %H:%M}"


def _amount_text(amount, currency: str) -> tuple[str, str]:
    """Montant et devise tels qu'affichés : USD avec 2 décimales, francs
    congolais sans décimales (règle de la charte, 2026-11-07)."""
    if currency == "CDF":
        return f"{amount:,.0f}".replace(",", " "), "FC"
    return f"{amount:.2f}", currency


def _party_language(db, mission: BotMission, role: str) -> str | None:
    """Langue du client ou du prestataire de la mission (celle de son compte
    Nexis). None si la mission n'a personne dans ce rôle (rien à envoyer)."""
    telegram_id = _party_telegram_id(mission, role)
    if telegram_id is None:
        return None
    return _language(db, telegram_id)


def _party_telegram_id(mission: BotMission, role: str) -> int | None:
    return mission.telegram_id if role == "client" else mission.provider_telegram_id


def notify_dispute_decided(db, mission: BotMission) -> None:
    """Première décision enregistrée : le client et le prestataire reçoivent
    les montants prévus, la date d'exécution et un bouton pour contester."""
    decision = next(row for row in ledger.dispute_decisions(db, mission.mission_id) if row.round == ledger.FIRST_DECISION)
    for role, mine, theirs in (
        ("client", decision.client_amount, decision.provider_amount),
        ("provider", decision.provider_amount, decision.client_amount),
    ):
        lang = _party_language(db, mission, role)
        if lang is None:
            continue
        mine_text, currency = _amount_text(mine, decision.currency)
        theirs_text, _ = _amount_text(theirs, decision.currency)
        text = get_message(
            f"dispute_decision_{role}",
            lang,
            mission_id=mission.mission_id,
            mine=mine_text,
            theirs=theirs_text,
            currency=currency,
            deadline=_kinshasa_time(decision.execute_after),
        )
        keyboard = {
            "inline_keyboard": [
                [
                    {
                        "text": get_message("button_contest_decision", lang),
                        # c / p : la langue à utiliser ensuite (client ou prestataire).
                        "callback_data": f"dispute_contest_{role[0]}_{mission.mission_id}",
                    }
                ]
            ]
        }
        send_telegram_message(_party_telegram_id(mission, role), text, keyboard)


def notify_dispute_contested(db, mission: BotMission) -> None:
    """Décision contestée : l'autre partie est prévenue que l'argent reste
    bloqué, et l'admin qu'une autre personne doit revoir le litige."""
    decision = next(row for row in ledger.dispute_decisions(db, mission.mission_id) if row.round == ledger.FIRST_DECISION)
    other = "provider" if decision.contested_by_role == "client" else "client"
    lang = _party_language(db, mission, other)
    if lang is not None:
        send_telegram_message(
            _party_telegram_id(mission, other),
            get_message(f"dispute_contested_notify_{other}", lang, mission_id=mission.mission_id),
        )
    who = "le client" if decision.contested_by_role == "client" else "le prestataire"
    _alert_admin(
        f"⚖️ Décision contestée par {who} : mission NXH-{mission.mission_id:04d}.\n"
        f"Raison : {html.escape(decision.contest_reason or '')}\n"
        f"À revoir avant le {mission.dispute_deadline:%d/%m %H:%M} UTC par une autre personne de Nexis Hub "
        "que celle qui a pris la première décision. L'argent reste bloqué."
    )


def notify_dispute_settled(db, mission: BotMission) -> None:
    """Prévient le client et le prestataire qu'une décision de litige a été
    appliquée, avec les montants du règlement enregistré."""
    settlement = ledger.mission_money_state(db, mission.mission_id)["settlement"] or {}
    decision = settlement.get("decision")
    if decision not in ledger.DISPUTE_DECISIONS:
        return
    mission_id, currency = mission.mission_id, mission.currency
    client_lang = _party_language(db, mission, "client")
    if client_lang is not None:
        client_text = {
            "refund": get_message("dispute_resolved_refund_client", client_lang, mission_id=mission_id),
            "release": get_message("dispute_resolved_release_client", client_lang, mission_id=mission_id),
            "split": get_message(
                "dispute_resolved_split_client",
                client_lang,
                mission_id=mission_id,
                refund=settlement.get("client_amount"),
                currency=currency,
            ),
        }[decision]
        send_telegram_message(mission.telegram_id, client_text)
    provider_lang = _party_language(db, mission, "provider")
    if provider_lang is not None:
        if decision == "refund":
            provider_text = get_message("dispute_resolved_refund_provider", provider_lang, mission_id=mission_id)
        else:
            provider_text = get_message(
                f"dispute_resolved_{decision}_provider",
                provider_lang,
                mission_id=mission_id,
                net=settlement.get("provider_amount"),
                currency=currency,
            )
        send_telegram_message(mission.provider_telegram_id, provider_text)


def send_provider_reminders() -> int:
    """Relance les prestataires matchés si une mission reste `pending` (sans
    devis) après 10 min, puis après 20 min.

    Relance les prestataires prévenus à la création (`mission_alerts`), et
    eux seuls : ce sont les seuls qui peuvent répondre par un devis.
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
                for account_id in crud.alerted_provider_account_ids(db, mission.mission_id):
                    provider_telegram_id = ledger.telegram_id_of(db, account_id)
                    if provider_telegram_id is None:
                        continue
                    send_telegram_message(
                        provider_telegram_id,
                        get_message(
                            message_key,
                            profils.language_of(db, account_id),
                            mission_id=mission.mission_id,
                            service=mission.service,
                            commune=mission.commune,
                        ),
                    )
                    sent += 1
        return sent
    finally:
        db.close()


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
    client_id = ledger.telegram_id_of(db, request["client_account_id"])
    provider_id = ledger.telegram_id_of(db, request["provider_account_id"])
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
        _notify_provider_paid(db, provider_id, intent, funding)
    elif intent.status in ("failed", "expired"):
        send_telegram_message(client_id, get_message("payment_mobile_failed_client", client_lang, mission_id=intent.mission_id))
    elif intent.status == "overpaid":
        send_telegram_message(
            client_id,
            get_message("payment_overpaid_client", client_lang, mission_id=intent.mission_id, amount=f"{intent.amount:.2f}", currency=intent.currency),
        )
        _alert_admin(f"⚠️ Paiement en trop crédité au wallet : intention {intent.id}, mission NXH-{intent.mission_id:04d}, {intent.amount} {intent.currency}.")
    elif intent.status == "mismatch":
        send_telegram_message(client_id, get_message("payment_mismatch_client", client_lang, mission_id=intent.mission_id))
        _alert_admin(
            f"⚠️ Montant reçu différent : intention {intent.id}, mission NXH-{intent.mission_id:04d} ({intent.failure_reason}). "
            "Rien n'a été payé. À régler dans /admin → Montants différents."
        )


def _notify_provider_paid(db, provider_id: int, intent: PaymentIntent, funding: dict) -> None:
    provider_lang = _language(db, provider_id)
    send_telegram_message(
        provider_id,
        get_message(
            "payment_confirmed_provider_notify", provider_lang,
            mission_id=intent.mission_id, brut=float(funding["total"]), commission=float(funding["commission"]),
            net=float(funding["net"]), currency=intent.currency,
        ),
        # « Je suis arrivé », code du client, lieu exact (lu dans le backend à
        # l'appui, avec ses règles d'accès : jamais dans la notification).
        reply_markup=provider_arrival_keyboard(intent.mission_id, provider_lang),
    )


def notify_mismatch_resolved(db, intent: PaymentIntent) -> None:
    """Décision de l'admin sur un montant reçu différent : le client sait où
    est son argent ; si la mission est payée, le prestataire peut commencer."""
    request = intent.funding_request
    client_id = ledger.telegram_id_of(db, request["client_account_id"])
    client_lang = _language(db, client_id)
    received = dict(mission_id=intent.mission_id, amount=f"{intent.received_amount:.2f}", currency=intent.received_currency)
    if intent.status == "mismatch_credited":
        send_telegram_message(client_id, get_message("payment_mismatch_credited_client", client_lang, **received))
    elif intent.status == "mismatch_paid":
        send_telegram_message(client_id, get_message("payment_mismatch_paid_client", client_lang, **received))
        funding = ledger.mission_money_state(db, intent.mission_id)["funding"]
        _notify_provider_paid(db, ledger.telegram_id_of(db, request["provider_account_id"]), intent, funding)


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


def check_pending_mobile_money() -> int:
    """Vérification de secours : relit chez l'agrégateur les paiements
    (`mobile_money.intents_to_refresh`) et retraits en attente (webhook perdu,
    retard)."""
    db = SessionLocal()
    try:
        intent_ids = mobile_money.intents_to_refresh(db, mobile_money._utcnow())
        payout_ids = [payout_id for (payout_id,) in db.query(Payout.id).filter(Payout.status == "processing")]
        for intent_id in intent_ids:
            refresh_and_notify_intent(db, intent_id)
        for payout_id in payout_ids:
            refresh_and_notify_payout(db, payout_id)
        return len(intent_ids) + len(payout_ids)
    finally:
        db.close()


def send_daily_reconciliation() -> bool:
    """Rapprochement interne quotidien (backend/app/reconciliation.py), envoyé
    à l'admin même sans écart : un rapport qui n'arrive pas se remarque."""
    db = SessionLocal()
    try:
        report = reconciliation.reconcile(db)
        if not report.ok:
            logger.warning("Rapprochement : %d écart(s) : %s", len(report.anomalies), report.anomalies)
        _alert_admin(reconciliation.format_admin_report(report))
        return report.ok
    finally:
        db.close()


# --- Application mobile (étape 1, PR 4) -------------------------------------------

# Heure de Kinshasa (UTC+1, sans heure d'été), pour les messages.
KINSHASA_OFFSET = timedelta(hours=1)
NEW_DEVICE_ALERT_RETRIES = 12


def send_new_device_alert(db, device_id: int) -> bool:
    """Prévient la personne, sur Telegram, qu'un téléphone vient d'être
    ajouté à son compte, avec le bouton « Ce n'est pas moi ». Rend False
    seulement si l'envoi a échoué (la tâche réessaie) ; True si c'est envoyé
    ou s'il n'y a rien à envoyer (premier téléphone d'un compte tout neuf,
    téléphone déjà coupé, compte sans Telegram)."""
    device = db.get(Device, device_id)
    if device is None or not app_sessions.needs_new_device_alert(device):
        return True
    telegram_id = ledger.telegram_id_of(db, device.account_id)
    if telegram_id is None:
        # Compte sans Telegram : l'alerte passera par WhatsApp (PR 6) et par
        # les notifications de l'app (étape 2). Le délai de 72 h protège
        # l'argent en attendant.
        logger.warning("Nouvel appareil %s : compte sans Telegram, alerte non envoyée", device_id)
        return True
    account = db.get(NexisAccount, device.account_id)
    lang = account.language if account is not None else "fr"
    local = device.created_at + KINSHASA_OFFSET
    text = get_message(
        "app_new_device_alert",
        lang,
        device=device.label or get_message("app_device_unnamed", lang),
        date=local.strftime("%d/%m/%Y"),
        time=local.strftime("%H:%M"),
    )
    keyboard = {"inline_keyboard": [[{"text": get_message("button_app_not_me", lang), "callback_data": f"app_not_me_{device.id}"}]]}
    return send_telegram_message(telegram_id, text, reply_markup=keyboard)


def _next_device_alert_delay(attempts: int) -> timedelta:
    """1 min, 2 min, 4 min… plafonné à 1 h entre deux essais."""
    return timedelta(seconds=min(60 * 2 ** (attempts - 1), 3600))


def send_pending_device_alerts(now: datetime | None = None) -> int:
    """Envoie les alertes « Nouvel appareil » dues (boîte d'envoi sur
    `Device.alert_due_at`, posée à la connexion dans la même transaction que
    le téléphone). Un échec repousse l'essai suivant ; après
    `NEW_DEVICE_ALERT_RETRIES` échecs, l'admin est prévenu et on s'arrête.
    Chaque téléphone est traité sous verrou de ligne et validé à part :
    une ligne en échec n'arrête pas les autres. Rend le nombre d'alertes
    envoyées."""
    now = now or datetime.utcnow()
    db = SessionLocal()
    try:
        due_ids = [
            device_id
            for (device_id,) in db.query(Device.id)
            .filter(Device.alert_due_at.is_not(None), Device.alert_due_at <= now)
            .order_by(Device.alert_due_at)
        ]
        sent = 0
        for device_id in due_ids:
            device = (
                db.query(Device)
                .filter(Device.id == device_id, Device.alert_due_at.is_not(None), Device.alert_due_at <= now)
                .with_for_update(skip_locked=True)
                .one_or_none()
            )
            if device is None:
                db.rollback()
                continue
            try:
                delivered = send_new_device_alert(db, device.id)
                reached = (
                    app_sessions.needs_new_device_alert(device)
                    and ledger.telegram_id_of(db, device.account_id) is not None
                )
            except Exception:
                # Erreur inattendue (base, réseau) : on repart d'une transaction
                # propre et l'essai compte comme un échec.
                logger.exception("Alerte « Nouvel appareil » : erreur pour le téléphone %s", device_id)
                db.rollback()
                device = db.query(Device).filter(Device.id == device_id).with_for_update().one()
                delivered = reached = False
            if delivered:
                device.alert_due_at = None
                if reached:
                    device.alert_sent_at = now
                    sent += 1
            else:
                device.alert_attempts += 1
                if device.alert_attempts >= NEW_DEVICE_ALERT_RETRIES:
                    device.alert_due_at = None
                    logger.error("Alerte « Nouvel appareil » abandonnée pour le téléphone %s", device.id)
                    _alert_admin(
                        f"⚠️ Alerte « Nouvel appareil » non envoyée après {device.alert_attempts} essais : "
                        f"téléphone {device.id} du compte {device.account_id}. Le délai de 72 h protège l'argent ; "
                        "préviens la personne autrement."
                    )
                else:
                    device.alert_due_at = now + _next_device_alert_delay(device.alert_attempts)
            db.commit()
        return sent
    finally:
        db.close()


def alert_admin_not_me(device_id: int, account_id: int) -> None:
    """« Ce n'est pas moi » : l'admin est prévenu (compte peut-être visé)."""
    _alert_admin(
        f"🚨 « Ce n'est pas moi » : téléphone {device_id} du compte {account_id} coupé par la personne. "
        "Vérifie le compte (connexions récentes, retraits)."
    )


def purge_request_nonces() -> int:
    """Efface les nonces des demandes signées de plus de 24 heures."""
    db = SessionLocal()
    try:
        return app_sessions.purge_request_nonces(db)
    finally:
        db.close()


def purge_idempotency_keys() -> int:
    """Efface les clés d'idempotence de plus de 30 jours (idempotency.RETENTION)."""
    db = SessionLocal()
    try:
        return idempotency.purge(db)
    finally:
        db.close()
