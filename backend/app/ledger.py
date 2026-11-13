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

from backend.app.models import (
    BotMission,
    BotQuote,
    ChannelIdentity,
    DisputeDecision,
    LedgerEntry,
    MoneyOperation,
    NexisAccount,
    Payout,
)

CENT = Decimal("0.01")
ZERO = Decimal("0.00")
CURRENCIES = ("USD", "CDF")

STANDARD_COMMISSION_RATE = Decimal("0.10")
URGENT_COMMISSION_RATE = Decimal("0.15")
DISPUTE_RESOLUTION_DELAY = timedelta(hours=48)
# Délai pour signaler un problème après la fin de la mission (décidé par Ben
# le 2026-11-07) : sans confirmation ni litige, l'argent part au prestataire.
AUTO_RELEASE_DELAY = timedelta(hours=48)
MAX_DISPUTE_REASON_LENGTH = 1000
# Décision d'un litige en deux temps (décidé par Ben le 2026-11-08) : la
# décision de Nexis Hub n'est exécutée que 3 jours plus tard ; pendant ce
# délai le client ou le prestataire peut la contester, et l'argent reste gelé.
# Une contestation est revue par une autre personne de Nexis Hub, avec le
# même délai de réponse que l'ouverture d'un litige.
DISPUTE_CONTEST_WINDOW = timedelta(days=3)
DISPUTE_REVIEW_DELAY = DISPUTE_RESOLUTION_DELAY
FIRST_DECISION = 1
REVIEW_DECISION = 2

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
# WhatsApp, clients seulement (docs/ARCHITECTURE_WHATSAPP.md). L'identifiant
# est le BSUID que Meta attribue à chaque utilisateur pour l'entreprise
# (« business-scoped user ID », par exemple `CD.13491208655302741918`), et non
# le numéro : depuis 2026, Meta peut masquer le numéro d'un utilisateur qui a
# un nom d'utilisateur WhatsApp. Le numéro, quand Meta le donne, n'est que le
# numéro prouvé du compte.
WHATSAPP = "whatsapp"
# Application mobile Nexis : une seule identité `app` par compte, sous laquelle
# sont rangés ses téléphones (`devices`). Jamais acceptée comme acteur déclaré
# par en-têtes sur l'API des canaux de confiance : l'acteur `app` ne naît que
# d'une session vérifiée (app-mobile/plan-etape1-connexion-api).
APP = "app"

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


def telegram_id_of(db: Session, account_id: int | None) -> int | None:
    """Identifiant Telegram d'un compte, pour les colonnes d'adaptateur du
    canal Telegram (affichage du bot). Jamais utilisé pour une règle d'argent."""
    if account_id is None:
        return None
    identity = (
        db.query(ChannelIdentity)
        .filter(ChannelIdentity.account_id == account_id, ChannelIdentity.channel == TELEGRAM)
        .one_or_none()
    )
    return int(identity.external_id) if identity is not None else None


def wallet_balances(db: Session, account_id: int | None) -> dict[str, Decimal]:
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
    """Paiement et règlement enregistrés d'une mission, montants en texte, et
    décisions de litige (première décision puis révision éventuelle)."""
    state = {}
    for phase in (FUNDING, SETTLEMENT):
        operation = mission_operation(db, mission_id, phase)
        state[phase] = (
            {"kind": operation.kind, "reference": operation.reference, **(operation.details or {})}
            if operation is not None
            else None
        )
    state["dispute_decisions"] = [dispute_decision_view(decision) for decision in dispute_decisions(db, mission_id)]
    return state


def dispute_decisions(db: Session, mission_id: int) -> list[DisputeDecision]:
    return db.query(DisputeDecision).filter(DisputeDecision.mission_id == mission_id).order_by(DisputeDecision.round).all()


