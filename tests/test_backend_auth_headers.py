"""Verifie la transmission de la cle interne du bot au backend."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("BOT_TOKEN", "123:ABC")

import main


def test_backend_request_headers_include_configured_key(monkeypatch):
    monkeypatch.setattr(main, "BACKEND_API_KEY", "test-internal-key")
    assert main.backend_request_headers() == {
        "X-Nexis-Internal-Key": "test-internal-key",
    }


def test_backend_request_headers_do_not_send_empty_secret(monkeypatch):
    monkeypatch.setattr(main, "BACKEND_API_KEY", "")
    assert main.backend_request_headers() == {}
