"""Qui est prévenu de quoi : les notifications de chaque événement métier.

Chaque fonction ajoute les notifications d'un événement à la transaction en
cours (`notifications.enqueue`), **sans valider** : elle est appelée juste
avant la validation de l'événement, par le code qui le décide (crud, ledger,
mobile_money, presence, taches). Un événement annulé n'envoie donc rien, un
événement validé ne perd jamais son message, et un événement rejoué n'en crée
pas un second (clé d'événement unique par destinataire).

Les destinataires sont toujours des comptes Nexis ; le canal (Telegram ou
WhatsApp) est celui de chaque destinataire. Les textes nomment la mission et
l'état, jamais une instruction à exécuter : un message reçu deux fois ne
trompe personne. Aucun montant n'est recalculé ici : ils sont lus dans le
registre (`ledger.mission_money_state`) ou sur l'opération enregistrée.
"""

from __future__ import annotations

import html
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from backend.app import ledger, profils
from backend.app.models import (
    BotMission,
    BotQuote,
    ClientServiceRequest,
    DisputeSettlementOffer,
    MissionMedia,
    PaymentIntent,
    Payout,
    PayoutDestination,
    ProviderProfile,
    ProviderServiceAddition,
    StoredFile,
    ProviderServiceRequest,
)
from backend.app.notifications import admin_text, enqueue, enqueue_admins, withdraw

# Heure montrée aux personnes : Kinshasa (UTC+1, sans heure d'été). Les
# colonnes sont en UTC naïf.
KINSHASA_OFFSET = timedelta(hours=1)


def kinshasa_time(value: datetime) -> str:
    return f"{value + KINSHASA_OFFSET:%d/%m/%Y %H:%M}"


def amount_text(amount, currency: str) -> tuple[str, str]:
    """Montant et devise tels qu'affichés : USD avec 2 décimales, francs
    congolais sans décimales (règle de la charte, 2026-11-07)."""
    if currency == "CDF":
        return f"{Decimal(str(amount)):,.0f}".replace(",", " "), "FC"
    return f"{Decimal(str(amount)):.2f}", currency


def _ref(mission_id: int) -> str:
    return f"NXH-{mission_id:04d}"


def _button(label: str, action: str) -> dict:
    return {"label": label, "action": action}


# --- Boutons (identifiants compris par le bot Telegram, et plus tard par le
# service WhatsApp) --------------------------------------------------------------


def mission_alert_buttons(mission_id: int) -> list:
    return [[_button("button_alert_accept", f"provider_accept_{mission_id}"), _button("button_alert_skip", f"provider_skip_{mission_id}")]]


def quote_buttons(quote_id: int) -> list:
    return [[_button("button_quote_accept", f"quote_accept_{quote_id}")], [_button("button_quote_reject", f"quote_reject_{quote_id}")]]


def completion_buttons(mission_id: int) -> list:
    return [
        [_button("button_confirm_completion", f"client_confirm_done_{mission_id}")],
        [_button("button_report_issue", f"client_report_issue_{mission_id}")],
    ]


def provider_arrival_buttons(mission_id: int) -> list:
    """Prestataire d'une mission payée qui n'a pas encore commencé."""
    return [
        [_button("button_arrived", f"presence_arrived_{mission_id}")],
        [_button("button_presence_enter_code", f"presence_code_{mission_id}")],
        [_button("button_view_place", f"mission_place_{mission_id}")],
    ]


def provider_finish_buttons(mission_id: int) -> list:
    return [
        [_button("button_finish_mission", f"mission_finish_{mission_id}")],
        [_button("button_view_place", f"mission_place_{mission_id}")],
    ]


def presence_question_buttons(mission_id: int) -> list:
    return [
        [_button("button_presence_yes", f"presence_yes_{mission_id}")],
        [_button("button_presence_not_yet", f"presence_notyet_{mission_id}")],
        [_button("button_presence_wrong", f"presence_wrong_{mission_id}")],
    ]


# --- Mission et devis --------------------------------------------------------------