def dispute_decision_view(decision: DisputeDecision) -> dict:
    """Décision telle que le client, le prestataire et les canaux la lisent :
    montants figés en texte, échéances. Jamais l'identité de la personne de
    Nexis Hub qui a décidé."""

    def iso(value: datetime | None) -> str | None:
        return value.isoformat() if value is not None else None

    if decision.executed_at is not None:
        state = "executed"
    elif decision.contested_at is not None:
        state = "contested"
    else:
        state = "pending"
    return {
        "id": decision.id,
        "round": decision.round,
        "decision": decision.decision,
        "state": state,
        "percentage": str(decision.provider_percentage) if decision.provider_percentage is not None else None,
        "currency": decision.currency,
        "provider_amount": str(decision.provider_amount),
        "client_amount": str(decision.client_amount),
        "platform_amount": str(decision.platform_amount),
        "decided_at": iso(decision.decided_at),
        "execute_after": iso(decision.execute_after),
        "contested_at": iso(decision.contested_at),
        "contested_by": decision.contested_by_role,
        "executed_at": iso(decision.executed_at),
    }


# --- Écriture (privé) ---------------------------------------------------------


def _record(
    db: Session,
    *,
    kind: str,
    currency: str,
    movements: list[tuple[str, int | None, Decimal]],
    mission_id: int | None = None,
    phase: str | None = None,
    actor_account_id: int | None = None,
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
        actor_account_id=actor_account_id,
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


def require_mission_client(mission: BotMission, account_id: int) -> None:
    """Seul le compte client de la mission agit comme client. Une mission sans
    compte client rattaché est refusée : on n'accepte jamais par défaut."""
    if mission.client_account_id is None:
        raise MoneyError("mission_account_missing", mission=mission)
    if mission.client_account_id != account_id:
        raise MoneyError("not_mission_client", 403, mission)


def _require_provider(db: Session, mission: BotMission, account_id: int) -> None:
    """Le prestataire n'est fixé qu'au paiement : sans paiement, la mission
    n'a pas encore de prestataire. Payée sans compte prestataire : refus."""
    if mission.provider_account_id is None:
        if mission_operation(db, mission.mission_id, FUNDING) is None:
            raise MoneyError("not_paid", mission=mission)
        raise MoneyError("mission_account_missing", mission=mission)
    if mission.provider_account_id != account_id:
        raise MoneyError("not_mission_provider", 403, mission)


def funding_terms(db: Session, mission_id: int, quote_id: int, client_account_id: int) -> dict:
    """Ce qui sera payé, lu dans le backend et nulle part ailleurs : la mission
    (verrouillée jusqu'à la fin de la demande), son devis accepté, le
    prestataire de ce devis. Aucun canal ne fixe le montant, la devise ni le
    prestataire d'un paiement."""
    mission = db.get(BotMission, mission_id, with_for_update=True)
    if mission is None:
        raise MoneyError("mission_not_found", 404)
    require_mission_client(mission, client_account_id)
    quote = db.get(BotQuote, quote_id)
    if quote is None or quote.mission_id != mission_id or quote.status != "accepted":
        if mission_operation(db, mission_id, FUNDING) is not None:
            # Mission déjà payée (sur un autre devis) : c'est ce qu'il faut dire.
            raise MoneyError("already_paid", mission=mission)
        if quote is None or quote.mission_id != mission_id:
            raise MoneyError("quote_not_found", 404, mission)
        raise MoneyError("quote_not_accepted", mission=mission)
    if quote.provider_account_id is None:
        raise MoneyError("mission_account_missing", mission=mission)
    if quote.currency not in CURRENCIES:
        raise MoneyError("invalid_currency", 400, mission)
    return {
        "mission": mission,
        "quote_id": quote.id,
        "provider_account_id": quote.provider_account_id,
        "amount": quote.amount,
        "currency": quote.currency,
        "urgent": bool(mission.urgent),
    }


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
    client_account_id: int,
    quote_id: int,
    reference: str | None = None,
    also=None,
) -> BotMission:
    """Paie une mission en escrow, sur son devis accepté.

    Montant, devise, prestataire et urgence viennent du backend
    (`funding_terms`), jamais de la demande. `reference` : référence de
    l'agrégateur (paiement Mobile Money réel) ; `also(mission)` : écritures à
    valider dans la même transaction (statut de l'intention de paiement, frais
    d'agrégateur). La mission doit exister : un paiement n'en crée jamais."""
    if method not in PAYMENT_METHODS:
        raise MoneyError("invalid_method", 400)
    terms = funding_terms(db, mission_id, quote_id, client_account_id)
    mission = terms["mission"]
    provider_account_id = terms["provider_account_id"]
    currency = terms["currency"]
    urgent = terms["urgent"]
    quote_ref = terms["quote_id"]
    amounts = payment_amounts(terms["amount"], urgent)
    kind, reference_prefix = PAYMENT_METHODS[method]
    details = {
        "method": method,
        "quote_ref": quote_ref,
        "provider_account_id": provider_account_id,
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
        return (
            operation.kind == kind
            and _comparable_funding_details(db, operation.details) == details
            and operation.reference == reference
        )

    if provider_account_id == client_account_id:
        # Une même personne peut être cliente et prestataire, jamais sur la
        # même mission : elle se paierait elle-même.
        raise MoneyError("provider_is_client", mission=mission)
    provider_telegram_id = telegram_id_of(db, provider_account_id)
    if provider_telegram_id is None:
        # Les prestataires n'existent que sur Telegram (et la Mini App).
        raise MoneyError("provider_not_found", 404, mission)

    existing = mission_operation(db, mission_id, FUNDING)
    if existing is not None:
        if matches(existing):
            return mission
        raise MoneyError("already_paid", mission=mission)
    if mission.status not in FUNDABLE_STATUSES or mission.payment_status not in (None, "unpaid"):
        raise MoneyError("invalid_state", mission=mission)

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
            actor_account_id=client_account_id,
            actor_telegram_id=mission.telegram_id,
            reference=reference,
            details=details,
            movements=[(*source, -amounts["total"]), (ESCROW, mission_id, amounts["total"])],
        )
        if also is not None:
            also(mission)
        mission.provider_telegram_id = provider_telegram_id
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


