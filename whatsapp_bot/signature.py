"""Signature des webhooks de Meta (`X-Hub-Signature-256`).

Meta signe le corps brut de chaque webhook avec le secret de l'application :
`sha256=` suivi du HMAC-SHA256 en hexadécimal. La vérification porte sur les
octets reçus, avant toute lecture du JSON (un JSON relu puis réécrit
n'aurait pas les mêmes octets), et se fait en temps constant.
"""

from __future__ import annotations

import hashlib
import hmac

HEADER = "X-Hub-Signature-256"
PREFIX = "sha256="


def sign(app_secret: str, body: bytes) -> str:
    return PREFIX + hmac.new(app_secret.encode(), body, hashlib.sha256).hexdigest()


def is_valid(app_secret: str, body: bytes, presented: str | None) -> bool:
    if not app_secret or not presented or not presented.startswith(PREFIX):
        return False
    return hmac.compare_digest(sign(app_secret, body).encode(), presented.encode())
