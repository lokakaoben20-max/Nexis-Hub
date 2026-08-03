"""Backfill providers registered in db.py (legacy SQLite) into the V5 backend.

Provider sync to the backend only happens once, at registration
(terminer_inscription_prestataire in main.py). A provider registered before
the backend was reachable, or whose one-shot sync failed, is never retried
and stays permanently absent from bot_providers -- which silently breaks
review-derived stats (average_rating/total_reviews), since crud.create_review
recomputes them only if the provider already exists in Postgres.

Run manually whenever you suspect drift between db.py and the backend
(e.g. after restoring an environment, or if a provider's profile/rating
looks stale on the backend):

    python backfill_providers_to_backend.py
"""

import json

from backend.app.crud import _recompute_provider_rating, upsert_provider
from backend.app.database import SessionLocal
from db import get_all_providers


def _load_json_list(raw) -> list[str]:
    if not raw:
        return []
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return []


def main() -> None:
    providers = get_all_providers(limit=100_000)
    synced, failed = 0, []

    with SessionLocal() as db:
        for provider in providers:
            try:
                upsert_provider(
                    db,
                    telegram_id=provider["telegram_id"],
                    full_name=provider["full_name"],
                    phone_number=provider["phone_number"],
                    services=_load_json_list(provider["services"]),
                    communes=_load_json_list(provider["communes"]),
                    language=provider["language"],
                )
                _recompute_provider_rating(db, provider["telegram_id"])
                synced += 1
            except Exception as exc:  # noqa: BLE001 - report and keep going
                failed.append((provider["telegram_id"], str(exc)))

    print(f"Backfill terminé : {synced} prestataire(s) synchronisé(s), {len(failed)} échec(s).")
    for telegram_id, error in failed:
        print(f"  - {telegram_id}: {error}")


if __name__ == "__main__":
    main()
