"""Paiements et retraits Mobile Money réels (CONCEPTION_MOBILE_MONEY.md).

Deux temps, toujours : une demande (intention de paiement, retrait), puis la
confirmation de l'agrégateur, qui seule déplace l'argent dans le registre
(`backend/app/ledger.py`). Un webhook ne fait jamais foi seul : le statut est
toujours relu auprès de l'agrégateur (`refresh_intent`, `refresh_payout`).

Règles de Ben : frais d'encaissement à la charge de Nexis Hub ; frais de
retrait au prix coûtant à la charge du prestataire, avec un minimum ;
retraits validés par l'admin, automatiques seulement sous un plafond ; un
remboursement ne se retire qu'après vérification admin.
"""

import os
import re
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app import ledger
from backend.app.ledger import CENT, ZERO, MoneyError, to_money
from backend.app.models import BotMission, PaymentIntent, Payout
from backend.app.payment_gateway import FAILED, PENDING, SUCCEEDED, GatewayUnavailable, get_gateway

OPERATORS = {"mpesa", "airtel", "orange"}
OPEN_INTENT = ("created", "pending")
# Une intention expirée peut encore être confirmée en retard par
# l'agrégateur : elle reste relue, et l'argent n'est jamais ignoré.
REFRESHABLE_INTENT = OPEN_INTENT + ("expired",)
INTENT_LIFETIME = timedelta(minutes=15)
PHONE_RE = re.compile(r"^\+243\d{9}$")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _setting(name: str, currency: str, default: str) -> Decimal:
    """Réglages par devise, ex. PAYOUT_MINIMUM_USD. À fixer avec les tarifs
    PayOut de FlexPaie ; valeurs par défaut prudentes."""
    return to_money(os.getenv(f"{name}_{currency}", default))


def payout_fee(amount: Decimal, currency: str) -> Decimal:
    rate = Decimal(os.getenv("PAYOUT_FEE_RATE", "0"))
    fixed = _setting("PAYOUT_FEE_FIXED", currency, "0")
    return ((amount * rate).quantize(CENT, rounding=ROUND_HALF_UP) + fixed)


def _check_phone_and_operator(phone: str, operator: str) -> None:
    if operator not in OPERATORS:
        raise MoneyError("invalid_operator", 400)
    if not PHONE_RE.match(phone or ""):
        raise MoneyError("invalid_phone", 400)


# --- Encaissement -----------------------------------------------------------------


def create_intent(db: Session, mission_id: int, *, phone: str, operator: str, funding_request: dict) -> PaymentIntent:
    """Ouvre (ou renvoie) l'intention de paiement de la mission et demande à
    l'agrégateur d'envoyer la demande sur le téléphone du client.

    `funding_request` : les paramètres de `ledger.fund_mission`, sauf la
    méthode ; ils serviront tels quels quand l'argent arrivera."""
    _check_phone_and_operator(phone, operator)
    currency = funding_request["currency"]
    if currency not in ledger.CURRENCIES:
        raise MoneyError("invalid_currency", 400)
    amount = ledger.payment_amounts(funding_request["amount"], funding_request["urgent"])["total"]
    client_telegram_id = funding_request["client_telegram_id"]
    if funding_request["provider_telegram_id"] == client_telegram_id:
        raise MoneyError("provider_is_client")

    mission = db.get(BotMission, mission_id)
    if mission is not None and mission.telegram_id != client_telegram_id:
        raise MoneyError("not_mission_client", 403, mission)
    if ledger.mission_operation(db, mission_id, ledger.FUNDING) is not None:
        raise MoneyError("already_paid", mission=mission)
    if mission is not None and (mission.status not in ledger.FUNDABLE_STATUSES or mission.payment_status not in (None, "unpaid")):
        raise MoneyError("invalid_state", mission=mission)
    if mission is None:
        # La mission doit exister pour l'intention (clé étrangère) : même
        # création que le paiement, sans argent.
        db.add(
            BotMission(
                mission_id=mission_id,
                telegram_id=client_telegram_id,
                service=funding_request["service"],
                commune=funding_request["commune"],
                currency=currency,
                description=funding_request.get("description", ""),
                urgent=bool(funding_request["urgent"]),
                status="pending",
            )
        )

    existing = _open_intent(db, mission_id)
    if existing is not None:
        return existing
    intent = PaymentIntent(
        mission_id=mission_id,
        account_id=ledger.account_id_for(db, ledger.TELEGRAM, client_telegram_id, create=True),
        gateway=get_gateway().name,
        operator=operator,
        phone=phone,
        amount=amount,
        currency=currency,
        funding_request=funding_request,
        status="created",
        expires_at=_utcnow() + INTENT_LIFETIME,
    )
    db.add(intent)
    try:
        db.commit()
    except IntegrityError:
        # Deux clics simultanés : l'index « une intention ouverte par mission »
        # en a refusé une ; on renvoie celle qui a gagné.
        db.rollback()
        existing = _open_intent(db, mission_id)
        if existing is None:
            raise
        return existing

    try:
        result = get_gateway().request_collection(intent)
    except GatewayUnavailable:
        intent.status, intent.failure_reason, intent.updated_at = "failed", "gateway_unavailable", _utcnow()
        db.commit()
        raise MoneyError("gateway_unavailable", 503)
    return _apply_collection_result(db, intent, result)