def mission_created(db: Session, mission: BotMission, provider_account_ids: list[int]) -> None:
    """Chaque prestataire prévenu reçoit la demande, puis chaque pièce jointe
    (photo, note vocale, note vidéo) dans l'ordre où le client l'a envoyée."""
    media = (
        db.query(MissionMedia)
        .filter(MissionMedia.mission_id == mission.mission_id)
        .order_by(MissionMedia.position)
        .all()
    )
    for account_id in provider_account_ids:
        enqueue(
            db,
            event_key=f"mission_alert:{mission.mission_id}",
            account_id=account_id,
            message_key="new_mission_alert",
            params={
                "mission_id": mission.mission_id,
                "service": {"$service": mission.service},
                "commune": mission.commune,
                "urgent": {"$yes_no": bool(mission.urgent)},
                "description": mission.description or "",
            },
            buttons=mission_alert_buttons(mission.mission_id),
        )
        for item in media:
            caption = {"photo": "mission_photo_caption", "voice": "mission_voice_caption"}.get(item.kind)
            media_ref = {"kind": item.kind, "channel": item.channel, "id": item.external_id}
            enqueue(
                db,
                event_key=f"mission_alert_media:{mission.mission_id}:{item.id}",
                account_id=account_id,
                message_key=caption or "mission_video_note_caption",
                params={"mission_id": mission.mission_id},
                media=media_ref,
            )
            if caption is None:
                # Une note vidéo ne porte pas de légende : le numéro suit.
                enqueue(
                    db,
                    event_key=f"mission_alert_media_caption:{mission.mission_id}:{item.id}",
                    account_id=account_id,
                    message_key="mission_video_note_caption",
                    params={"mission_id": mission.mission_id},
                )


def mission_reminder(db: Session, mission: BotMission, provider_account_ids: list[int], tier: str) -> None:
    """Relance à 10 puis 20 minutes d'une mission restée sans devis, aux
    prestataires prévenus seulement (eux seuls peuvent y répondre)."""
    for account_id in provider_account_ids:
        enqueue(
            db,
            event_key=f"mission_reminder_{tier}:{mission.mission_id}",
            account_id=account_id,
            message_key=f"mission_reminder_{tier}_provider",
            params={"mission_id": mission.mission_id, "service": {"$service": mission.service}, "commune": mission.commune},
        )


def provider_trust(provider: ProviderProfile | None) -> dict:
    """Ce que le client voit pour se fier à un prestataire (note, missions,
    badge, vérification)."""
    if provider is None:
        return {"total_missions": 0}
    return {
        "rating": float(provider.average_rating or 0),
        "total_missions": int(provider.total_missions or 0),
        "success_rate": float(provider.success_rate or 0),
        "badge": provider.badge,
        "is_verified": profils.is_verified(provider),
    }


def quote_created(db: Session, quote: BotQuote) -> None:
    mission = db.get(BotMission, quote.mission_id)
    provider = profils.provider_profile(db, quote.provider_account_id)
    enqueue(
        db,
        event_key=f"quote_received:{quote.id}",
        account_id=mission.client_account_id,
        message_key="new_quote_received_client",
        params={
            "mission_id": mission.mission_id,
            "prestataire": (provider.full_name if provider is not None else None) or "—",
            "trust_line": {"$trust": provider_trust(provider)},
            "amount": float(quote.amount),
            "currency": quote.currency,
            "delay": quote.delay_hours,
            "message": quote.message if quote.message else {"$message": "quote_no_message"},
        },
        buttons=quote_buttons(quote.id),
    )


def quote_accepted(db: Session, quote: BotQuote) -> None:
    enqueue(
        db,
        event_key=f"quote_accepted:{quote.id}",
        account_id=quote.provider_account_id,
        message_key="quote_accept_provider_notify",
        params={"mission_id": quote.mission_id, "amount": float(quote.amount), "currency": quote.currency},
    )


def quote_rejected(db: Session, quote: BotQuote) -> None:
    enqueue(
        db,
        event_key=f"quote_rejected:{quote.id}",
        account_id=quote.provider_account_id,
        message_key="quote_rejected_provider_notify",
        params={"mission_id": quote.mission_id},
    )