def _comparable_funding_details(db: Session, details: dict | None) -> dict:
    """Détails d'un paiement enregistré, exprimés comme aujourd'hui. Les
    paiements antérieurs au passage aux comptes nommaient le prestataire par
    son identifiant Telegram : on le traduit pour qu'un rejeu identique reste
    reconnu, sans jamais réécrire l'opération enregistrée."""
    details = dict(details or {})
    if "provider_telegram_id" in details and "provider_account_id" not in details:
        details["provider_account_id"] = account_id_for(db, TELEGRAM, details.pop("provider_telegram_id"))
    return details


# --- Déroulement de la mission -----------------------------------------------


def start_mission(db: Session, mission_id: int, provider_account_id: int) -> BotMission:
    """Usage interne et tests : aucune route ne laisse le prestataire démarrer
    seul. Une mission démarre quand sa présence est confirmée par le client ou
    par le code de présence (backend.app.presence)."""
    mission = _lock_mission(db, mission_id)
    _require_provider(db, mission, provider_account_id)
    if mission.status == "in_progress":
        return mission
    begin_work(db, mission)
    db.commit()
    return mission


def begin_work(db: Session, mission: BotMission) -> None:
    """Passe une mission payée et confirmée en cours, sans valider : l'appelant
    tient le verrou de la mission et valide avec ses propres changements (la
    présence confirmée et le démarrage vont ensemble ou pas du tout)."""
    _require_open_escrow(db, mission)
    if mission.status != "confirmed":
        raise MoneyError("invalid_state", mission=mission)
    _set_status(mission, "in_progress")


def finish_mission(db: Session, mission_id: int, provider_account_id: int) -> BotMission:
    mission = _lock_mission(db, mission_id)
    _require_provider(db, mission, provider_account_id)
    if mission.status == "awaiting_confirmation":
        return mission
    _require_open_escrow(db, mission)
    if mission.status != "in_progress":
        raise MoneyError("invalid_state", mission=mission)
    _set_status(mission, "awaiting_confirmation")
    mission.release_after = mission.status_changed_at + AUTO_RELEASE_DELAY
    db.commit()
    return mission


