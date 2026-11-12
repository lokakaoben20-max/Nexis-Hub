"""Le bot et la Mini App refusent de démarrer sans la clé du canal Telegram,
ou avec l'ancienne clé unique encore dans le `.env`."""

import pytest
from fastapi.testclient import TestClient

from telegram_bot import backend_client

KEY = "test-backend-api-key-not-a-secret"


def test_old_single_key_is_refused(monkeypatch):
    monkeypatch.setattr(backend_client, "BACKEND_API_KEY", KEY)
    monkeypatch.setenv("BACKEND_API_KEY", KEY)
    with pytest.raises(RuntimeError, match="BACKEND_API_KEY_TELEGRAM"):
        backend_client.check_backend_key()


def test_missing_telegram_key_is_refused(monkeypatch):
    monkeypatch.setattr(backend_client, "BACKEND_API_KEY", "")
    with pytest.raises(RuntimeError, match="BACKEND_API_KEY_TELEGRAM manquante"):
        backend_client.check_backend_key()


def test_telegram_key_present_is_accepted(monkeypatch):
    monkeypatch.setattr(backend_client, "BACKEND_API_KEY", KEY)
    backend_client.check_backend_key()


def test_mini_app_does_not_start_without_the_telegram_key(monkeypatch):
    from mini_app import app as mini_app_module

    monkeypatch.setattr(backend_client, "BACKEND_API_KEY", "")
    with pytest.raises(RuntimeError, match="BACKEND_API_KEY_TELEGRAM"):
        with TestClient(mini_app_module.app):
            pass