# --- Paiement ---------------------------------------------------------------------


def mission_funded(db: Session, mission: BotMission, method: str) -> None:
    """Mission payée en escrow : le prestataire peut y aller (boutons
    d'arrivée et lieu exact, lu dans le backend à l'appui)."""
    funding = ledger.mission_money_state(db, mission.mission_id)["funding"]
    enqueue(
        db,
        event_key=f"mission_funded:{mission.mission_id}",
        account_id=mission.provider_account_id,
        message_key="payment_wallet_confirmed_provider_notify" if method == "wallet" else "payment_confirmed_provider_notify",
        params={
            "mission_id": mission.mission_id,
            "brut": float(funding["total"]),
            "commission": float(funding["commission"]),
            "net": float(funding["net"]),
            "currency": mission.currency,
        },
        buttons=provider_arrival_buttons(mission.mission_id),
    )


def payment_confirmed(db: Session, intent: PaymentIntent, mission: BotMission) -> None:
    """Paiement Mobile Money confirmé par l'agrégateur : le client le sait,
    même s'il a fermé la conversation (sur le wallet, il voit la réponse à
    l'écran). Appelé après l'écriture du paiement, dans sa transaction."""
    funding = ledger.mission_money_state(db, mission.mission_id)["funding"]
    enqueue(
        db,
        event_key=f"payment_confirmed:{intent.id}",
        account_id=mission.client_account_id,
        message_key="payment_mobile_confirmed_client",
        params={
            "mission_id": mission.mission_id,
            "ref": funding["reference"],
            "total": float(funding["total"]),
            "currency": mission.currency,
        },
    )


def payment_intent_closed(db: Session, intent: PaymentIntent) -> None:
    """Paiement Mobile Money sans paiement de mission : échoué ou expiré, en
    trop (crédité au wallet) ou montant différent (l'admin tranche)."""
    client = intent.funding_request.get("client_account_id")
    ref = _ref(intent.mission_id)
    if intent.status in ("failed", "expired"):
        enqueue(
            db,
            event_key=f"payment_failed:{intent.id}",
            account_id=client,
            message_key="payment_mobile_failed_client",
            params={"mission_id": intent.mission_id},
        )
    elif intent.status == "overpaid":
        enqueue(
            db,
            event_key=f"payment_overpaid:{intent.id}",
            account_id=client,
            message_key="payment_overpaid_client",
            params={"mission_id": intent.mission_id, "amount": f"{intent.amount:.2f}", "currency": intent.currency},
        )
        enqueue_admins(
            db,
            event_key=f"admin_payment_overpaid:{intent.id}",
            params=admin_text(
                f"⚠️ Paiement en trop crédité au wallet : intention {intent.id}, mission {ref}, "
                f"{intent.amount} {html.escape(intent.currency)}."
            ),
        )
    elif intent.status == "mismatch":
        enqueue(
            db,
            event_key=f"payment_mismatch:{intent.id}",
            account_id=client,
            message_key="payment_mismatch_client",
            params={"mission_id": intent.mission_id},
        )
        enqueue_admins(
            db,
            event_key=f"admin_payment_mismatch:{intent.id}",
            params=admin_text(
                f"⚠️ Montant reçu différent : intention {intent.id}, mission {ref} "
                f"({html.escape(intent.failure_reason or '')}). Rien n'a été payé. À régler dans /admin → Montants différents."
            ),
        )


def mismatch_resolved(db: Session, intent: PaymentIntent) -> None:
    """Décision de l'admin sur un montant reçu différent : le client sait où
    est son argent (si la mission est payée, le prestataire l'apprend par le
    paiement lui-même, `mission_funded`)."""
    client = intent.funding_request.get("client_account_id")
    received = {"mission_id": intent.mission_id, "amount": f"{intent.received_amount:.2f}", "currency": intent.received_currency}
    if intent.status == "mismatch_credited":
        enqueue(db, event_key=f"mismatch_resolved:{intent.id}", account_id=client, message_key="payment_mismatch_credited_client", params=received)
    elif intent.status == "mismatch_paid":
        enqueue(db, event_key=f"mismatch_resolved:{intent.id}", account_id=client, message_key="payment_mismatch_paid_client", params=received)


