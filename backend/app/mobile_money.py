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
from backend.app.models import NexisAccount, PaymentIntent, Payout
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

    # La mission doit exister pour l'intention (clé étrangère) : même création
    # que le paiement, sans argent. Verrouillée jusqu'à la fin de la demande.
    mission = ledger.ensure_mission(
        db, mission_id, client_telegram_id=client_telegram_id, service=funding_request["service"],
        commune=funding_request["commune"], currency=currency, description=funding_request.get("description", ""),
        urgent=funding_request["urgent"],
    )
    if mission.telegram_id != client_telegram_id:
        raise MoneyError("not_mission_client", 403, mission)
    if ledger.mission_operation(db, mission_id, ledger.FUNDING) is not None:
        raise MoneyError("already_paid", mission=mission)
    if mission.status not in ledger.FUNDABLE_STATUSES or mission.payment_status not in (None, "unpaid"):
        raise MoneyError("invalid_state", mission=mission)

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


# Une intention « created » plus vieille que ce délai n'a jamais reçu la réponse
# de l'agrégateur (backend arrêté entre son enregistrement et l'appel). Le délai
# laisse finir une demande encore en cours.
STALLED_CREATED_AFTER = timedelta(minutes=2)
LATE_CONFIRMATION_WINDOW = timedelta(hours=24)


def intents_to_refresh(db: Session, now: datetime) -> list[int]:
    """Intentions à relire chez l'agrégateur par la vérification de secours :
    en attente ; restées « created » (sinon elles bloquaient la mission, une
    seule intention ouverte, et un paiement reçu entre-temps n'arrivait jamais
    au registre) ; expirées depuis moins de 24 h, car un paiement confirmé en
    retard n'est jamais ignoré."""
    rows = (
        db.query(PaymentIntent.id)
        .filter(
            (PaymentIntent.status == "pending")
            | ((PaymentIntent.status == "created") & (PaymentIntent.created_at < now - STALLED_CREATED_AFTER))
            | ((PaymentIntent.status == "expired") & (PaymentIntent.expires_at > now - LATE_CONFIRMATION_WINDOW))
        )
        .order_by(PaymentIntent.id)
        .all()
    )
    return [intent_id for (intent_id,) in rows]


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
        intent.received_amount = to_money(result.amount) if result.amount is not None else None
        intent.received_currency = (result.currency or "")[:3] or None
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


# --- Montant reçu différent : décision de l'admin ----------------------------------

# Décision -> statut final de l'intention.
MISMATCH_DECISIONS = {"credit_wallet": "mismatch_credited", "pay_mission": "mismatch_paid"}


def list_mismatches(db: Session, limit: int = 20) -> list[PaymentIntent]:
    return (
        db.query(PaymentIntent)
        .filter(PaymentIntent.status == "mismatch")
        .order_by(PaymentIntent.id)
        .limit(min(limit, 50))
        .all()
    )


def resolve_mismatch(db: Session, intent_id: int, admin_telegram_id: int, decision: str) -> tuple[PaymentIntent, bool]:
    """L'agrégateur a encaissé un montant différent de la demande : l'argent
    est chez lui, hors registre. L'admin décide, en une transaction :

    - `credit_wallet` : le montant reçu va au wallet du client ;
    - `pay_mission` : même crédit, puis la mission est payée depuis ce wallet
      au montant du devis (seulement dans la même devise et si le reçu suffit) ;
      le surplus reste au wallet.

    Le montant reçu est toujours relu chez l'agrégateur au moment de décider,
    jamais repris d'une ancienne réponse ; agrégateur injoignable ou paiement
    non confirmé = rien ne bouge. Rejouer la même décision ne crédite jamais
    deux fois (intention verrouillée, statut final).

    Renvoie l'intention et si cet appel a réglé le paiement (False pour un
    rejeu : le client n'est prévenu qu'une fois)."""
    try:
        return _resolve_mismatch(db, intent_id, admin_telegram_id, decision)
    except Exception:
        # Tout refus ou panne annule l'ensemble et libère le verrou.
        db.rollback()
        raise


def _resolve_mismatch(db: Session, intent_id: int, admin_telegram_id: int, decision: str) -> tuple[PaymentIntent, bool]:
    if decision not in MISMATCH_DECISIONS:
        raise MoneyError("invalid_decision", 400)
    intent = db.get(PaymentIntent, intent_id, with_for_update=True)
    if intent is None:
        raise MoneyError("intent_not_found", 404)
    if intent.status in MISMATCH_DECISIONS.values():
        if intent.status == MISMATCH_DECISIONS[decision]:
            db.commit()  # rien écrit : libère le verrou
            return intent, False
        raise MoneyError("already_resolved")
    if intent.status != "mismatch":
        raise MoneyError("invalid_state")

    try:
        result = get_gateway().collection_status(intent)
    except GatewayUnavailable:
        raise MoneyError("gateway_unavailable", 503)
    if result.status != SUCCEEDED:
        raise MoneyError("gateway_not_confirmed")
    if result.amount is None or result.currency not in ledger.CURRENCIES or to_money(result.amount) <= ZERO:
        # Montant ou devise que le registre ne sait pas porter : à régler
        # avec l'agrégateur, jamais deviné ici.
        raise MoneyError("invalid_received_amount")
    if intent.gateway_reference and result.reference and result.reference != intent.gateway_reference:
        raise MoneyError("reference_mismatch")
    if not (intent.gateway_reference or result.reference):
        # Sans référence, l'argent entrerait au registre sans lien avec
        # l'agrégateur : ni rapprochement, ni preuve. À voir avec lui.
        raise MoneyError("missing_reference")

    received, currency = to_money(result.amount), result.currency
    intent.gateway_reference = reference = intent.gateway_reference or result.reference
    now = _utcnow()
    if decision == "pay_mission" and (currency != intent.currency or received < to_money(intent.amount)):
        raise MoneyError("received_amount_too_low")

    intent.received_amount, intent.received_currency = received, currency
    intent.resolved_by_telegram_id, intent.resolved_at, intent.updated_at = admin_telegram_id, now, now
    intent.status = MISMATCH_DECISIONS[decision]
    ledger.record_mismatch_credit(
        db, account_id=intent.account_id, currency=currency, amount=received, reference=reference,
        mission_id=intent.mission_id, admin_telegram_id=admin_telegram_id,
    )
    ledger.record_collection_fee(db, mission_id=intent.mission_id, currency=currency, fee=result.fee or ZERO, reference=reference)
    if decision == "credit_wallet":
        db.commit()
        return db.get(PaymentIntent, intent_id), True

    # Le solde du wallet est relu par `fund_mission` : écritures envoyées
    # d'abord, validées ensemble avec le paiement (ou annulées avec lui).
    db.flush()
    ledger.fund_mission(db, intent.mission_id, method="wallet", reference=reference, **dict(intent.funding_request))
    intent = db.get(PaymentIntent, intent_id)
    if intent.status != "mismatch_paid":
        # `fund_mission` n'a rien validé (rejeu concurrent impossible sous le
        # verrou de l'intention) : on ne laisse jamais un état à moitié écrit.
        raise RuntimeError(f"Intention {intent_id} : paiement de la mission non validé")
    return intent, True


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

    # Verrou sur le compte AVANT de décider s'il faut l'admin : sinon deux
    # retraits simultanés lisent la même part « sans vérification » et
    # sortent ensemble l'argent d'un remboursement sans validation.
    db.get(NexisAccount, account_id, with_for_update=True)
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
