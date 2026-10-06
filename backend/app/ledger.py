"""Argent de Nexis Hub : seule source de vérité (voir CONCEPTION_ARGENT.md).

Toute opération d'argent passe par ce module et par lui seul : paiement d'une
mission (Mobile Money ou wallet), démarrage et fin (qui conditionnent la
libération), confirmation client, libération automatique, litige et sa
résolution. Chaque opération :

- s'exécute dans une seule transaction SQL : la mission est verrouillée
  (`FOR UPDATE`), l'opération, ses mouvements et le nouvel état de la mission
  sont écrits ensemble, puis validés ; en cas d'erreur, rien n'est écrit ;
- est idempotente : `money_operations` n'accepte qu'un paiement (`funding`)
  et qu'un règlement (`settlement`) par mission. Rejouer la même demande
  renvoie le résultat déjà enregistré ; une demande différente sur une phase
  déjà prise est refusée ;
- écrit des mouvements en partie double dont la somme vaut 0. Un solde est la
  somme des mouvements d'un compte : il n'existe aucune autre copie.

Les refus métier lèvent `MoneyError` avec un code stable, que l'API traduit
en réponse HTTP et que le bot traduit en message pour l'utilisateur.
"""

from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.models import BotMission, BotUser, ChannelIdentity, LedgerEntry, MoneyOperation, NexisAccount, Payout

CENT = Decimal("0.01")
ZERO = Decimal("0.00")
CURRENCIES = ("USD", "CDF")

STANDARD_COMMISSION_RATE = Decimal("0.10")
URGENT_COMMISSION_RATE = Decimal("0.15")
DISPUTE_RESOLUTION_DELAY = timedelta(hours=48)
AUTO_RELEASE_DELAY = timedelta(hours=24)
MAX_DISPUTE_REASON_LENGTH = 1000

FUNDING = "funding"
SETTLEMENT = "settlement"

# Méthode de paiement -> type d'opération et préfixe de référence.
PAYMENT_METHODS = {
    "mobile_money": ("fund_mobile_money", "SIM"),
    "wallet": ("fund_wallet", "WLT"),
}
DISPUTE_DECISIONS = {"refund", "release", "split"}

# Une mission se paie avant tout démarrage ; un litige s'ouvre après paiement
# et avant tout règlement.
FUNDABLE_STATUSES = {None, "pending", "quoted", "confirmed"}
DISPUTABLE_STATUSES = {"confirmed", "in_progress", "awaiting_confirmation"}

# Canaux par lesquels une personne s'identifie (voir `account_id_for`).
TELEGRAM = "telegram"

# Comptes du registre. Une personne n'a qu'un wallet, qu'elle agisse en
# cliente ou en prestataire.
EXTERNAL = "external"
WALLET = "wallet"
ESCROW = "escrow"
PAYOUT_PENDING = "payout_pending"  # identifiant : id du retrait
FEES = "fees"  # frais facturés par l'agrégateur
PLATFORM = "platform"


def _utcnow() -> datetime:
    # Colonnes DateTime naïves en UTC, comme le reste du schéma.
    return datetime.now(timezone.utc).replace(tzinfo=None)


class MoneyError(Exception):
    """Refus métier. `code` est stable (le bot le traduit), `http_status`
    sert à l'API, `mission` est l'état courant à renvoyer à l'appelant."""

    def __init__(self, code: str, http_status: int = 409, mission: BotMission | None = None):
        super().__init__(code)
        self.code = code
        self.http_status = http_status
        self.mission = mission


def to_money(value) -> Decimal:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as error:
        raise MoneyError("invalid_amount", 400) from error
    if not amount.is_finite():
        raise MoneyError("invalid_amount", 400)
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


def payment_amounts(amount, urgent: bool) -> dict[str, Decimal]:
    """Le client paie le montant du devis ; la plateforme prend 10 % (15 % si
    urgent), arrondis au centime ; le prestataire reçoit le reste."""
    total = to_money(amount)
    if total <= ZERO:
        raise MoneyError("invalid_amount", 400)
    rate = URGENT_COMMISSION_RATE if urgent else STANDARD_COMMISSION_RATE
    commission = (total * rate).quantize(CENT, rounding=ROUND_HALF_UP)
    return {"total": total, "commission": commission, "net": total - commission}