def payout_changed(db: Session, payout: Payout) -> None:
    """Retrait validé, envoyé ou rendu au wallet : la personne qui l'a
    demandé est prévenue (une fois par état)."""
    keys = {
        "processing": "payout_processing",
        "succeeded": "payout_succeeded",
        "failed": "payout_returned",
        "rejected": "payout_returned",
    }
    key = keys.get(payout.status)
    if key is None:
        return
    enqueue(
        db,
        event_key=f"payout_{payout.status}:{payout.id}",
        account_id=payout.account_id,
        message_key=key,
        params={"amount": f"{payout.amount - payout.fee:.2f}", "gross": f"{payout.amount:.2f}", "currency": payout.currency},
    )


OPERATOR_NAMES = {"mpesa": "M-Pesa", "airtel": "Airtel Money", "orange": "Orange Money"}


def payout_destination_added(db: Session, destination: PayoutDestination) -> None:
    """Numéro de retrait ajouté : la personne est toujours prévenue. Si ce
    n'est pas elle, elle a le délai de sécurité pour réagir."""
    params = {
        "operateur": OPERATOR_NAMES.get(destination.operator, destination.operator),
        "numero": destination.phone,
    }
    if destination.usable_after is not None:
        params["date"] = kinshasa_time(destination.usable_after)
    enqueue(
        db,
        event_key=f"payout_destination_added:{destination.id}",
        account_id=destination.account_id,
        message_key="payout_destination_added_delayed" if destination.usable_after else "payout_destination_added",
        params=params,
    )


# --- Déroulement de la mission -----------------------------------------------------


def mission_finished(db: Session, mission: BotMission) -> None:
    enqueue(
        db,
        event_key=f"mission_finished:{mission.mission_id}",
        account_id=mission.client_account_id,
        message_key="mission_finished_client",
        params={"mission_id": mission.mission_id},
        buttons=completion_buttons(mission.mission_id),
    )


def mission_released(db: Session, mission: BotMission, *, automatic: bool, details: dict) -> None:
    """Paiement libéré au prestataire, par le client ou automatiquement après
    48 h. Le montant est celui de l'opération enregistrée."""
    if automatic:
        enqueue(
            db,
            event_key=f"mission_released:{mission.mission_id}",
            account_id=mission.client_account_id,
            message_key="payment_released_client",
            params={"mission_id": mission.mission_id},
        )
    enqueue(
        db,
        event_key=f"mission_released:{mission.mission_id}",
        account_id=mission.provider_account_id,
        message_key="payment_released_provider",
        params={"mission_id": mission.mission_id, "net": details["provider_amount"], "currency": mission.currency},
    )


def dispute_opened(db: Session, mission: BotMission) -> None:
    enqueue(
        db,
        event_key=f"dispute_opened:{mission.mission_id}",
        account_id=mission.provider_account_id,
        message_key="dispute_opened_provider_notify",
        params={"mission_id": mission.mission_id},
    )


def _party(mission: BotMission, role: str) -> int | None:
    return mission.client_account_id if role == "client" else mission.provider_account_id


def dispute_decided(db: Session, mission: BotMission, decision) -> None:
    """Première décision : chacun reçoit les montants prévus, la date
    d'exécution et un bouton pour contester."""
    for role, mine, theirs in (
        ("client", decision.client_amount, decision.provider_amount),
        ("provider", decision.provider_amount, decision.client_amount),
    ):
        mine_text, currency = amount_text(mine, decision.currency)
        theirs_text, _ = amount_text(theirs, decision.currency)
        enqueue(
            db,
            event_key=f"dispute_decided:{decision.id}",
            account_id=_party(mission, role),
            message_key=f"dispute_decision_{role}",
            params={
                "mission_id": mission.mission_id,
                "mine": mine_text,
                "theirs": theirs_text,
                "currency": currency,
                "deadline": kinshasa_time(decision.execute_after),
            },
            # c / p : la langue à utiliser ensuite (client ou prestataire).
            buttons=[[_button("button_contest_decision", f"dispute_contest_{role[0]}_{mission.mission_id}")]],
        )


