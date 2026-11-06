"""Rapprochement interne quotidien du registre d'argent (CONCEPTION_MOBILE_MONEY.md,
étape 6).

Vérifie que tout ce que le backend sait de l'argent concorde, sans rien
demander à l'agrégateur : registre en partie double, escrow de chaque mission,
argent bloqué de chaque retrait, intentions de paiement, frais, statuts recopiés
sur les missions. La comparaison avec le relevé de l'agrégateur s'ajoutera à ce
rapport quand son module existera (étape 5).

Lecture seule. Aucune correction automatique : un écart est signalé à l'admin,
qui corrige par une opération explicite, tracée dans le registre.
"""

import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app import ledger
from backend.app.ledger import ESCROW, FUNDING, PAYOUT_PENDING, SETTLEMENT, WALLET, ZERO, to_money
from backend.app.models import BotMission, LedgerEntry, MoneyOperation, PaymentIntent, Payout
from backend.app.payment_gateway import collection_fee_rate

# Une intention restée « created » ou un retrait resté « processing » au-delà
# de ces délais n'a pas été relu chez l'agrégateur : l'argent peut être parti
# ou arrivé sans que le registre le sache.
STUCK_INTENT_AFTER = timedelta(minutes=10)
STUCK_PAYOUT_AFTER = timedelta(hours=24)

# Paiements « Mobile Money » simulés au clic, d'avant les intentions de
# paiement (référence `SIM-<devis>`, ledger.PAYMENT_METHODS) : aucune
# intention ne leur correspond, c'est normal.
LEGACY_SIMULATED_REFERENCE = re.compile(r"^SIM-\d+$")

# Statut recopié sur la mission selon le règlement enregistré.
SETTLEMENT_PAYMENT_STATUS = {
    "release": "released",
    "auto_release": "released",
    "dispute_release": "released",
    "refund": "refunded",
    "split": "split",
}

# Opérations attendues sur l'argent bloqué d'un retrait, selon son statut.
PAYOUT_CLOSING_KIND = {"succeeded": "payout", "failed": "payout_failed", "rejected": "payout_rejected"}
PAYOUT_OPEN = ("awaiting_approval", "processing")


@dataclass
class Report:
    generated_at: datetime
    anomalies: list[dict] = field(default_factory=list)
    counts: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.anomalies

    def add(self, code: str, detail: str) -> None:
        self.anomalies.append({"code": code, "detail": detail})


def _balances(db: Session, account_type: str) -> dict[tuple[int | None, str], Decimal]:
    rows = (
        db.query(LedgerEntry.account_id, LedgerEntry.currency, func.sum(LedgerEntry.amount))
        .filter(LedgerEntry.account_type == account_type)
        .group_by(LedgerEntry.account_id, LedgerEntry.currency)
        .all()
    )
    return {(account_id, currency): to_money(total) for account_id, currency, total in rows}


def reconcile(db: Session, now: datetime | None = None) -> Report:
    now = now or ledger._utcnow()
    report = Report(generated_at=now)
    _check_double_entry(db, report)
    _check_no_negative_balance(db, report)
    _check_escrow(db, report)
    _check_payouts(db, report, now)
    _check_intents(db, report, now)
    _check_mobile_money_fundings(db, report)
    _check_mismatch_credits(db, report)
    report.counts = {
        "operations": db.query(func.count(MoneyOperation.id)).scalar(),
        "intents": db.query(func.count(PaymentIntent.id)).scalar(),
        "payouts": db.query(func.count(Payout.id)).scalar(),
    }
    return report


def _check_double_entry(db: Session, report: Report) -> None:
    rows = (
        db.query(LedgerEntry.operation_id, LedgerEntry.currency, func.sum(LedgerEntry.amount))
        .group_by(LedgerEntry.operation_id, LedgerEntry.currency)
        .all()
    )
    for operation_id, currency, total in rows:
        if to_money(total) != ZERO:
            report.add("unbalanced_operation", f"opération {operation_id} : somme {to_money(total)} {currency} au lieu de 0")


def _check_no_negative_balance(db: Session, report: Report) -> None:
    for account_type, label in ((WALLET, "wallet du compte"), (ESCROW, "escrow de la mission"), (PAYOUT_PENDING, "retrait")):
        for (account_id, currency), total in _balances(db, account_type).items():
            if total < ZERO:
                report.add("negative_balance", f"{label} {account_id} : {total} {currency}")