# --- Lecture -----------------------------------------------------------------


def balance(db: Session, account_type: str, account_id: int | None, currency: str) -> Decimal:
    total = (
        db.query(func.coalesce(func.sum(LedgerEntry.amount), 0))
        .filter(
            LedgerEntry.account_type == account_type,
            LedgerEntry.account_id.is_(None) if account_id is None else LedgerEntry.account_id == account_id,
            LedgerEntry.currency == currency,
        )
        .scalar()
    )
    return to_money(total)


def account_id_for(db: Session, channel: str, external_id, create: bool = False) -> int | None:
    """Compte Nexis d'un identifiant de canal ; créé à la demande. Le registre
    ne connaît que ces comptes, jamais un identifiant Telegram ou WhatsApp."""
    external_id = str(external_id)
    identity = (
        db.query(ChannelIdentity)
        .filter(ChannelIdentity.channel == channel, ChannelIdentity.external_id == external_id)
        .one_or_none()
    )
    if identity is not None:
        return identity.account_id
    if not create:
        return None
    try:
        with db.begin_nested():
            account = NexisAccount()
            db.add(account)
            db.flush()
            db.add(ChannelIdentity(account_id=account.id, channel=channel, external_id=external_id, verified_at=_utcnow()))
            db.flush()
        return account.id
    except IntegrityError:
        # Créé au même instant par une autre requête : on prend le sien.
        account_id = account_id_for(db, channel, external_id)
        if account_id is None:
            raise
        return account_id


def wallet_balances(db: Session, channel: str, external_id) -> dict[str, Decimal]:
    account_id = account_id_for(db, channel, external_id)
    if account_id is None:
        return {currency: ZERO for currency in CURRENCIES}
    return {currency: balance(db, WALLET, account_id, currency) for currency in CURRENCIES}


def mission_operation(db: Session, mission_id: int, phase: str) -> MoneyOperation | None:
    return (
        db.query(MoneyOperation)
        .filter(MoneyOperation.mission_id == mission_id, MoneyOperation.phase == phase)
        .one_or_none()
    )


def mission_money_state(db: Session, mission_id: int) -> dict:
    """Paiement et règlement enregistrés d'une mission, montants en texte."""
    state = {}
    for phase in (FUNDING, SETTLEMENT):
        operation = mission_operation(db, mission_id, phase)
        state[phase] = (
            {"kind": operation.kind, "reference": operation.reference, **(operation.details or {})}
            if operation is not None
            else None
        )
    return state


# --- Écriture (privé) ---------------------------------------------------------


def _record(
    db: Session,
    *,
    kind: str,
    currency: str,
    movements: list[tuple[str, int | None, Decimal]],
    mission_id: int | None = None,
    phase: str | None = None,
    actor_telegram_id: int | None = None,
    reference: str | None = None,
    details: dict | None = None,
) -> MoneyOperation:
    movements = [(account_type, account_id, amount) for account_type, account_id, amount in movements if amount != ZERO]
    if any(account_id is None for account_type, account_id, _ in movements if account_type in (WALLET, ESCROW, PAYOUT_PENDING)):
        raise RuntimeError(f"Opération {kind} : compte sans identifiant : {movements}")
    if sum((amount for _, _, amount in movements), ZERO) != ZERO:
        # Invariant de partie double : ne peut arriver que par bug de ce module.
        raise RuntimeError(f"Opération {kind} déséquilibrée : {movements}")
    operation = MoneyOperation(
        kind=kind,
        mission_id=mission_id,
        phase=phase,
        actor_telegram_id=actor_telegram_id,
        reference=reference,
        details=details or {},
    )
    db.add(operation)
    db.flush()  # lève IntegrityError tout de suite si la phase est déjà prise
    for account_type, account_id, amount in movements:
        db.add(
            LedgerEntry(
                operation_id=operation.id,
                account_type=account_type,
                account_id=account_id,
                currency=currency,
                amount=amount,
            )
        )
    return operation


def _set_status(mission: BotMission, status: str) -> None:
    mission.status = status
    mission.status_changed_at = _utcnow()