def dispute_contested(db: Session, mission: BotMission, decision) -> None:
    """L'autre partie apprend que l'argent reste bloqué ; l'admin, qu'une
    autre personne doit revoir le litige."""
    other = "provider" if decision.contested_by_role == "client" else "client"
    enqueue(
        db,
        event_key=f"dispute_contested:{decision.id}",
        account_id=_party(mission, other),
        message_key=f"dispute_contested_notify_{other}",
        params={"mission_id": mission.mission_id},
    )
    who = "le client" if decision.contested_by_role == "client" else "le prestataire"
    enqueue_admins(
        db,
        event_key=f"admin_dispute_contested:{decision.id}",
        params=admin_text(
            f"⚖️ Décision contestée par {who} : mission {_ref(mission.mission_id)}.\n"
            f"Raison : {html.escape(decision.contest_reason or '')}\n"
            f"À revoir avant le {mission.dispute_deadline:%d/%m %H:%M} UTC par une autre personne de Nexis Hub "
            "que celle qui a pris la première décision. L'argent reste bloqué."
        ),
    )


def dispute_settled(db: Session, mission: BotMission, decision_id: int, settlement: dict) -> None:
    """Décision de litige appliquée : montants du règlement enregistré."""
    decision = settlement.get("decision")
    if decision not in ledger.DISPUTE_DECISIONS:
        return
    mission_id, currency = mission.mission_id, mission.currency
    client_params = {"mission_id": mission_id}
    if decision == "split":
        client_params.update(refund=settlement.get("client_amount"), currency=currency)
    enqueue(
        db,
        event_key=f"dispute_settled:{decision_id}",
        account_id=mission.client_account_id,
        message_key=f"dispute_resolved_{decision}_client",
        params=client_params,
    )
    provider_params = {"mission_id": mission_id}
    if decision != "refund":
        provider_params.update(net=settlement.get("provider_amount"), currency=currency)
    enqueue(
        db,
        event_key=f"dispute_settled:{decision_id}",
        account_id=mission.provider_account_id,
        message_key=f"dispute_resolved_{decision}_provider",
        params=provider_params,
    )