def lock_mission(db: Session, mission_id: int) -> BotMission:
    return _lock_mission(db, mission_id)


def require_mission_provider(db: Session, mission: BotMission, account_id: int) -> None:
    _require_provider(db, mission, account_id)


def require_open_escrow(db: Session, mission: BotMission) -> None:
    _require_open_escrow(db, mission)


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
    actor_account_id: int | None,
    actor_telegram_id: int | None,
    movements: list,
    details: dict,
    payment_status: str,
    status: str,
    matches,
    before=None,
    on_recorded=None,
) -> BotMission:
    """Enregistre le règlement et le nouvel état en une transaction, puis
    recalcule les statistiques du prestataire. `before` écrit d'abord ce qui
    doit aller dans la même transaction ; `on_recorded(opération)` complète
    après l'écriture du règlement (décision de litige marquée exécutée)."""
    mission_id = mission.mission_id

    def write():
        if before is not None:
            before()
        operation = _record(
            db,
            kind=kind,
            currency=mission.currency,
            mission_id=mission_id,
            phase=SETTLEMENT,
            actor_account_id=actor_account_id,
            actor_telegram_id=actor_telegram_id,
            details=details,
            movements=movements,
        )
        mission.payment_status = payment_status
        _set_status(mission, status)
        if on_recorded is not None:
            on_recorded(operation)

    _write(db, mission_id, SETTLEMENT, matches, write)
    return _after_settlement(db, mission_id)


def confirm_completion(db: Session, mission_id: int, client_account_id: int) -> BotMission:
    """Le client confirme la fin : le prestataire est payé."""
    mission = _lock_mission(db, mission_id)
    require_mission_client(mission, client_account_id)
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
        actor_account_id=client_account_id,
        actor_telegram_id=mission.telegram_id,
        movements=_release_movements(mission, amounts),
        details=_release_details(amounts),
        payment_status="released",
        status="completed",
        matches=lambda operation: operation.kind == "release",
    )


def auto_release(db: Session, mission_id: int, now: datetime | None = None) -> BotMission:
    """Libération automatique : seulement une mission en attente de
    confirmation dont l'échéance `release_after` est passée, donc jamais une
    mission en litige. Sans échéance enregistrée, rien n'est versé."""
    now = now or _utcnow()
    mission = _lock_mission(db, mission_id)
    _require_open_escrow(db, mission)
    if mission.status != "awaiting_confirmation" or mission.release_after is None or mission.release_after > now:
        raise MoneyError("invalid_state", mission=mission)
    amounts = _funded_amounts(db, mission)
    return _settle(
        db,
        mission,
        kind="auto_release",
        actor_account_id=None,
        actor_telegram_id=None,
        movements=_release_movements(mission, amounts),
        details=_release_details(amounts),
        payment_status="released",
        status="completed",
        matches=lambda operation: False,
    )


# --- Litige -------------------------------------------------------------------


def open_dispute(db: Session, mission_id: int, client_account_id: int, reason: str) -> BotMission:
    """Gèle les fonds : plus aucune libération (manuelle ou automatique) tant
    que l'admin n'a pas tranché."""
    reason = (reason or "").strip()
    if not reason or len(reason) > MAX_DISPUTE_REASON_LENGTH:
        raise MoneyError("invalid_reason", 400)
    mission = _lock_mission(db, mission_id)
    require_mission_client(mission, client_account_id)
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