def _lock_mission(db: Session, mission_id: int) -> BotMission:
    mission = db.get(BotMission, mission_id, with_for_update=True)
    if mission is None:
        raise MoneyError("mission_not_found", 404)
    return mission


def ensure_mission(
    db: Session, mission_id: int, *, client_telegram_id: int, service: str, commune: str, currency: str, description: str, urgent: bool
) -> BotMission:
    """Mission verrouillée, créée si le backend ne l'a jamais reçue (le bot
    crée missions et devis dans db.py). Création dans un point de reprise :
    deux requêtes simultanées ne la créent qu'une fois."""
    mission = db.get(BotMission, mission_id, with_for_update=True)
    if mission is not None:
        return mission
    try:
        with db.begin_nested():
            db.add(
                BotMission(
                    mission_id=mission_id,
                    telegram_id=client_telegram_id,
                    service=service,
                    commune=commune,
                    currency=currency,
                    description=description,
                    urgent=bool(urgent),
                    status="pending",
                )
            )
            client = db.get(BotUser, client_telegram_id)
            if client is not None:
                client.total_missions += 1
    except IntegrityError:
        pass  # créée au même instant par une autre requête
    return db.get(BotMission, mission_id, with_for_update=True)


def _funded_amounts(db: Session, mission: BotMission) -> dict[str, Decimal]:
    """Montants tels qu'enregistrés au paiement : la seule référence pour
    libérer, rembourser ou partager (jamais les colonnes float de la mission)."""
    funding = mission_operation(db, mission.mission_id, FUNDING)
    if funding is None:
        raise MoneyError("not_paid", mission=mission)
    details = funding.details
    return {"total": to_money(details["total"]), "commission": to_money(details["commission"]), "net": to_money(details["net"])}


def _write(db: Session, mission_id: int, phase: str, matches, write) -> None:
    """Écrit (`write`) puis valide, en une transaction. Si une requête
    concurrente a pris la même phase entre-temps (contrainte d'unicité, ou
    mission créée en même temps), annule tout et décide : rejeu identique
    accepté, toute autre demande refusée."""
    try:
        write()
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = mission_operation(db, mission_id, phase)
        mission = db.get(BotMission, mission_id)
        if existing is not None and matches(existing):
            return
        raise MoneyError("already_paid" if phase == FUNDING else "already_settled", mission=mission)


# --- Paiement ----------------------------------------------------------------