def _open_intent(db: Session, mission_id: int) -> PaymentIntent | None:
    return (
        db.query(PaymentIntent)
        .filter(PaymentIntent.mission_id == mission_id, PaymentIntent.status.in_(OPEN_INTENT))
        .one_or_none()
    )


def refresh_intent(db: Session, intent_id: int) -> PaymentIntent:
    """Relit le statut auprès de l'agrégateur (webhook reçu, ou vérification
    de secours) et en tire les conséquences."""
    intent = db.get(PaymentIntent, intent_id, with_for_update=True)
    if intent is None:
        raise MoneyError("intent_not_found", 404)
    if intent.status not in REFRESHABLE_INTENT:
        return intent
    try:
        result = get_gateway().collection_status(intent)
    except GatewayUnavailable:
        db.rollback()
        return db.get(PaymentIntent, intent_id)
    return _apply_collection_result(db, intent, result)


def _apply_collection_result(db: Session, intent: PaymentIntent, result) -> PaymentIntent:
    intent_id = intent.id
    now = _utcnow()
    if result.reference and not intent.gateway_reference:
        intent.gateway_reference = result.reference
    if result.status == PENDING:
        if intent.status != "expired":
            intent.status = "expired" if now > intent.expires_at else "pending"
        intent.updated_at = now
        db.commit()
        return intent
    if result.status == FAILED:
        intent.status, intent.failure_reason, intent.updated_at = "failed", (result.reason or "refused")[:255], now
        db.commit()
        return intent
    if result.status != SUCCEEDED:
        raise RuntimeError(f"Statut d'agrégateur inconnu : {result.status}")

    if to_money(result.amount) != to_money(intent.amount) or result.currency != intent.currency:
        # Jamais de paiement de mission sur un montant différent : l'admin tranche.
        intent.status, intent.failure_reason, intent.updated_at = "mismatch", f"reçu {result.amount} {result.currency}", now
        db.commit()
        return intent

    fee = to_money(result.fee or ZERO)
    reference = intent.gateway_reference

    def also(mission):
        intent.status, intent.updated_at = "succeeded", now
        ledger.record_collection_fee(db, mission_id=intent.mission_id, currency=intent.currency, fee=fee, reference=reference)

    request = dict(intent.funding_request)
    try:
        ledger.fund_mission(db, intent.mission_id, method="mobile_money", reference=reference, also=also, **request)
    except MoneyError as error:
        if error.code in ("invalid_amount", "invalid_currency", "invalid_method"):
            raise
        # Argent bien reçu, mais la mission est déjà payée (confirmation en
        # retard, autre intention) ou ne peut plus l'être : il n'est jamais
        # perdu, il va au wallet du client.
        db.rollback()
        intent = db.get(PaymentIntent, intent_id, with_for_update=True)
        if intent.status not in REFRESHABLE_INTENT:
            return intent
        ledger.record_overpayment(
            db, account_id=intent.account_id, currency=intent.currency, amount=intent.amount, reference=reference, mission_id=intent.mission_id
        )
        ledger.record_collection_fee(db, mission_id=intent.mission_id, currency=intent.currency, fee=fee, reference=reference)
        intent.status, intent.failure_reason, intent.updated_at = "overpaid", error.code, now
        db.commit()
    return db.get(PaymentIntent, intent_id)


# --- Retraits ---------------------------------------------------------------------


