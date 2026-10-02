"""Recopie les soldes wallet de db.py (SQLite legacy) vers le backend V5.

backfill_users_to_backend.py et backfill_providers_to_backend.py recopient
l'identité des comptes, jamais leur wallet : tout solde antérieur au backend
(ou dérivé pendant une panne, avant la file `backend_outbox`) reste faux côté
Postgres, ce que relève audit_backend_parity.py.

À lancer à la main, après les deux backfills d'identité (un compte absent du
backend est ignoré). Par défaut, simulation : affiche les écarts sans rien
écrire.

    .venv\\Scripts\\python.exe backfill_wallets_to_backend.py           # simulation
    .venv\\Scripts\\python.exe backfill_wallets_to_backend.py --apply   # écrit

Écrase le solde backend par celui de db.py, qui reste la source de vérité.
Attention : une libération faite par le backend seul (auto-libération Celery
à 24h, que db.py ne voit pas) serait effacée -- relire la simulation avant
--apply. Refuse de tourner tant que `backend_outbox` n'est pas vide : un
mouvement encore en file serait sinon compté deux fois (une fois par la
copie, une fois au rejeu).
"""

import sys

from backend.app.database import SessionLocal
from backend.app.models import BotProvider, BotUser
from db import count_backend_outbox, get_all_providers, get_all_users

WALLET_FIELDS = ("wallet_balance_usd", "wallet_balance_cdf")


def _copy_wallets(db, model, local_rows, label: str, apply: bool) -> int:
    changed = 0
    for local in local_rows:
        remote = db.get(model, local["telegram_id"])
        if remote is None:
            continue
        diffs = {
            field: (getattr(remote, field), local[field])
            for field in WALLET_FIELDS
            if getattr(remote, field) != local[field]
        }
        if not diffs:
            continue
        changed += 1
        print(f"  {label} {local['telegram_id']} : " + ", ".join(f"{f} {old} -> {new}" for f, (old, new) in diffs.items()))
        if apply:
            for field, (_, new) in diffs.items():
                setattr(remote, field, new)
    return changed


def main(apply: bool) -> int:
    pending = count_backend_outbox()
    if pending:
        print(f"Refusé : {pending} mouvement(s) d'argent encore en file vers le backend (backend_outbox).")
        print("Relance le bot avec le backend joignable pour vider la file, puis réessaie.")
        return 1

    with SessionLocal() as db:
        changed = _copy_wallets(db, BotUser, get_all_users(limit=100_000), "client", apply)
        changed += _copy_wallets(db, BotProvider, get_all_providers(limit=100_000), "prestataire", apply)
        if apply:
            db.commit()

    if not changed:
        print("Aucun écart de wallet.")
    elif apply:
        print(f"{changed} compte(s) mis à jour dans le backend.")
    else:
        print(f"{changed} compte(s) à mettre à jour. Simulation seulement : relance avec --apply pour écrire.")
    return 0


if __name__ == "__main__":
    sys.exit(main(apply="--apply" in sys.argv[1:]))
