"""Tests de sécurité des privilèges administrateur Telegram."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("BOT_TOKEN", "123:ABC")

import main


def test_admin_access_is_denied_when_not_configured(monkeypatch):
    monkeypatch.setattr(main, "ADMIN_TELEGRAM_ID", None)
    assert main.is_admin(12345) is False

    monkeypatch.setattr(main, "ADMIN_TELEGRAM_ID", "")
    assert main.is_admin(12345) is False


def test_only_the_configured_telegram_id_is_admin(monkeypatch):
    monkeypatch.setattr(main, "ADMIN_TELEGRAM_ID", "12345")
    assert main.is_admin(12345) is True
    assert main.is_admin(67890) is False