def request_payout(db: Session, *, telegram_id: int, amount, currency: str, phone: str, operator: str) -> Payout:
    """Bloque le montant et crée le retrait. Il part tout de suite seulement
    s'il ne demande aucune vérification (sous le plafond, aucun fonds de
    remboursement) ; sinon il attend l'admin."""
    _check_phone_and_operator(phone, operator)
    if currency not in ledger.CURRENCIES:
        raise MoneyError("invalid_currency", 400)
    amount = to_money(amount)
    if amount <= ZERO:
        raise MoneyError("invalid_amount", 400)
    if amount < _setting("PAYOUT_MINIMUM", currency, "5" if currency == "USD" else "10000"):
        raise MoneyError("below_minimum")
    fee = payout_fee(amount, currency)
    if fee >= amount:
        raise MoneyError("below_minimum")
    account_id = ledger.account_id_for(db, ledger.TELEGRAM, telegram_id)
    if account_id is None:
        raise MoneyError("insufficient_balance")

    review = None
    if amount > ledger.withdrawable_without_review(db, account_id, currency):
        review = "refund_funds"
    elif amount > _setting("PAYOUT_AUTO_LIMIT", currency, "0"):
        review = "above_auto_limit"

    payout = Payout(
        account_id=account_id,
        requested_by_telegram_id=telegram_id,
        gateway=get_gateway().name,
        operator=operator,
        phone=phone,
        amount=amount,
        fee=fee,
        currency=currency,
        status="awaiting_approval" if review else "processing",
        needs_review_reason=review,
    )
    db.add(payout)
    db.flush()
    ledger.hold_payout(db, payout)
    db.commit()
    if review is None:
        return _send_payout(db, payout.id)
    return payout


def approve_payout(db: Session, payout_id: int, admin_telegram_id: int) -> Payout:
    payout = db.get(Payout, payout_id, with_for_update=True)
    if payout is None:
        raise MoneyError("payout_not_found", 404)
    if payout.status != "awaiting_approval":
        if payout.status in ("processing", "succeeded") and payout.decided_by_telegram_id == admin_telegram_id:
            return payout  # double clic
        raise MoneyError("invalid_state")
    payout.status, payout.decided_by_telegram_id, payout.updated_at = "processing", admin_telegram_id, _utcnow()
    db.commit()
    return _send_payout(db, payout_id)


def reject_payout(db: Session, payout_id: int, admin_telegram_id: int, reason: str = "") -> Payout:
    payout = db.get(Payout, payout_id, with_for_update=True)
    if payout is None:
        raise MoneyError("payout_not_found", 404)
    if payout.status == "rejected":
        return payout
    if payout.status != "awaiting_approval":
        raise MoneyError("invalid_state")
    ledger.release_payout(db, payout, "payout_rejected")
    payout.status, payout.decided_by_telegram_id = "rejected", admin_telegram_id
    payout.failure_reason, payout.updated_at = (reason or "")[:255] or None, _utcnow()
    db.commit()
    return payout


def _send_payout(db: Session, payout_id: int) -> Payout:
    payout = db.get(Payout, payout_id, with_for_update=True)
    try:
        result = get_gateway().request_payout(payout)
    except GatewayUnavailable:
        # On ne sait pas si l'agrégateur a reçu l'ordre : surtout ne pas rendre
        # l'argent ni le renvoyer. La vérification de secours relit le statut
        # (référence = id du retrait) et le rapprochement tranche.
        db.rollback()
        return db.get(Payout, payout_id)
    return _apply_payout_result(db, payout, result)


def refresh_payout(db: Session, payout_id: int) -> Payout:
    payout = db.get(Payout, payout_id, with_for_update=True)
    if payout is None:
        raise MoneyError("payout_not_found", 404)
    if payout.status != "processing":
        return payout
    try:
        result = get_gateway().payout_status(payout)
    except GatewayUnavailable:
        db.rollback()
        return db.get(Payout, payout_id)
    return _apply_payout_result(db, payout, result)


def _apply_payout_result(db: Session, payout: Payout, result) -> Payout:
    if result.reference and not payout.gateway_reference:
        payout.gateway_reference = result.reference
    payout.updated_at = _utcnow()
    if result.status == SUCCEEDED:
        ledger.complete_payout(db, payout, payout.gateway_reference)
        payout.status = "succeeded"
    elif result.status == FAILED:
        ledger.release_payout(db, payout, "payout_failed")
        payout.status, payout.failure_reason = "failed", (result.reason or "refused")[:255]
    db.commit()
    return payout


def withdrawable(db: Session, telegram_id: int, currency: str) -> dict:
    account_id = ledger.account_id_for(db, ledger.TELEGRAM, telegram_id)
    if account_id is None:
        return {"balance": "0.00", "without_review": "0.00"}
    return {
        "balance": str(ledger.balance(db, ledger.WALLET, account_id, currency)),
        "without_review": str(ledger.withdrawable_without_review(db, account_id, currency)),
    }
