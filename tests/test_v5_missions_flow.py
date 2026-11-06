"""Écrans de missions du bot : lus dans le backend, seule mémoire des missions."""

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("BOT_TOKEN", "123:ABC")

from telegram_bot import dashboard


def test_my_missions_are_read_in_the_backend_by_role(live_backend):
    ordered = live_backend.new_mission(99)
    entrusted, _ = live_backend.accepted_quote(50, 99)

    as_client = asyncio.run(dashboard.fetch_my_missions(99, "client"))
    as_provider = asyncio.run(dashboard.fetch_my_missions(99, "provider"))

    assert [mission["mission_id"] for mission in as_client] == [ordered]
    assert [mission["mission_id"] for mission in as_provider] == [entrusted]


def test_my_missions_are_unknown_when_the_backend_is_down():
    """Aucune copie locale : None, jamais une liste vide trompeuse."""
    assert asyncio.run(dashboard.fetch_my_missions(99, "client")) is None