def dispute_split_amounts(amounts: dict[str, Decimal], percentage: Decimal) -> dict[str, Decimal]:
    """Partage au prorata (décidé par Ben le 2026-11-08) pour un pourcentage p
    versé au prestataire : le prestataire reçoit son net × p, Nexis Hub garde
    sa commission × p, chacun arrondi au centime, et le client récupère le
    reste du total, frais compris. Le reste est calculé par soustraction : la
    somme des mouvements vaut toujours exactement zéro."""
    ratio = percentage / Decimal("100")
    provider_amount = (amounts["net"] * ratio).quantize(CENT, rounding=ROUND_HALF_UP)
    platform_amount = (amounts["commission"] * ratio).quantize(CENT, rounding=ROUND_HALF_UP)
    return {
        "provider_amount": provider_amount,
        "platform_amount": platform_amount,
        "client_amount": amounts["total"] - provider_amount - platform_amount,
    }


def _decision_percentage(decision: str, provider_percentage) -> Decimal | None:
    if decision not in DISPUTE_DECISIONS:
        raise MoneyError("invalid_decision", 400)
    if decision != "split":
        return None
    try:
        percentage = Decimal(str(provider_percentage))
    except (InvalidOperation, ValueError, TypeError) as error:
        raise MoneyError("invalid_percentage", 400) from error
    if not percentage.is_finite() or not (Decimal("0") <= percentage <= Decimal("100")):
        raise MoneyError("invalid_percentage", 400)
    return percentage.quantize(CENT, rounding=ROUND_HALF_UP)


def _decision_amounts(amounts: dict[str, Decimal], decision: str, percentage: Decimal | None) -> dict[str, Decimal]:
    if decision == "refund":
        return {"provider_amount": ZERO, "client_amount": amounts["total"], "platform_amount": ZERO}
    if decision == "release":
        return {"provider_amount": amounts["net"], "client_amount": ZERO, "platform_amount": amounts["commission"]}
    return dispute_split_amounts(amounts, percentage)


def _same_decision(row: DisputeDecision, decision: str, percentage: Decimal | None) -> bool:
    stored = row.provider_percentage.quantize(CENT) if row.provider_percentage is not None else None
    return row.decision == decision and stored == percentage


def decide_dispute(
    db: Session,
    mission_id: int,
    *,
    decision: str,
    admin_account_id: int,
    admin_telegram_id: int | None,
    provider_percentage=None,
    now: datetime | None = None,
) -> BotMission:
    """Décision de Nexis Hub sur un litige : rembourser le client (tout, frais
    compris), payer le prestataire, ou partager au prorata.

    - Sans décision : c'est la première décision. Ses montants sont figés,
      l'argent reste gelé, et elle ne sera exécutée qu'au bout de 3 jours
      (`execute_dispute_decision`), sauf contestation.
    - Décision contestée : c'est la révision, par une autre personne que celle
      qui a pris la première décision (`same_reviewer` sinon). Elle est finale
      et exécutée tout de suite, dans la même transaction.

    Un rejeu identique renvoie l'état enregistré ; une décision différente
    alors qu'une décision attend son exécution est refusée
    (`decision_pending`)."""
    percentage = _decision_percentage(decision, provider_percentage)
    now = now or _utcnow()
    mission = _lock_mission(db, mission_id)
    decisions = {row.round: row for row in dispute_decisions(db, mission_id)}
    first, review = decisions.get(FIRST_DECISION), decisions.get(REVIEW_DECISION)

    # Rejeu de la dernière décision prise (double clic, réseau coupé) : on
    # renvoie l'état enregistré. Une première décision contestée n'est plus
    # « la dernière » : la redemander, c'est demander une révision.
    latest = review if review is not None else (first if first is not None and first.contested_at is None else None)
    if latest is not None and latest.decided_by_account_id == admin_account_id and _same_decision(latest, decision, percentage):
        return mission

    if mission_operation(db, mission_id, SETTLEMENT) is not None:
        raise MoneyError("already_settled", mission=mission)
    if mission.status != "disputed":
        raise MoneyError("not_disputed", mission=mission)
    if first is not None and first.contested_at is None:
        raise MoneyError("decision_pending", mission=mission)
    if first is not None and first.decided_by_account_id == admin_account_id:
        raise MoneyError("same_reviewer", 403, mission)

    funded = _funded_amounts(db, mission)
    split = _decision_amounts(funded, decision, percentage)
    row = DisputeDecision(
        mission_id=mission_id,
        round=FIRST_DECISION if first is None else REVIEW_DECISION,
        decision=decision,
        provider_percentage=percentage,
        currency=mission.currency,
        provider_amount=split["provider_amount"],
        client_amount=split["client_amount"],
        platform_amount=split["platform_amount"],
        decided_by_account_id=admin_account_id,
        decided_by_telegram_id=admin_telegram_id,
        decided_at=now,
        execute_after=now + DISPUTE_CONTEST_WINDOW if first is None else now,
    )

    if first is None:
        try:
            db.add(row)
            db.commit()
        except IntegrityError:
            # Décision enregistrée au même instant par une autre demande : un
            # rejeu identique est accepté, toute autre décision attend.
            db.rollback()
            stored = next((r for r in dispute_decisions(db, mission_id) if r.round == FIRST_DECISION), None)
            mission = db.get(BotMission, mission_id)
            if stored is not None and stored.decided_by_account_id == admin_account_id and _same_decision(stored, decision, percentage):
                return mission
            raise MoneyError("decision_pending", mission=mission) from None
        return db.get(BotMission, mission_id)

    def add_review():
        db.add(row)
        db.flush()

    return _execute(db, mission, row, now=now, before=add_review)


