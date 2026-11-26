"""Interrupteurs d'arrêt Mobile Money : couper les encaissements ou les
versements sans redéployer (fraude, agrégateur en panne, anomalie du
registre).

Deux interrupteurs, enregistrés en base (`money_switches`) :

- `collections` (encaissements) : coupé, aucune nouvelle demande de paiement
  ne part vers l'agrégateur. Une demande déjà partie (le téléphone du client
  a peut-être déjà sonné) reste relue et confirmée : l'argent qui arrive
  n'est jamais ignoré.
- `payouts` (versements) : coupé, aucun ordre de versement ne part, et
  aucune nouvelle demande de retrait n'est acceptée. Un retrait déjà validé
  qui n'est pas encore parti reste bloqué dans le registre, sans être rendu
  ni envoyé ; il part par la vérification de secours une fois les versements
  rouverts. Un retrait déjà envoyé reste relu chez l'agrégateur. Refuser un
  retrait (rendre l'argent au wallet) reste possible.

Couper ou rouvrir demande une raison et laisse une trace jamais effacée
(`money_switch_events`). Depuis Telegram (admins, `/couper`, `/rouvrir`), ou
depuis le serveur si le bot ne répond plus :

    python -m backend.app.interrupteurs couper encaissements --raison "..."
    python -m backend.app.interrupteurs rouvrir versements --raison "..."
    python -m backend.app.interrupteurs etat
"""

import argparse
import logging
import sys
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.ledger import MoneyError
from backend.app.models import MONEY_SWITCHES, MoneySwitch, MoneySwitchEvent

logger = logging.getLogger(__name__)

COLLECTIONS, PAYOUTS = MONEY_SWITCHES
# Noms français, pour la commande serveur et le bot.
FRENCH_NAMES = {"encaissements": COLLECTIONS, "versements": PAYOUTS}
LABELS = {COLLECTIONS: "encaissements", PAYOUTS: "versements"}
MAX_REASON_LENGTH = 500


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _check_name(name: str) -> str:
    if name not in MONEY_SWITCHES:
        raise MoneyError("unknown_switch", 404)
    return name


def is_open(db: Session, name: str) -> bool:
    """Le flux est-il ouvert ? Jamais coupé (aucune ligne) : ouvert. Une base
    injoignable lève une erreur : la demande échoue, rien ne part."""
    row = db.get(MoneySwitch, _check_name(name))
    return True if row is None else row.is_open


def state(db: Session) -> list[dict]:
    rows = {row.name: row for row in db.query(MoneySwitch)}
    result = []
    for name in MONEY_SWITCHES:
        row = rows.get(name)
        result.append(
            {
                "name": name,
                "is_open": True if row is None else row.is_open,
                "changed_at": row.changed_at.isoformat() if row else None,
                "changed_by_telegram_id": row.changed_by_telegram_id if row else None,
                "reason": row.reason if row else None,
            }
        )
    return result


def _locked_row(db: Session, name: str, now: datetime, reason: str) -> MoneySwitch:
    """Ligne de l'interrupteur, verrouillée jusqu'au commit : deux changements
    simultanés passent l'un après l'autre. Créée ouverte au premier
    changement."""
    row = db.get(MoneySwitch, name, with_for_update=True)
    if row is not None:
        return row
    db.add(MoneySwitch(name=name, is_open=True, changed_at=now, reason=reason))
    try:
        db.flush()
    except IntegrityError:
        # Créée au même instant par un autre changement : on prend la sienne.
        db.rollback()
    return db.get(MoneySwitch, name, with_for_update=True, populate_existing=True)


def switch(
    db: Session, name: str, *, open: bool, reason: str, source: str, by_telegram_id: int | None = None
) -> tuple[MoneySwitch, bool]:
    """Coupe (`open=False`) ou rouvre un flux. Renvoie l'interrupteur et
    `changed` : déjà dans cet état, rien n'est écrit (ni journal)."""
    _check_name(name)
    reason = (reason or "").strip()
    if not reason or len(reason) > MAX_REASON_LENGTH:
        raise MoneyError("reason_required", 400)
    now = _utcnow()
    row = _locked_row(db, name, now, reason)
    if row.is_open == open:
        db.commit()  # rien écrit : libère le verrou
        return row, False
    row.is_open, row.changed_at, row.changed_by_telegram_id, row.reason = open, now, by_telegram_id, reason
    db.add(
        MoneySwitchEvent(name=name, is_open=open, at=now, by_telegram_id=by_telegram_id, source=source, reason=reason)
    )
    # Les autres admins sont prévenus dans la même transaction (tous, si le
    # changement vient du serveur).
    from backend.app import evenements, ledger

    admin_account_id = ledger.account_id_for(db, ledger.TELEGRAM, by_telegram_id) if by_telegram_id else None
    evenements.money_switch_changed(
        db,
        label=LABELS[name].capitalize(),
        state_text="rouverts" if open else "coupés",
        opened=open,
        admin_account_id=admin_account_id,
        source=source,
        reason=reason,
        changed_at=now,
    )
    db.commit()
    logger.warning(
        "Interrupteur %s %s par %s (%s) : %s",
        LABELS[name], "rouvert" if open else "coupé", by_telegram_id or "le serveur", source, reason,
    )
    return row, True


def main(argv: list[str] | None = None) -> int:
    from backend.app.database import SessionLocal

    parser = argparse.ArgumentParser(prog="python -m backend.app.interrupteurs")
    commandes = parser.add_subparsers(dest="commande", required=True)
    for nom, aide in (("couper", "coupe un flux Mobile Money"), ("rouvrir", "rouvre un flux Mobile Money")):
        commande = commandes.add_parser(nom, help=aide)
        commande.add_argument("flux", choices=sorted(FRENCH_NAMES))
        commande.add_argument("--raison", required=True)
    commandes.add_parser("etat", help="affiche l'état des deux interrupteurs")
    args = parser.parse_args(argv)

    with SessionLocal() as db:
        try:
            if args.commande == "etat":
                for item in state(db):
                    texte = "ouverts" if item["is_open"] else "COUPÉS"
                    depuis = f" depuis le {item['changed_at'][:16].replace('T', ' ')} UTC : {item['reason']}" if item["changed_at"] else ""
                    print(f"{LABELS[item['name']].capitalize()} : {texte}{depuis}")
                return 0
            row, changed = switch(
                db, FRENCH_NAMES[args.flux], open=args.commande == "rouvrir", reason=args.raison, source="cli"
            )
        except MoneyError as error:
            print("Une raison est obligatoire (500 caractères au plus)." if error.code == "reason_required" else error.code, file=sys.stderr)
            return 1
    texte = "ouverts" if row.is_open else "coupés"
    print(f"{args.flux.capitalize()} {texte}." if changed else f"{args.flux.capitalize()} déjà {texte} : rien n'a changé.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
