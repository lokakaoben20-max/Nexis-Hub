"""Admins de Nexis Hub : qui peut décider sur l'argent et les prestataires.

Plusieurs personnes peuvent être admin. Le rôle est enregistré en base
(`admin_roles`), rattaché au compte Nexis de la personne. Il n'existe que par
cette commande, qui laisse une trace (date et raison, jamais effacées) :

    python -m backend.app.admins ajouter <identifiant Telegram> --raison "..."
    python -m backend.app.admins retirer <identifiant Telegram> --raison "..."
    python -m backend.app.admins liste

Aucune route de l'API ne donne ni ne retire ce rôle. Un admin agit depuis
Telegram (le bot) : c'est son identifiant Telegram qui le désigne.
"""

import argparse
import logging
import sys
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app import ledger
from backend.app.models import AdminRole, ChannelIdentity

logger = logging.getLogger(__name__)

MAX_REASON_LENGTH = 500


class AdminError(Exception):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _active_role(db: Session, account_id: int) -> AdminRole | None:
    return db.query(AdminRole).filter(AdminRole.account_id == account_id, AdminRole.revoked_at.is_(None)).one_or_none()


def is_admin_account(db: Session, account_id: int | None) -> bool:
    return account_id is not None and _active_role(db, account_id) is not None


def is_admin_telegram(db: Session, telegram_id) -> bool:
    return is_admin_account(db, ledger.account_id_for(db, ledger.TELEGRAM, telegram_id))


def admin_telegram_ids(db: Session) -> list[int]:
    """Identifiants Telegram des admins actifs, pour leur envoyer les alertes."""
    rows = (
        db.query(ChannelIdentity.external_id)
        .join(AdminRole, AdminRole.account_id == ChannelIdentity.account_id)
        .filter(AdminRole.revoked_at.is_(None), ChannelIdentity.channel == ledger.TELEGRAM)
        .order_by(AdminRole.granted_at, AdminRole.id)
        .all()
    )
    return [int(external_id) for (external_id,) in rows]


def _reason(reason: str) -> str:
    reason = (reason or "").strip()
    if not reason or len(reason) > MAX_REASON_LENGTH:
        raise AdminError("Une raison est obligatoire (500 caractères au plus).")
    return reason


def _telegram_id(value) -> int:
    try:
        telegram_id = int(str(value).strip())
    except ValueError as error:
        raise AdminError("L'identifiant Telegram doit être un nombre.") from error
    if telegram_id <= 0:
        raise AdminError("L'identifiant Telegram doit être un nombre positif.")
    return telegram_id


def grant(db: Session, telegram_id, reason: str, now: datetime | None = None) -> AdminRole:
    """Donne le rôle admin. Déjà admin : rien ne change, le rôle existant est
    renvoyé."""
    telegram_id, reason = _telegram_id(telegram_id), _reason(reason)
    account_id = ledger.account_id_for(db, ledger.TELEGRAM, telegram_id, create=True)
    existing = _active_role(db, account_id)
    if existing is not None:
        return existing
    role = AdminRole(account_id=account_id, granted_at=now or _utcnow(), granted_reason=reason)
    db.add(role)
    try:
        db.commit()
    except IntegrityError:
        # Donné au même instant par une autre commande : c'est le même rôle.
        db.rollback()
        return _active_role(db, account_id)
    return role


def revoke(db: Session, telegram_id, reason: str, now: datetime | None = None) -> AdminRole:
    telegram_id, reason = _telegram_id(telegram_id), _reason(reason)
    account_id = ledger.account_id_for(db, ledger.TELEGRAM, telegram_id)
    role = _active_role(db, account_id) if account_id is not None else None
    if role is None:
        raise AdminError(f"{telegram_id} n'est pas admin.")
    role.revoked_at = now or _utcnow()
    role.revoked_reason = reason
    db.commit()
    return role


def main(argv: list[str] | None = None) -> int:
    from backend.app.database import SessionLocal

    parser = argparse.ArgumentParser(prog="python -m backend.app.admins")
    commandes = parser.add_subparsers(dest="commande", required=True)
    for nom, aide in (("ajouter", "donne le rôle admin"), ("retirer", "retire le rôle admin")):
        commande = commandes.add_parser(nom, help=aide)
        commande.add_argument("telegram_id")
        commande.add_argument("--raison", required=True)
    commandes.add_parser("liste", help="affiche les admins actifs")
    args = parser.parse_args(argv)

    with SessionLocal() as db:
        try:
            if args.commande == "ajouter":
                role = grant(db, args.telegram_id, args.raison)
                print(f"Admin : {args.telegram_id} (depuis le {role.granted_at:%d/%m/%Y %H:%M} UTC)")
                logger.warning("Rôle admin donné à %s : %s", args.telegram_id, args.raison)
            elif args.commande == "retirer":
                revoke(db, args.telegram_id, args.raison)
                print(f"Plus admin : {args.telegram_id}")
                logger.warning("Rôle admin retiré à %s : %s", args.telegram_id, args.raison)
            else:
                ids = admin_telegram_ids(db)
                for telegram_id in ids:
                    print(telegram_id)
                if not ids:
                    print("Aucun admin : personne ne peut décider sur l'argent ni les prestataires.")
                elif len(ids) < 2:
                    print("Un seul admin : une décision de litige contestée ne pourra pas être revue.")
        except AdminError as error:
            print(error, file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