def contest_dispute_decision(
    db: Session, mission_id: int, account_id: int, reason: str, now: datetime | None = None
) -> BotMission:
    """Le client ou le prestataire de la mission conteste la première
    décision, une seule fois, avant son exécution. L'argent reste gelé et la
    révision a le délai de réponse habituel (48 h)."""
    reason = (reason or "").strip()
    if not reason or len(reason) > MAX_DISPUTE_REASON_LENGTH:
        raise MoneyError("invalid_reason", 400)
    now = now or _utcnow()
    mission = _lock_mission(db, mission_id)
    if account_id == mission.client_account_id:
        role = "client"
    elif account_id is not None and account_id == mission.provider_account_id:
        role = "provider"
    else:
        raise MoneyError("not_mission_party", 403, mission)

    first = next((row for row in dispute_decisions(db, mission_id) if row.round == FIRST_DECISION), None)
    if first is None:
        raise MoneyError("no_decision", mission=mission)
    if first.contested_at is not None:
        if first.contested_by_account_id == account_id:
            return mission
        raise MoneyError("already_contested", mission=mission)
    if first.executed_at is not None or mission_operation(db, mission_id, SETTLEMENT) is not None:
        raise MoneyError("decision_already_executed", mission=mission)
    if now >= first.execute_after:
        raise MoneyError("contest_window_closed", mission=mission)

    first.contested_by_account_id = account_id
    first.contested_by_role = role
    first.contested_at = now
    first.contest_reason = reason
    # Le délai de réponse repart pour la révision, avec ses alertes.
    mission.dispute_deadline = now + DISPUTE_REVIEW_DELAY
    mission.dispute_overdue_alerted_at = None
    db.commit()
    return db.get(BotMission, mission_id)


def execute_dispute_decision(db: Session, decision_id: int, now: datetime | None = None) -> BotMission:
    """Exécute une première décision non contestée dont le délai de
    contestation est passé (tâche du planificateur). Tout est revérifié sous
    le verrou de la mission : une contestation arrivée juste avant gagne, et
    une décision déjà exécutée ne l'est jamais deux fois."""
    now = now or _utcnow()
    row = db.get(DisputeDecision, decision_id)
    if row is None:
        raise MoneyError("decision_not_found", 404)
    mission = _lock_mission(db, row.mission_id)
    db.refresh(row)
    if row.executed_at is not None:
        return mission
    if row.contested_at is not None:
        raise MoneyError("decision_contested", mission=mission)
    if now < row.execute_after:
        raise MoneyError("decision_not_due", mission=mission)
    return _execute(db, mission, row, now=now)