def dispute_overdue(db: Session, mission: BotMission, now: datetime, contested: bool) -> int:
    """Litige sans décision après le délai de réponse : alerte aux admins,
    une par passage (la tâche ne repasse qu'une fois par jour)."""
    late_hours = int((now - mission.dispute_deadline).total_seconds() // 3600)
    deadline = f"{mission.dispute_deadline:%d/%m %H:%M}"
    if contested:
        text = (
            f"⏰ Décision contestée sans révision : mission {_ref(mission.mission_id)}. Le délai de réponse "
            f"(échéance {deadline} UTC) est dépassé de {late_hours} h. "
            "La révision doit venir d'une autre personne de Nexis Hub que celle de la première décision. "
            "L'argent reste bloqué jusque-là."
        )
    else:
        text = (
            f"⏰ Litige sans décision : mission {_ref(mission.mission_id)}. Le délai de réponse "
            f"(échéance {deadline} UTC) est dépassé de {late_hours} h. "
            "L'argent reste bloqué tant que personne n'a tranché."
        )
    return enqueue_admins(db, event_key=f"admin_dispute_overdue:{mission.mission_id}:{now:%Y%m%d%H%M}", params=admin_text(text))


def _offer_amounts(offer: DisputeSettlementOffer, role: str) -> dict:
    mine = offer.client_amount if role == "client" else offer.provider_amount
    theirs = offer.provider_amount if role == "client" else offer.client_amount
    if mine is None:
        return {}
    mine_text, currency = amount_text(mine, offer.currency)
    theirs_text, _ = amount_text(theirs, offer.currency)
    return {"mine": mine_text, "theirs": theirs_text, "currency": currency}


def offer_percentage(offer: DisputeSettlementOffer) -> str:
    if offer.provider_percentage is None:
        return ""
    return f"{offer.provider_percentage.normalize():f}"


def settlement_offer(db: Session, offer: DisputeSettlementOffer, event: str) -> None:
    """Accord amiable : le prestataire reçoit la proposition avec les boutons
    pour répondre ; le client apprend la réponse ou l'expiration ; Nexis Hub
    est prévenu d'un accord conclu (le litige n'attend plus sa décision)."""
    mission = db.get(BotMission, offer.mission_id)
    mission_id = mission.mission_id
    if event == "proposed":
        enqueue(
            db,
            event_key=f"offer_proposed:{offer.id}",
            account_id=mission.provider_account_id,
            message_key=f"dispute_offer_received_{offer.kind}",
            params={
                "mission_id": mission_id,
                "deadline": kinshasa_time(offer.expires_at),
                "percentage": offer_percentage(offer),
                **_offer_amounts(offer, "provider"),
            },
            buttons=[[
                _button("button_offer_accept", f"doffer_ok_{mission_id}_{offer.id}"),
                _button("button_offer_decline", f"doffer_no_{mission_id}_{offer.id}"),
            ]],
        )
        return
    if event == "accepted":
        key = "dispute_offer_accepted_client_redo" if offer.kind == "redo" else "dispute_offer_accepted_client"
        enqueue(
            db,
            event_key=f"offer_accepted:{offer.id}",
            account_id=mission.client_account_id,
            message_key=key,
            params={"mission_id": mission_id, **_offer_amounts(offer, "client")},
        )
        what = {
            "redo": "le prestataire repasse (mission reprise, argent toujours bloqué)",
            "release": "prestataire payé en entier",
            "refund": "client remboursé en entier",
            "split": f"partage, {offer_percentage(offer)} % au prestataire",
        }[offer.kind]
        enqueue_admins(
            db,
            event_key=f"admin_offer_accepted:{offer.id}",
            params=admin_text(f"🤝 Accord amiable conclu : mission {_ref(mission_id)}, {what}. Le litige n'attend plus de décision."),
        )
    elif event in ("declined", "expired"):
        enqueue(
            db,
            event_key=f"offer_{event}:{offer.id}",
            account_id=mission.client_account_id,
            message_key=f"dispute_offer_{event}_client",
            params={"mission_id": mission_id},
            buttons=[[_button("button_propose_agreement", f"doffer_new_{mission_id}")]],
        )


# --- Présence du prestataire ---------------------------------------------------------


def presence_question(db: Session, mission: BotMission, code: str, asked_at: datetime) -> None:
    """« Votre prestataire est-il arrivé ? », avec la photo et le prénom du
    prestataire (le client vérifie que c'est bien la personne inscrite) et
    son code de présence. Une question par déclaration d'arrivée."""
    provider = profils.provider_profile(db, mission.provider_account_id)
    name = (provider.full_name or "").split()[0] if provider is not None and provider.full_name else "—"
    media = None
    if provider is not None and provider.selfie_file_id:
        # Sans photo (ou photo refusée par Telegram), la question part quand même.
        media = {"kind": "photo", "channel": "telegram", "id": provider.selfie_file_id, "optional": True}
    enqueue(
        db,
        event_key=f"presence_question:{mission.mission_id}:{asked_at:%Y%m%d%H%M%S%f}",
        account_id=mission.client_account_id,
        message_key="presence_question_client",
        params={"mission_id": mission.mission_id, "provider_name": name, "code": code},
        buttons=presence_question_buttons(mission.mission_id),
        media=media,
    )


def presence_confirmed(db: Session, mission: BotMission, *, tell_client: bool, tell_provider: bool) -> None:
    """Présence confirmée et mission démarrée. Chacun est prévenu, sauf celui
    dont le canal vient d'afficher la réponse."""
    if tell_client:
        enqueue(
            db,
            event_key=f"presence_confirmed:{mission.mission_id}",
            account_id=mission.client_account_id,
            message_key="presence_confirmed_client",
            params={"mission_id": mission.mission_id},
        )
    if tell_provider:
        enqueue(
            db,
            event_key=f"presence_confirmed:{mission.mission_id}",
            account_id=mission.provider_account_id,
            message_key="presence_confirmed_provider",
            params={"mission_id": mission.mission_id},
            buttons=provider_finish_buttons(mission.mission_id),
        )


def presence_not_yet(db: Session, mission: BotMission, answered_at: datetime) -> None:
    enqueue(
        db,
        event_key=f"presence_not_yet:{mission.mission_id}:{answered_at:%Y%m%d%H%M%S%f}",
        account_id=mission.provider_account_id,
        message_key="presence_not_yet_provider",
        params={"mission_id": mission.mission_id},
        buttons=provider_arrival_buttons(mission.mission_id),
    )


def presence_wrong_person(db: Session, mission: BotMission) -> None:
    enqueue(
        db,
        event_key=f"presence_wrong:{mission.mission_id}",
        account_id=mission.provider_account_id,
        message_key="presence_wrong_provider",
        params={"mission_id": mission.mission_id},
    )
    enqueue_admins(
        db,
        event_key=f"admin_presence_wrong:{mission.mission_id}",
        params=admin_text(
            f"🚫 « Ce n'est pas lui » : le client de la mission {_ref(mission.mission_id)} dit que la personne arrivée "
            f"n'est pas le prestataire inscrit (compte {mission.provider_account_id}). Litige ouvert, fonds gelés. "
            "À examiner dans /admin → Litiges."
        ),
    )


def presence_code_locked(db: Session, mission: BotMission, max_attempts: int) -> None:
    enqueue(
        db,
        event_key=f"presence_code_locked:{mission.mission_id}",
        account_id=mission.client_account_id,
        message_key="presence_code_locked_client",
        params={"mission_id": mission.mission_id},
    )
    enqueue_admins(
        db,
        event_key=f"admin_presence_code_locked:{mission.mission_id}",
        params=admin_text(
            f"⚠️ Code de présence : {max_attempts} mauvais codes tapés par le prestataire (compte "
            f"{mission.provider_account_id}) sur la mission {_ref(mission.mission_id)}. Seul le client peut maintenant "
            "confirmer l'arrivée. Tentative de deviner le code ?"
        ),
    )


# --- Comptes, prestataires, équipe ------------------------------------------------------


def new_device(db: Session, device, account_language: str | None = None) -> None:
    """Téléphone ajouté à un compte existant : la personne est prévenue, avec
    le bouton « Ce n'est pas moi ». Le délai de 72 h protège l'argent."""
    local = device.created_at + KINSHASA_OFFSET
    enqueue(
        db,
        event_key=f"new_device:{device.id}",
        account_id=device.account_id,
        message_key="app_new_device_alert",
        params={
            "device": device.label if device.label else {"$message": "app_device_unnamed"},
            "date": local.strftime("%d/%m/%Y"),
            "time": local.strftime("%H:%M"),
        },
        buttons=[[_button("button_app_not_me", f"app_not_me_{device.id}")]],
    )


def device_revoked(db: Session, device_id: int) -> None:
    """Téléphone coupé : son alerte « Nouvel appareil » ne part plus si elle
    attend encore."""
    withdraw(db, f"new_device:{device_id}")


def device_not_me(db: Session, device_id: int, account_id: int) -> None:
    enqueue_admins(
        db,
        event_key=f"admin_device_not_me:{device_id}",
        params=admin_text(
            f"🚨 « Ce n'est pas moi » : téléphone {device_id} du compte {account_id} coupé par la personne. "
            "Vérifie le compte (connexions récentes, retraits)."
        ),
    )


def provider_submitted(db: Session, provider: ProviderProfile, submitted_at: datetime) -> None:
    """Prestataire en attente de vérification : chaque admin reçoit son
    dossier (résumé, pièce d'identité, selfie, photos de travaux, puis les
    boutons Approuver / Refuser). Une fois par inscription ou réinscription."""
    stamp = f"{provider.account_id}:{submitted_at:%Y%m%d%H%M%S%f}"
    services = profils.provider_services(db, provider.account_id)
    communes = profils.provider_communes(db, provider.account_id)
    enqueue_admins(
        db,
        event_key=f"admin_provider_pending:{stamp}",
        message_key="admin_new_provider_summary",
        params={
            "nom": provider.full_name or "",
            "telephone": provider.phone_number or "",
            "services": {"$services": services},
            "communes": ", ".join(communes),
        },
    )
    documents = [
        ("id", provider.id_document_file_id, "admin_new_provider_id_caption"),
        ("selfie", provider.selfie_file_id, "admin_new_provider_selfie_caption"),
    ] + [
        (f"portfolio{position}", file_id, "admin_new_provider_portfolio_caption")
        for position, file_id in enumerate(provider.portfolio_file_ids or [])
    ]
    for name, file_id, caption in documents:
        # Une photo envoyée par l'app est gardée chiffrée par le backend :
        # l'admin l'ouvre dans l'espace admin, elle ne part pas sur Telegram.
        if not file_id or (len(file_id) == 32 and db.get(StoredFile, file_id) is not None):
            continue
        enqueue_admins(
            db,
            event_key=f"admin_provider_pending_{name}:{stamp}",
            message_key=caption,
            media={"kind": "photo", "channel": "telegram", "id": file_id},
        )
    enqueue_admins(
        db,
        event_key=f"admin_provider_pending_decide:{stamp}",
        message_key="admin_new_provider_approve_prompt",
        buttons=[[
            _button("button_admin_approve", f"admin_verify_provider_acc_{provider.account_id}"),
            _button("button_admin_reject", f"admin_reject_provider_acc_{provider.account_id}"),
        ]],
    )


PROVIDER_DECISION_MESSAGES = {
    "verify": "provider_verified_and_active",
    "reject": "provider_registration_rejected",
    "suspend": "provider_suspended_notice",
    "unsuspend": "provider_unsuspended_notice",
}


def provider_decided(db: Session, provider: ProviderProfile, action: str, decided_at: datetime) -> None:
    enqueue(
        db,
        event_key=f"provider_{action}:{provider.account_id}:{decided_at:%Y%m%d%H%M%S%f}",
        account_id=provider.account_id,
        message_key=PROVIDER_DECISION_MESSAGES[action],
    )


def client_request_decided(db: Session, request: ClientServiceRequest) -> None:
    enqueue(
        db,
        event_key=f"client_request_decided:{request.id}",
        account_id=request.account_id,
        message_key="client_need_accepted" if request.status == "accepted" else "client_need_rejected",
        params={"reference": f"BES-{request.id:04d}"},
    )


def service_request_decided(db: Session, request: ProviderServiceRequest) -> None:
    enqueue(
        db,
        event_key=f"service_request_decided:{request.id}",
        account_id=request.provider_account_id,
        message_key="service_request_accepted_provider" if request.status == "accepted" else "service_request_rejected_provider",
        params={"service": request.service_name},
    )


def service_addition_decided(db: Session, addition: ProviderServiceAddition) -> None:
    if addition.status == "approved":
        key, params = "service_addition_approved", {"service": {"$service": addition.service_key}}
    elif addition.admin_note:
        key, params = "service_addition_rejected_note", {"service": {"$service": addition.service_key}, "note": addition.admin_note}
    else:
        key, params = "service_addition_rejected", {"service": {"$service": addition.service_key}}
    enqueue(
        db,
        event_key=f"service_addition_decided:{addition.id}",
        account_id=addition.account_id,
        message_key=key,
        params=params,
    )


def money_switch_changed(
    db: Session,
    *,
    label: str,
    state_text: str,
    opened: bool,
    admin_account_id: int | None,
    source: str,
    reason: str,
    changed_at: datetime,
) -> None:
    """Flux d'argent coupé ou rouvert : les autres admins sont prévenus (tous,
    si le changement vient du serveur)."""
    who = f"l'admin (compte {admin_account_id})" if admin_account_id is not None else f"le serveur ({html.escape(source)})"
    enqueue_admins(
        db,
        event_key=f"admin_money_switch:{label.lower()}:{changed_at:%Y%m%d%H%M%S%f}",
        params=admin_text(f"{'🟢' if opened else '⛔'} {html.escape(label)} {html.escape(state_text)} par {who} : {html.escape(reason)}"),
        except_account_id=admin_account_id,
    )
