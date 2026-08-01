import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import db


def _make_provider(tmp_path, telegram_id=2002):
    db.DB_PATH = tmp_path / "test_nexis_hub.db"
    db.init_db()
    db.create_provider(telegram_id, "+243800000002", "Bob", ["service_plomberie"], ["Gombe"], language="fr")
    return telegram_id


def test_provider_stays_available_below_three_ignored(tmp_path):
    telegram_id = _make_provider(tmp_path)

    for _ in range(2):
        provider = db.update_consecutive_ignored(telegram_id)

    assert provider["consecutive_ignored"] == 2
    assert provider["status"] == "available"


def test_provider_is_auto_paused_on_third_consecutive_ignore(tmp_path):
    telegram_id = _make_provider(tmp_path)

    for _ in range(3):
        provider = db.update_consecutive_ignored(telegram_id)

    assert provider["consecutive_ignored"] == 3
    assert provider["status"] == "paused"


def test_reactivating_resets_the_ignored_counter(tmp_path):
    telegram_id = _make_provider(tmp_path)

    for _ in range(3):
        db.update_consecutive_ignored(telegram_id)
    paused = db.get_provider_by_telegram_id(telegram_id)
    assert paused["status"] == "paused"

    db.update_provider_status(telegram_id, "available")
    db.reset_consecutive_ignored(telegram_id)
    reactivated = db.get_provider_by_telegram_id(telegram_id)

    assert reactivated["status"] == "available"
    assert reactivated["consecutive_ignored"] == 0


def test_without_reset_a_single_ignore_after_reactivation_would_re_pause(tmp_path):
    # Regression guard: this is exactly the trap the reset-on-reactivation
    # fix in main.py avoids — without it, a provider who comes back online
    # is one skip away from being paused again instead of a fresh count of 3.
    telegram_id = _make_provider(tmp_path)

    for _ in range(3):
        db.update_consecutive_ignored(telegram_id)
    db.update_provider_status(telegram_id, "available")  # reactivate WITHOUT resetting

    provider = db.update_consecutive_ignored(telegram_id)
    assert provider["status"] == "paused"
    assert provider["consecutive_ignored"] == 4