def _check_escrow(db: Session, report: Report) -> None:
    """L'escrow d'une mission vaut le montant payé tant qu'elle n'est pas
    réglée, 0 ensuite ; le statut recopié sur la mission suit le registre."""
    operations = defaultdict(dict)
    for operation in db.query(MoneyOperation).filter(MoneyOperation.phase.in_((FUNDING, SETTLEMENT))):
        operations[operation.mission_id][operation.phase] = operation
    escrow = _balances(db, ESCROW)

    missions_with_escrow = {mission_id for mission_id, _ in escrow} | set(operations)
    for mission_id in sorted(missions_with_escrow):
        funding = operations.get(mission_id, {}).get(FUNDING)
        settlement = operations.get(mission_id, {}).get(SETTLEMENT)
        held = {currency: total for (account_id, currency), total in escrow.items() if account_id == mission_id and total != ZERO}
        if funding is None:
            if held:
                report.add("escrow_without_funding", f"mission NXH-{mission_id:04d} : {held} en escrow sans paiement enregistré")
            if settlement is not None:
                report.add("settlement_without_funding", f"mission NXH-{mission_id:04d} : règlement sans paiement")
            continue
        currency = funding.details.get("currency")
        expected = ZERO if settlement is not None else to_money(funding.details["total"])
        if held.get(currency, ZERO) != expected or set(held) - {currency}:
            report.add("escrow_mismatch", f"mission NXH-{mission_id:04d} : escrow {held or 0}, attendu {expected} {currency}")

        mission = db.get(BotMission, mission_id)
        expected_status = SETTLEMENT_PAYMENT_STATUS.get(settlement.kind) if settlement is not None else "paid_escrow"
        if mission is not None and mission.payment_status != expected_status:
            report.add(
                "mission_status_mismatch",
                f"mission NXH-{mission_id:04d} : payment_status {mission.payment_status}, le registre dit {expected_status}",
            )

    for mission in db.query(BotMission).filter(BotMission.payment_status == "paid_escrow"):
        if FUNDING not in operations.get(mission.mission_id, {}):
            report.add("mission_status_mismatch", f"mission NXH-{mission.mission_id:04d} : marquée payée sans paiement au registre")


def _check_payouts(db: Session, report: Report, now: datetime) -> None:
    """L'argent d'un retrait est bloqué tant qu'il est ouvert, puis sort une
    seule fois : versé, ou rendu au wallet."""
    kinds = defaultdict(list)
    for operation in db.query(MoneyOperation).filter(
        MoneyOperation.kind.in_(("payout_hold", "payout", "payout_failed", "payout_rejected"))
    ):
        kinds[(operation.details or {}).get("payout_id")].append(operation.kind)
    pending = _balances(db, PAYOUT_PENDING)

    for payout in db.query(Payout).order_by(Payout.id):
        held = pending.get((payout.id, payout.currency), ZERO)
        expected_held = to_money(payout.amount) if payout.status in PAYOUT_OPEN else ZERO
        if held != expected_held:
            report.add("payout_hold_mismatch", f"retrait {payout.id} ({payout.status}) : {held} bloqué, attendu {expected_held} {payout.currency}")
        expected_kinds = ["payout_hold"] + ([PAYOUT_CLOSING_KIND[payout.status]] if payout.status in PAYOUT_CLOSING_KIND else [])
        if sorted(kinds.get(payout.id, [])) != sorted(expected_kinds):
            report.add("payout_operations_mismatch", f"retrait {payout.id} ({payout.status}) : opérations {kinds.get(payout.id, [])}, attendu {expected_kinds}")
        # created_at, pas updated_at : la vérification de secours rafraîchit
        # updated_at toutes les 2 min tant que l'agrégateur répond « en attente ».
        if payout.status == "processing" and payout.created_at < now - STUCK_PAYOUT_AFTER:
            report.add("payout_stuck", f"retrait {payout.id} demandé le {payout.created_at:%Y-%m-%d %H:%M}, toujours en cours d'envoi : statut à vérifier chez l'agrégateur")