def fund_mission(
    db: Session,
    mission_id: int,
    *,
    method: str,
    client_telegram_id: int,
    provider_telegram_id: int,
    quote_ref: int,
    amount,
    currency: str,
    urgent: bool,
    service: str,
    commune: str,
    description: str = "",
    reference: str | None = None,
    also=None,
) -> BotMission:
    """Paie une mission en escrow.

    `reference` : référence de l'agrégateur (paiement Mobile Money réel) ;
    `also(mission)` : écritures à valider dans la même transaction (statut de
    l'intention de paiement, frais d'agrégateur). La demande porte tout ce qu'il faut (le
    bot crée missions et devis dans db.py) : si la mission n'existe pas encore
    côté backend, elle est créée ici, sans dépendre d'une recopie antérieure."""
    if method not in PAYMENT_METHODS:
        raise MoneyError("invalid_method", 400)
    if currency not in CURRENCIES:
        raise MoneyError("invalid_currency", 400)
    amounts = payment_amounts(amount, urgent)
    kind, reference_prefix = PAYMENT_METHODS[method]
    details = {
        "method": method,
        "quote_ref": quote_ref,
        "provider_telegram_id": provider_telegram_id,
        "currency": currency,
        "urgent": bool(urgent),
        "total": str(amounts["total"]),
        "commission": str(amounts["commission"]),
        "net": str(amounts["net"]),
    }

    reference = reference or f"{reference_prefix}-{quote_ref:04d}"

    def matches(operation: MoneyOperation) -> bool:
        # Même référence exigée : un second paiement Mobile Money réel (autre
        # référence d'agrégateur) n'est jamais pris pour un rejeu du premier.
        return operation.kind == kind and operation.details == details and operation.reference == reference

    mission = ensure_mission(
        db, mission_id, client_telegram_id=client_telegram_id, service=service, commune=commune,
        currency=currency, description=description, urgent=urgent,
    )
    if mission.telegram_id != client_telegram_id:
        raise MoneyError("not_mission_client", 403, mission)

    existing = mission_operation(db, mission_id, FUNDING)
    if existing is not None:
        if matches(existing):
            return mission
        raise MoneyError("already_paid", mission=mission)
    if mission.status not in FUNDABLE_STATUSES or mission.payment_status not in (None, "unpaid"):
        raise MoneyError("invalid_state", mission=mission)

    client_account_id = account_id_for(db, TELEGRAM, client_telegram_id, create=True)
    provider_account_id = account_id_for(db, TELEGRAM, provider_telegram_id, create=True)
    if provider_account_id == client_account_id:
        # Une même personne peut être cliente et prestataire, jamais sur la
        # même mission : elle se paierait elle-même.
        raise MoneyError("provider_is_client", mission=mission)
    if method == "wallet":
        # Verrou sur le compte du client : deux paiements wallet simultanés ne
        # peuvent pas lire le même solde puis le débiter deux fois.
        db.get(NexisAccount, client_account_id, with_for_update=True)
        if balance(db, WALLET, client_account_id, currency) < amounts["total"]:
            raise MoneyError("insufficient_balance", mission=mission)
        source = (WALLET, client_account_id)
    else:
        source = (EXTERNAL, None)

    def write():
        _record(
            db,
            kind=kind,
            currency=currency,
            mission_id=mission_id,
            phase=FUNDING,
            actor_telegram_id=client_telegram_id,
            reference=reference,
            details=details,
            movements=[(*source, -amounts["total"]), (ESCROW, mission_id, amounts["total"])],
        )
        if also is not None:
            also(mission)
        mission.provider_telegram_id = provider_telegram_id
        mission.client_account_id = client_account_id
        mission.provider_account_id = provider_account_id
        mission.currency = currency
        mission.urgent = bool(urgent)
        mission.accepted_quote_ref = quote_ref
        mission.commission_amount = float(amounts["commission"])
        mission.tola_fee = 0.0
        mission.aggregator_fee = 0.0
        mission.total_client = float(amounts["total"])
        mission.net_provider = float(amounts["net"])
        mission.payment_status = "paid_escrow"
        _set_status(mission, "confirmed")

    _write(db, mission_id, FUNDING, matches, write)
    return db.get(BotMission, mission_id)


# --- Déroulement de la mission -----------------------------------------------


def start_mission(db: Session, mission_id: int, provider_telegram_id: int) -> BotMission:
    mission = _lock_mission(db, mission_id)
    if mission.provider_telegram_id != provider_telegram_id:
        raise MoneyError("not_mission_provider", 403, mission)
    if mission.status == "in_progress":
        return mission
    _require_open_escrow(db, mission)
    if mission.status != "confirmed":
        raise MoneyError("invalid_state", mission=mission)
    _set_status(mission, "in_progress")
    db.commit()
    return mission


def finish_mission(db: Session, mission_id: int, provider_telegram_id: int) -> BotMission:
    mission = _lock_mission(db, mission_id)
    if mission.provider_telegram_id != provider_telegram_id:
        raise MoneyError("not_mission_provider", 403, mission)
    if mission.status == "awaiting_confirmation":
        return mission
    _require_open_escrow(db, mission)
    if mission.status != "in_progress":
        raise MoneyError("invalid_state", mission=mission)
    _set_status(mission, "awaiting_confirmation")
    db.commit()
    return mission


def _require_open_escrow(db: Session, mission: BotMission) -> None:
    """Payée, ni en litige ni réglée."""
    if mission_operation(db, mission.mission_id, SETTLEMENT) is not None:
        raise MoneyError("already_settled", mission=mission)
    if mission.status == "disputed":
        raise MoneyError("mission_disputed", mission=mission)
    if mission_operation(db, mission.mission_id, FUNDING) is None:
        raise MoneyError("not_paid", mission=mission)


# --- Libération ---------------------------------------------------------------


def _release_details(amounts: dict[str, Decimal]) -> dict:
    return {"provider_amount": str(amounts["net"]), "client_amount": "0.00", "platform_amount": str(amounts["commission"])}


