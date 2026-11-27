"""Numéros de retrait : les seuls numéros vers lesquels l'argent sort.

Règles (décision de Ben, 2026-11-27) :

- la personne enregistre elle-même ses numéros (Airtel Money, Orange Money,
  M-Pesa ; plus tard une carte bancaire), jusqu'à `MAX_ACTIVE_DESTINATIONS` ;
  à chaque retrait elle choisit l'un d'eux. Jamais de numéro saisi pour un
  seul retrait ;
- ce qui touche à la sécurité se fait dans l'application (un Telegram ou un
  WhatsApp volé ne suffit pas) : seul le tout premier numéro du compte peut
  s'enregistrer depuis un bot (`first_only`) ; ajouter un autre numéro ou en
  retirer un se fait dans l'API de l'app (`backend/app/public.py`), par
  demande signée d'un téléphone autorisé à faire sortir de l'argent ;
- aucun contrôle du nom du titulaire : en RDC beaucoup de SIM ne sont pas au
  nom de la personne qui s'en sert ;
- protection si quelqu'un prend le compte : le tout premier numéro sert tout
  de suite ; tout numéro ajouté ensuite (même après avoir retiré l'ancien)
  n'est utilisable qu'après `NEW_DESTINATION_DELAY` (72 h). La personne est
  prévenue de chaque ajout : si ce n'est pas elle, elle a ce délai pour réagir ;
- un numéro retiré ne sert plus ; un retrait déjà demandé garde le numéro
  recopié au moment de la demande.

Toutes les écritures verrouillent le compte, comme `mobile_money.request_payout` :
un ajout et un retrait simultanés ne se croisent jamais.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app import evenements
from backend.app.ledger import MoneyError
from backend.app.models import NexisAccount, PayoutDestination

NEW_DESTINATION_DELAY = timedelta(hours=72)
# Numéros enregistrés (actifs) par compte.
MAX_ACTIVE_DESTINATIONS = 4


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _active(db: Session, account_id: int):
    return db.query(PayoutDestination).filter(
        PayoutDestination.account_id == account_id,
        PayoutDestination.status == "active",
    )


def active_destinations(db: Session, account_id: int) -> list[PayoutDestination]:
    return _active(db, account_id).order_by(PayoutDestination.id).all()


def add_destination(
    db: Session, *, account_id: int, operator: str, phone: str, first_only: bool = False
) -> PayoutDestination:
    """Enregistre un numéro. Le même numéro déjà enregistré est rendu tel
    quel (double envoi) : jamais deux lignes, jamais de délai remis à zéro.

    `first_only` (bots) : seulement le tout premier numéro du compte ; tout
    changement ensuite est refusé (`destination_change_in_app`)."""
    from backend.app.mobile_money import check_phone_and_operator

    check_phone_and_operator(phone, operator)
    db.get(NexisAccount, account_id, with_for_update=True)
    existing = _active(db, account_id).filter(
        PayoutDestination.operator == operator, PayoutDestination.phone == phone
    ).one_or_none()
    if existing is not None:
        db.commit()  # rien écrit : libère le verrou
        return existing
    # Le compte a-t-il déjà eu un numéro (même retiré depuis) ? Sinon retirer
    # l'ancien numéro puis en ajouter un suffirait à éviter le délai.
    had_one = db.query(
        db.query(PayoutDestination).filter(PayoutDestination.account_id == account_id).exists()
    ).scalar()
    if first_only and had_one:
        raise MoneyError("destination_change_in_app", 403)
    if _active(db, account_id).count() >= MAX_ACTIVE_DESTINATIONS:
        raise MoneyError("too_many_destinations")
    now = _utcnow()
    destination = PayoutDestination(
        account_id=account_id,
        kind="mobile_money",
        operator=operator,
        phone=phone,
        status="active",
        created_at=now,
        usable_after=now + NEW_DESTINATION_DELAY if had_one else None,
    )
    try:
        with db.begin_nested():
            db.add(destination)
            db.flush()
    except IntegrityError as error:
        # Index unique : le même numéro vient d'être ajouté par une autre
        # demande (impossible sous le verrou du compte, gardé par sécurité).
        raise MoneyError("destination_exists") from error
    evenements.payout_destination_added(db, destination)
    db.commit()
    return destination


def remove_destination(db: Session, *, account_id: int, destination_id: int) -> PayoutDestination:
    """La personne retire un de ses numéros (depuis l'application seulement).
    Celui d'un autre compte est « introuvable » : on ne dit jamais qu'il existe."""
    db.get(NexisAccount, account_id, with_for_update=True)
    destination = db.get(PayoutDestination, destination_id, with_for_update=True)
    if destination is None or destination.account_id != account_id:
        raise MoneyError("destination_not_found", 404)
    if destination.status == "active":
        destination.status, destination.removed_at = "removed", _utcnow()
    db.commit()  # déjà retiré : rien à faire (double clic)
    return destination


def usable_destination(db: Session, *, account_id: int, destination_id: int, now: datetime | None = None) -> PayoutDestination:
    """Numéro vers lequel ce compte peut retirer maintenant. À appeler sous
    le verrou du compte (`mobile_money.request_payout`) : le numéro est relu
    verrouillé, un retrait simultané ne le voit pas retiré à moitié."""
    destination = db.get(PayoutDestination, destination_id, with_for_update=True)
    if destination is None or destination.account_id != account_id or destination.status != "active":
        raise MoneyError("destination_not_found", 404)
    if destination.usable_after is not None and (now or _utcnow()) < destination.usable_after:
        raise MoneyError("destination_too_new")
    return destination
