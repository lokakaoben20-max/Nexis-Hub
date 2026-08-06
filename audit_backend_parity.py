"""Audit de cohérence entre db.py (SQLite legacy) et le backend V5 (Postgres).

Lecture seule, ne modifie rien dans aucune des deux bases. Sert à mesurer la
dérive réelle avant d'envisager de basculer une lecture (profil, wallet,
matching...) du bot vers le backend plutôt que db.py -- voir la Phase 1-C de
V5_MIGRATION_PLAN.md.

Compare uniquement les champs qui ont vocation à être identiques dans les deux
bases (identité, contact, langue, wallet). Les champs dérivés des missions
(total_missions, success_rate, rating/average_rating) sont volontairement
exclus de la comparaison : le backend les calcule désormais (Phase 1-A/B),
db.py ne les a jamais calculés -- une différence attendue, pas une dérive.

Usage :
    .venv\\Scripts\\python.exe audit_backend_parity.py
"""

import json

from backend.app.database import SessionLocal
from backend.app.models import BotProvider, BotUser
from db import get_all_providers, get_all_users


def _load_json_list(raw) -> list[str]:
    if not raw:
        return []
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return []


def _diff_fields(local: dict, remote: dict, fields: list[str]) -> dict:
    diffs = {}
    for field in fields:
        if local.get(field) != remote.get(field):
            diffs[field] = (local.get(field), remote.get(field))
    return diffs


def audit_users(db) -> None:
    local_users = {u["telegram_id"]: dict(u) for u in get_all_users(limit=100_000)}
    remote_users = {u.telegram_id: u for u in db.query(BotUser).all()}

    only_local = sorted(set(local_users) - set(remote_users))
    only_remote = sorted(set(remote_users) - set(local_users))
    common = sorted(set(local_users) & set(remote_users))

    print(f"\n=== CLIENTS ===")
    print(f"db.py (SQLite)      : {len(local_users)}")
    print(f"backend (Postgres)  : {len(remote_users)}")
    print(f"présents seulement dans db.py      : {only_local or 'aucun'}")
    print(f"présents seulement dans le backend : {only_remote or 'aucun'}")

    fields = ["first_name", "phone_number", "language", "wallet_balance_usd", "wallet_balance_cdf"]
    drifted = 0
    for telegram_id in common:
        local = local_users[telegram_id]
        remote = remote_users[telegram_id]
        remote_dict = {
            "first_name": remote.first_name,
            "phone_number": remote.phone_number,
            "language": remote.language,
            "wallet_balance_usd": remote.wallet_balance_usd,
            "wallet_balance_cdf": remote.wallet_balance_cdf,
        }
        diffs = _diff_fields(local, remote_dict, fields)
        if diffs:
            drifted += 1
            print(f"  [{telegram_id}] dérive : {diffs}")

    print(f"communs et identiques : {len(common) - drifted}/{len(common)}")


def audit_providers(db) -> None:
    local_providers = {p["telegram_id"]: dict(p) for p in get_all_providers(limit=100_000)}
    remote_providers = {p.telegram_id: p for p in db.query(BotProvider).all()}

    only_local = sorted(set(local_providers) - set(remote_providers))
    only_remote = sorted(set(remote_providers) - set(local_providers))
    common = sorted(set(local_providers) & set(remote_providers))

    print(f"\n=== PRESTATAIRES ===")
    print(f"db.py (SQLite)      : {len(local_providers)}")
    print(f"backend (Postgres)  : {len(remote_providers)}")
    print(f"présents seulement dans db.py      : {only_local or 'aucun'}")
    print(f"présents seulement dans le backend : {only_remote or 'aucun'}")
    if only_local:
        print(
            "  -> ces prestataires ne recevront jamais de stats/reviews côté backend "
            "tant qu'ils ne sont pas backfillés (voir backfill_providers_to_backend.py)."
        )

    fields = ["full_name", "phone_number", "services", "communes", "status", "is_verified", "is_active", "is_suspended", "wallet_balance_usd", "wallet_balance_cdf"]
    drifted = 0
    for telegram_id in common:
        local = dict(local_providers[telegram_id])
        local["services"] = _load_json_list(local.get("services"))
        local["communes"] = _load_json_list(local.get("communes"))
        local["is_verified"] = bool(local.get("is_verified"))
        local["is_active"] = bool(local.get("is_active"))
        local["is_suspended"] = bool(local.get("is_suspended"))

        remote = remote_providers[telegram_id]
        remote_dict = {
            "full_name": remote.full_name,
            "phone_number": remote.phone_number,
            "services": remote.services or [],
            "communes": remote.communes or [],
            "status": remote.status,
            "is_verified": remote.is_verified,
            "is_active": remote.is_active,
            "is_suspended": remote.is_suspended,
            "wallet_balance_usd": remote.wallet_balance_usd,
            "wallet_balance_cdf": remote.wallet_balance_cdf,
        }
        diffs = _diff_fields(local, remote_dict, fields)
        if diffs:
            drifted += 1
            print(f"  [{telegram_id}] dérive : {diffs}")

    print(f"communs et identiques : {len(common) - drifted}/{len(common)}")

    # Champs dérivés : rappel qu'ils divergent par construction, pas par bug.
    print(
        "\nNote : total_missions/success_rate/rating (db.py) vs "
        "total_missions/success_rate/average_rating (backend) volontairement "
        "exclus ci-dessus -- le backend les calcule (Phase 1-A/B), db.py ne "
        "les a jamais calculés. Une différence attendue."
    )


def main() -> None:
    with SessionLocal() as db:
        audit_users(db)
        audit_providers(db)


if __name__ == "__main__":
    main()