def _release_movements(mission: BotMission, amounts: dict[str, Decimal]) -> list:
    return [
        (ESCROW, mission.mission_id, -amounts["total"]),
        (WALLET, mission.provider_account_id, amounts["net"]),
        (PLATFORM, None, amounts["commission"]),
    ]


def _settle(
    db: Session,
    mission: BotMission,
    *,
    kind: str,
    actor: int | None,
    movements: list,
    details: dict,
    payment_status: str,
    status: str,
    matches,
) -> BotMission:
    """Enregistre le règlement et le nouvel état en une transaction, puis
    recalcule les statistiques du prestataire."""
    mission_id = mission.mission_id

    def write():
        _record(
            db,
            kind=kind,
            currency=mission.currency,
            mission_id=mission_id,
            phase=SETTLEMENT,
            actor_telegram_id=actor,
            details=details,
            movements=movements,
        )
        mission.payment_status = payment_status
        _set_status(mission, status)

    _write(db, mission_id, SETTLEMENT, matches, write)
    return _after_settlement(db, mission_id)


def confirm_completion(db: Session, mission_id: int, client_telegram_id: int) -> BotMission:
    """Le client confirme la fin : le prestataire est payé."""
    mission = _lock_mission(db, mission_id)
    if mission.telegram_id != client_telegram_id:
        raise MoneyError("not_mission_client", 403, mission)
    settlement = mission_operation(db, mission_id, SETTLEMENT)
    if settlement is not None:
        if settlement.kind == "release":
            return mission
        raise MoneyError("already_settled", mission=mission)
    _require_open_escrow(db, mission)
    if mission.status != "awaiting_confirmation":
        raise MoneyError("invalid_state", mission=mission)
    amounts = _funded_amounts(db, mission)
    return _settle(
        db,
        mission,
        kind="release",
        actor=client_telegram_id,
        movements=_release_movements(mission, amounts),
        details=_release_details(amounts),
        payment_status="released",
        status="completed",
        matches=lambda operation: operation.kind == "release",
    )


def auto_release(db: Session, mission_id: int, now: datetime | None = None) -> BotMission:
    """Libération automatique : seulement une mission en attente de
    confirmation depuis plus de 24 h, donc jamais une mission en litige."""
    now = now or _utcnow()
    mission = _lock_mission(db, mission_id)
    _require_open_escrow(db, mission)
    if mission.status != "awaiting_confirmation" or mission.status_changed_at > now - AUTO_RELEASE_DELAY:
        raise MoneyError("invalid_state", mission=mission)
    amounts = _funded_amounts(db, mission)
    return _settle(
        db,
        mission,
        kind="auto_release",
        actor=None,
        movements=_release_movements(mission, amounts),
        details=_release_details(amounts),
        payment_status="released",
        status="completed",
        matches=lambda operation: False,
    )


# --- Litige -------------------------------------------------------------------


def open_dispute(db: Session, mission_id: int, client_telegram_id: int, reason: str) -> BotMission:
    """Gèle les fonds : plus aucune libération (manuelle ou automatique) tant
    que l'admin n'a pas tranché."""
    reason = (reason or "").strip()
    if not reason or len(reason) > MAX_DISPUTE_REASON_LENGTH:
        raise MoneyError("invalid_reason", 400)
    mission = _lock_mission(db, mission_id)
    if mission.telegram_id != client_telegram_id:
        raise MoneyError("not_mission_client", 403, mission)
    if mission.status == "disputed":
        return mission
    if mission_operation(db, mission_id, SETTLEMENT) is not None:
        raise MoneyError("already_settled", mission=mission)
    if mission_operation(db, mission_id, FUNDING) is None:
        raise MoneyError("not_paid", mission=mission)
    if mission.status not in DISPUTABLE_STATUSES:
        raise MoneyError("invalid_state", mission=mission)
    now = _utcnow()
    mission.dispute_reason = reason
    mission.dispute_opened_at = now
    mission.dispute_deadline = now + DISPUTE_RESOLUTION_DELAY
    _set_status(mission, "disputed")
    db.commit()
    _recompute_stats(db, mission)
    return db.get(BotMission, mission_id)