def _execute(db: Session, mission: BotMission, row: DisputeDecision, *, now: datetime, before=None) -> BotMission:
    """Écrit le règlement d'une décision avec ses montants figés et marque la
    décision exécutée, en une transaction."""
    mission_id = mission.mission_id
    if mission_operation(db, mission_id, SETTLEMENT) is not None:
        raise MoneyError("already_settled", mission=mission)
    if mission.status != "disputed":
        raise MoneyError("not_disputed", mission=mission)
    funded = _funded_amounts(db, mission)
    provider_amount, client_amount, platform_amount = row.provider_amount, row.client_amount, row.platform_amount
    if provider_amount + client_amount + platform_amount != funded["total"]:
        # Montants figés incohérents avec le paiement : ne peut venir que d'un bug.
        raise RuntimeError(f"Décision {row.id} : montants {provider_amount}/{client_amount}/{platform_amount} ≠ {funded['total']}")

    kind = {"refund": "refund", "release": "dispute_release", "split": "split"}[row.decision]
    movements = [
        (ESCROW, mission_id, -funded["total"]),
        (WALLET, mission.provider_account_id, provider_amount),
        (WALLET, mission.client_account_id, client_amount),
        (PLATFORM, None, platform_amount),
    ]
    payment_status, status = {
        "refund": ("refunded", "cancelled"),
        "release": ("released", "completed"),
        "split": ("split", "completed"),
    }[row.decision]
    details = {
        "decision": row.decision,
        "decision_round": row.round,
        "provider_amount": str(provider_amount),
        "client_amount": str(client_amount),
        "platform_amount": str(platform_amount),
    }
    if row.provider_percentage is not None:
        details["percentage"] = str(row.provider_percentage.quantize(CENT))

    def mark_executed(operation: MoneyOperation) -> None:
        row.executed_at = now
        row.executed_operation_id = operation.id

    def matches(operation: MoneyOperation) -> bool:
        # Une exécution concurrente de la même décision a déjà écrit le règlement.
        return (operation.details or {}).get("decision_round") == row.round and (operation.details or {}).get("decision") == row.decision

    return _settle(
        db,
        mission,
        kind=kind,
        actor_account_id=row.decided_by_account_id,
        actor_telegram_id=row.decided_by_telegram_id,
        movements=movements,
        details=details,
        payment_status=payment_status,
        status=status,
        matches=matches,
        before=before,
        on_recorded=mark_executed,
    )


# --- Après règlement ------------------------------------------------------------


def _recompute_stats(db: Session, mission: BotMission) -> None:
    # Import local : crud importe déjà les modèles, pas ce module.
    from backend.app.crud import _recompute_provider_stats

    if mission.provider_telegram_id is not None:
        _recompute_provider_stats(db, mission.provider_telegram_id, mission.provider_account_id)


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


def record_mismatch_credit(
    db: Session, *, account_id: int, currency: str, amount, reference: str | None, mission_id: int, admin_telegram_id: int
) -> None:
    """Argent reçu avec un montant différent de la demande, porté au wallet du
    client sur décision de l'admin (`mobile_money.resolve_mismatch`). Comme
    un trop-perçu, il ne se retire qu'après vérification admin."""
    amount = to_money(amount)
    if amount <= ZERO:
        raise MoneyError("invalid_amount", 400)
    _record(
        db,
        kind="mismatch_credit",
        currency=currency,
        reference=reference,
        actor_telegram_id=admin_telegram_id,
        details={"mission_id": mission_id},
        movements=[(EXTERNAL, None, -amount), (WALLET, account_id, amount)],
    )


def withdrawable_without_review(db: Session, account_id: int, currency: str) -> Decimal:
    """Part du wallet retirable sans vérification admin : le solde moins tout
    ce que le compte a reçu en remboursement, partage de litige (part client)
    trop-perçu ou paiement à montant différent (décision de Ben : ces fonds se
    retirent après vérification)."""
    client_credit_kinds = ("refund", "split", "overpayment", "mismatch_credit")
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
        actor_account_id=payout.account_id,
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