def _check_intents(db: Session, report: Report, now: datetime) -> None:
    by_reference = defaultdict(list)
    for operation in db.query(MoneyOperation).filter(MoneyOperation.reference.isnot(None)):
        by_reference[operation.reference].append(operation)
    rate = collection_fee_rate()

    for intent in db.query(PaymentIntent).order_by(PaymentIntent.id):
        label = f"intention {intent.id} (mission NXH-{intent.mission_id:04d})"
        operations = by_reference.get(intent.gateway_reference, []) if intent.gateway_reference else []
        kinds = [operation.kind for operation in operations]
        if intent.status == "succeeded":
            funding = ledger.mission_operation(db, intent.mission_id, FUNDING)
            if funding is None or funding.kind != "fund_mobile_money" or funding.reference != intent.gateway_reference:
                report.add("intent_not_in_ledger", f"{label} confirmée, mais le paiement de la mission au registre ne lui correspond pas")
        elif intent.status == "overpaid":
            if kinds.count("overpayment") != 1:
                report.add("intent_not_in_ledger", f"{label} payée en trop, mais {kinds.count('overpayment')} crédit(s) au wallet au registre")
        elif intent.status in ("mismatch_credited", "mismatch_paid"):
            credits = [operation for operation in operations if operation.kind == "mismatch_credit"]
            credited = sum((entry.amount for entry in db.query(LedgerEntry).filter(
                LedgerEntry.operation_id.in_([operation.id for operation in credits]), LedgerEntry.account_type == ledger.WALLET
            )), ZERO)
            if len(credits) != 1 or intent.received_amount is None or to_money(credited) != to_money(intent.received_amount):
                report.add("intent_not_in_ledger", f"{label} réglée par l'admin, mais le crédit au wallet au registre ne correspond pas au montant reçu")
            if intent.status == "mismatch_paid":
                funding = ledger.mission_operation(db, intent.mission_id, FUNDING)
                if funding is None or funding.kind != "fund_wallet" or funding.reference != intent.gateway_reference:
                    report.add("intent_not_in_ledger", f"{label} : l'admin a fait payer la mission, mais son paiement au registre ne lui correspond pas")
        elif intent.status == "mismatch":
            # Argent reçu par l'agrégateur, hors registre, jusqu'à la décision de l'admin.
            report.add("intent_amount_mismatch", f"{label} : montant reçu différent ({intent.failure_reason}), décision de l'admin requise")
        elif intent.status == "created" and intent.created_at < now - STUCK_INTENT_AFTER:
            report.add("intent_stuck", f"{label} jamais transmise ou jamais relue chez l'agrégateur depuis {intent.created_at:%Y-%m-%d %H:%M}")

        if intent.status in ("succeeded", "overpaid", "mismatch_credited", "mismatch_paid"):
            fees = [operation for operation in operations if operation.kind == "collection_fee"]
            if len(fees) > 1:
                report.add("duplicate_fee", f"{label} : {len(fees)} frais d'encaissement enregistrés")
            fee = sum((-entry.amount for entry in db.query(LedgerEntry).filter(
                LedgerEntry.operation_id.in_([operation.id for operation in fees]), LedgerEntry.account_type == ledger.PLATFORM
            )), ZERO)
            # Frais calculés sur l'argent réellement encaissé.
            collected = intent.received_amount if intent.status.startswith("mismatch_") and intent.received_amount is not None else intent.amount
            currency = intent.received_currency if intent.status.startswith("mismatch_") and intent.received_currency else intent.currency
            expected_fee = to_money(Decimal(collected) * rate)
            if abs(to_money(fee) - expected_fee) > Decimal("0.01"):
                report.add("fee_deviation", f"{label} : frais {to_money(fee)} {currency}, attendus {expected_fee} au taux {rate}")


def _check_mobile_money_fundings(db: Session, report: Report) -> None:
    """Tout paiement Mobile Money au registre vient d'une intention confirmée."""
    confirmed = {
        reference for (reference,) in db.query(PaymentIntent.gateway_reference).filter(PaymentIntent.status == "succeeded")
    }
    for operation in db.query(MoneyOperation).filter(MoneyOperation.kind == "fund_mobile_money"):
        if operation.reference in confirmed or LEGACY_SIMULATED_REFERENCE.match(operation.reference or ""):
            continue
        report.add("funding_without_intent", f"paiement {operation.reference} de la mission NXH-{operation.mission_id:04d} sans intention confirmée")


def _check_mismatch_credits(db: Session, report: Report) -> None:
    """Tout crédit « montant différent » vient d'une décision de l'admin
    enregistrée sur l'intention, sur le compte et dans la devise de celle-ci.
    Sinon (crédit sans décision, intention restée « mismatch »), l'admin
    risquerait de créditer une seconde fois."""
    resolved = {
        intent.gateway_reference: intent
        for intent in db.query(PaymentIntent).filter(PaymentIntent.status.in_(("mismatch_credited", "mismatch_paid")))
        if intent.gateway_reference
    }
    for operation in db.query(MoneyOperation).filter(MoneyOperation.kind == "mismatch_credit"):
        intent = resolved.get(operation.reference)
        if intent is None:
            report.add("mismatch_credit_without_decision", f"crédit {operation.reference} (opération {operation.id}) sans décision de l'admin enregistrée sur une intention")
            continue
        entries = db.query(LedgerEntry).filter(LedgerEntry.operation_id == operation.id, LedgerEntry.account_type == WALLET).all()
        if any(entry.account_id != intent.account_id or entry.currency != intent.received_currency for entry in entries):
            report.add("mismatch_credit_mismatch", f"crédit {operation.reference} : compte ou devise différents de l'intention {intent.id}")


def format_admin_report(report: Report, limit: int = 20) -> str:
    """Message Telegram pour l'admin (textes admin en français, comme les
    autres alertes de backend/app/tasks.py)."""
    date = report.generated_at.strftime("%Y-%m-%d")
    counts = report.counts
    summary = f"{counts.get('operations', 0)} opérations, {counts.get('intents', 0)} intentions, {counts.get('payouts', 0)} retraits"
    if report.ok:
        return f"✅ Rapprochement du {date} : aucun écart ({summary})."
    lines = [f"⚠️ Rapprochement du {date} : {len(report.anomalies)} écart(s) ({summary}). Aucune correction automatique."]
    lines += [f"• {anomaly['detail']}" for anomaly in report.anomalies[:limit]]
    if len(report.anomalies) > limit:
        lines.append(f"… et {len(report.anomalies) - limit} autre(s).")
    return "\n".join(lines)