def resolve_dispute(
    db: Session,
    mission_id: int,
    *,
    decision: str,
    admin_telegram_id: int,
    provider_percentage=None,
) -> BotMission:
    """Décision admin sur un litige : rembourser le client (tout, frais
    compris), payer le prestataire, ou partager le net du prestataire (la
    plateforme garde sa commission)."""
    if decision not in DISPUTE_DECISIONS:
        raise MoneyError("invalid_decision", 400)
    percentage = None
    if decision == "split":
        try:
            percentage = Decimal(str(provider_percentage))
        except (InvalidOperation, ValueError, TypeError) as error:
            raise MoneyError("invalid_percentage", 400) from error
        if not percentage.is_finite() or not (Decimal("0") <= percentage <= Decimal("100")):
            raise MoneyError("invalid_percentage", 400)
        percentage = percentage.quantize(CENT, rounding=ROUND_HALF_UP)

    kind = {"refund": "refund", "release": "dispute_release", "split": "split"}[decision]

    def matches(operation: MoneyOperation) -> bool:
        return operation.kind == kind and (operation.details or {}).get("percentage") == (
            str(percentage) if percentage is not None else None
        )

    mission = _lock_mission(db, mission_id)
    settlement = mission_operation(db, mission_id, SETTLEMENT)
    if settlement is not None:
        if matches(settlement):
            return mission
        raise MoneyError("already_settled", mission=mission)
    if mission.status != "disputed":
        raise MoneyError("not_disputed", mission=mission)
    amounts = _funded_amounts(db, mission)

    if decision == "refund":
        provider_amount, client_amount, platform_amount = ZERO, amounts["total"], ZERO
        movements = [(ESCROW, mission_id, -amounts["total"]), (WALLET, mission.client_account_id, amounts["total"])]
        payment_status, status = "refunded", "cancelled"
    elif decision == "release":
        provider_amount, client_amount, platform_amount = amounts["net"], ZERO, amounts["commission"]
        movements = _release_movements(mission, amounts)
        payment_status, status = "released", "completed"
    else:
        provider_amount = (amounts["net"] * percentage / Decimal("100")).quantize(CENT, rounding=ROUND_HALF_UP)
        client_amount = amounts["net"] - provider_amount
        platform_amount = amounts["commission"]
        movements = [
            (ESCROW, mission_id, -amounts["total"]),
            (WALLET, mission.provider_account_id, provider_amount),
            (WALLET, mission.client_account_id, client_amount),
            (PLATFORM, None, platform_amount),
        ]
        payment_status, status = "split", "completed"

    details = {
        "decision": decision,
        "provider_amount": str(provider_amount),
        "client_amount": str(client_amount),
        "platform_amount": str(platform_amount),
    }
    if percentage is not None:
        details["percentage"] = str(percentage)
    return _settle(
        db,
        mission,
        kind=kind,
        actor=admin_telegram_id,
        movements=movements,
        details=details,
        payment_status=payment_status,
        status=status,
        matches=matches,
    )


# --- Après règlement ------------------------------------------------------------


def _recompute_stats(db: Session, mission: BotMission) -> None:
    # Import local : crud importe déjà les modèles, pas ce module.
    from backend.app.crud import _recompute_provider_stats

    if mission.provider_telegram_id is not None:
        _recompute_provider_stats(db, mission.provider_telegram_id)


def _after_settlement(db: Session, mission_id: int) -> BotMission:
    mission = db.get(BotMission, mission_id)
    _recompute_stats(db, mission)
    return db.get(BotMission, mission_id)


# --- Soldes d'ouverture (migration) ----------------------------------------------


def record_opening_balance(db: Session, account_id: int, currency: str, amount) -> MoneyOperation | None:
    """Reprise d'un solde existant avant le registre (`account_id` : compte
    Nexis). Ne valide pas : l'appelant gère sa transaction."""
    amount = to_money(amount)
    if amount == ZERO:
        return None
    return _record(
        db,
        kind="opening_balance",
        currency=currency,
        details={"account_id": account_id},
        movements=[(EXTERNAL, None, -amount), (WALLET, account_id, amount)],
    )


