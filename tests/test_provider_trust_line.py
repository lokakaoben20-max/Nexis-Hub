import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("BOT_TOKEN", "123:ABC")

import db
from telegram_bot.mission import provider_trust_line


def _provider(**overrides):
    base = {
        "total_missions": 0,
        "rating": 0.0,
        "success_rate": 0.0,
        "badge": "pending",
        "is_verified": 0,
    }
    base.update(overrides)
    return base


def test_new_provider_without_missions_shows_neutral_message():
    line = provider_trust_line(_provider())
    assert line == "🆕 Nouveau prestataire sur Nexis Hub"


def test_experienced_provider_shows_rating_and_success_rate():
    line = provider_trust_line(_provider(total_missions=12, rating=4.8, success_rate=91))
    assert "4.8/5" in line
    assert "12 missions" in line
    assert "91% de réussite" in line


def test_badge_and_verification_are_appended_when_present():
    line = provider_trust_line(_provider(total_missions=30, rating=5.0, success_rate=100, badge="partner", is_verified=1))
    assert "🏆 Partenaire" in line
    assert "✅ Vérifié" in line


def test_pending_badge_is_not_shown_as_a_label():
    line = provider_trust_line(_provider(total_missions=5, rating=3.0, success_rate=80, badge="pending"))
    assert "pending" not in line.lower()


def test_provider_trust_line_works_with_real_db_row(tmp_path):
    db.DB_PATH = tmp_path / "test_nexis_hub.db"
    db.init_db()
    db.create_provider(3003, "+243800000003", "Chantal", ["service_peinture"], ["Gombe"], language="fr")

    provider = db.get_provider_by_telegram_id(3003)
    line = provider_trust_line(provider)

    assert line == "🆕 Nouveau prestataire sur Nexis Hub"
