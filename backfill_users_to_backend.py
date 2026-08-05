"""Backfill clients registered in db.py (legacy SQLite) into the V5 backend.

Same class of gap as backfill_providers_to_backend.py, but for clients: user
sync to the backend only happens once, at registration (persist_client_
registration in main.py). A client registered before the backend was
reachable, or whose one-shot sync failed, stays permanently absent from
bot_users -- and GET /api/profile/{id} then returns a placeholder "Client"
name instead of the real one, masking any later local update (e.g. via the
client's "Modifier" > "Modifier mon nom" menu) since the bot's profile
display prefers the backend's answer when the backend responds at all.

Run manually whenever you suspect drift between db.py and the backend
(e.g. after restoring an environment, or if a client's profile looks
wrong/stale on the backend):

    python backfill_users_to_backend.py
"""

from backend.app.crud import upsert_user
from backend.app.database import SessionLocal
from db import get_all_users


def main() -> None:
    users = get_all_users(limit=100_000)
    synced, failed = 0, []

    with SessionLocal() as db:
        for user in users:
            try:
                upsert_user(
                    db,
                    telegram_id=user["telegram_id"],
                    first_name=user["first_name"],
                    phone_number=user["phone_number"],
                    language=user["language"],
                )
                synced += 1
            except Exception as exc:  # noqa: BLE001 - report and keep going
                failed.append((user["telegram_id"], str(exc)))

    print(f"Backfill terminé : {synced} client(s) synchronisé(s), {len(failed)} échec(s).")
    for telegram_id, error in failed:
        print(f"  - {telegram_id}: {error}")


if __name__ == "__main__":
    main()