# --- Mobile Money réel : frais, trop-perçu, retraits ----------------------------
# Appelés par backend/app/mobile_money.py, dans sa transaction : ces fonctions
# écrivent sans valider (CONCEPTION_MOBILE_MONEY.md).


def record_collection_fee(db: Session, *, mission_id: int, currency: str, fee, reference: str | None) -> None:
    """Frais d'encaissement de l'agrégateur, à la charge de Nexis Hub (décision
    de Ben) : prélevés sur le compte de la plateforme."""
    fee = to_money(fee)
    if fee < ZERO:
        raise MoneyError("invalid_amount", 400)
    if fee == ZERO:
        return
    _record(
        db,
        kind="collection_fee",
        currency=currency,
        reference=reference,
        details={"mission_id": mission_id},
        movements=[(PLATFORM, None, -fee), (FEES, None, fee)],
    )


def record_overpayment(db: Session, *, account_id: int, currency: str, amount, reference: str | None, mission_id: int) -> None:
    """Argent reçu pour une mission déjà payée (confirmation en retard ou en
    double) : jamais perdu, crédité au wallet du client, retirable seulement
    après vérification admin."""
    amount = to_money(amount)
    _record(
        db,
        kind="overpayment",
        currency=currency,
        reference=reference,
        details={"mission_id": mission_id},
        movements=[(EXTERNAL, None, -amount), (WALLET, account_id, amount)],
    )


def withdrawable_without_review(db: Session, account_id: int, currency: str) -> Decimal:
    """Part du wallet retirable sans vérification admin : le solde moins tout
    ce que le compte a reçu en remboursement, partage de litige (part client)
    ou trop-perçu (décision de Ben : ces fonds se retirent après vérification)."""
    client_credit_kinds = ("refund", "split", "overpayment")
    reviewed = (
        db.query(func.coalesce(func.sum(LedgerEntry.amount), 0))
        .join(MoneyOperation, MoneyOperation.id == LedgerEntry.operation_id)
        .outerjoin(BotMission, BotMission.mission_id == MoneyOperation.mission_id)
        .filter(
            LedgerEntry.account_type == WALLET,
            LedgerEntry.account_id == account_id,
            LedgerEntry.currency == currency,
            LedgerEntry.amount > 0,
            MoneyOperation.kind.in_(client_credit_kinds),
            # Dans un partage, seule la part du client est concernée.
            (MoneyOperation.kind != "split") | (BotMission.client_account_id == account_id),
        )
        .scalar()
    )
    return max(ZERO, balance(db, WALLET, account_id, currency) - to_money(reviewed))


def hold_payout(db: Session, payout: Payout) -> None:
    """Bloque le montant d'un retrait : wallet → payout_pending. Verrouille le
    compte pour que deux retraits simultanés ne dépassent jamais le solde."""
    db.get(NexisAccount, payout.account_id, with_for_update=True)
    if balance(db, WALLET, payout.account_id, payout.currency) < payout.amount:
        raise MoneyError("insufficient_balance")
    _record(
        db,
        kind="payout_hold",
        currency=payout.currency,
        details={"payout_id": payout.id},
        movements=[(WALLET, payout.account_id, -to_money(payout.amount)), (PAYOUT_PENDING, payout.id, to_money(payout.amount))],
    )


def complete_payout(db: Session, payout: Payout, reference: str | None) -> None:
    """Versement confirmé par l'agrégateur : l'argent sort, frais à la charge
    du prestataire (décision de Ben)."""
    amount, fee = to_money(payout.amount), to_money(payout.fee)
    _record(
        db,
        kind="payout",
        currency=payout.currency,
        reference=reference,
        details={"payout_id": payout.id},
        movements=[(PAYOUT_PENDING, payout.id, -amount), (EXTERNAL, None, amount - fee), (FEES, None, fee)],
    )


def release_payout(db: Session, payout: Payout, kind: str) -> None:
    """Retrait refusé (`payout_rejected`) ou échoué (`payout_failed`) :
    l'argent bloqué revient au wallet, toujours."""
    amount = to_money(payout.amount)
    _record(
        db,
        kind=kind,
        currency=payout.currency,
        details={"payout_id": payout.id},
        movements=[(PAYOUT_PENDING, payout.id, -amount), (WALLET, payout.account_id, amount)],
    )
