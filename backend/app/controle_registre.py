"""Contrôle d'une base restaurée (ou de la production), en lecture seule.

    python -m backend.app.controle_registre        (rôle `controle-registre` de l'image)

Sert au test de restauration hebdomadaire et à chaque exercice de reprise
(plan-deploiement-2026-11-07.md, section 6) : une sauvegarde ne compte que si
la base qu'elle redonne passe ce contrôle.

Vérifie, sans rien écrire (transaction en lecture seule sous Postgres) :

- le schéma est à la dernière migration du code (`sante.problemes_base`) ;
- toutes les règles du rapprochement quotidien (`reconciliation.reconcile`,
  seule source de ces règles) : chaque opération à somme nulle par devise,
  aucun solde négatif, escrow cohérent avec les missions, retraits et
  paiements Mobile Money cohérents ;
- et, en plus, la somme de tout le registre par devise (nulle en partie
  double).

Sortie : un résumé JSON (compteurs, dernière écriture, anomalies), code 0 si
tout est bon, 1 sinon.
"""

from __future__ import annotations

import json
import sys
from decimal import Decimal

from sqlalchemy import func, text

import nexis_config
from backend.app import database, reconciliation, sante
from backend.app.ledger import ZERO, to_money
from backend.app.models import LedgerEntry


def controler(session) -> dict:
    if session.get_bind().dialect.name == "postgresql":
        session.execute(text("SET TRANSACTION READ ONLY"))
    resultat: dict = {"problemes_schema": sante.problemes_base(session)}
    if resultat["problemes_schema"]:
        resultat["ok"] = False
        return resultat

    rapport = reconciliation.reconcile(session)
    sommes = {
        devise: to_money(total)
        for devise, total in session.query(LedgerEntry.currency, func.sum(LedgerEntry.amount)).group_by(LedgerEntry.currency)
    }
    anomalies = list(rapport.anomalies)
    for devise, total in sorted(sommes.items()):
        if total != ZERO:
            anomalies.append({"code": "registre_desequilibre", "detail": f"somme du registre {total} {devise} au lieu de 0"})

    derniere = session.query(func.max(LedgerEntry.created_at)).scalar()
    resultat.update(
        ok=not anomalies,
        revision=sante.revision_attendue(),
        ecritures=session.query(func.count(LedgerEntry.id)).scalar(),
        compteurs=rapport.counts,
        sommes_par_devise={devise: str(total) for devise, total in sorted(sommes.items())},
        derniere_ecriture=derniere.isoformat() if derniere else None,
        anomalies=anomalies,
    )
    return resultat


def main() -> int:
    nexis_config.verifier("migration")  # seule la base est nécessaire
    with database.SessionLocal() as session:
        try:
            resultat = controler(session)
        finally:
            session.rollback()
    print(json.dumps(resultat, ensure_ascii=False, indent=2, default=lambda v: str(v) if isinstance(v, Decimal) else v))
    return 0 if resultat["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
