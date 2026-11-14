"""Client d'argent du bot (telegram_bot/backend_client.py) face au backend.

Le bot ne décide rien : il transmet, puis recopie. Il doit distinguer un refus
métier du backend (code stable + état réel de la mission) d'un backend
injoignable ou d'une réponse inattendue, où rien n'a bougé.
"""

import asyncio
import os

import httpx
import pytest

os.environ.setdefault("BOT_TOKEN", "123:ABC")

from telegram_bot import backend_client


def _client_answering(status, body):
    # httpx._client.AsyncClient : la vraie classe, httpx.AsyncClient étant
    # remplacé par la fixture « backend injoignable ».
    class _Client(httpx._client.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = httpx.MockTransport(lambda request: httpx.Response(status, json=body))
            super().__init__(*args, **kwargs)

    return _Client


def test_a_business_refusal_carries_its_code_and_the_current_mission(monkeypatch):
    mission = {"mission_id": 7, "status": "completed", "payment_status": "released"}
    monkeypatch.setattr(
        backend_client.httpx,
        "AsyncClient",
        _client_answering(409, {"detail": {"code": "already_settled", "mission": mission, "money": {"settlement": None}}}),
    )

    with pytest.raises(backend_client.MoneyRefused) as refusal:
        asyncio.run(backend_client.confirm_mission(7, 42))

    assert refusal.value.code == "already_settled"
    assert refusal.value.mission == mission


def test_an_unreachable_backend_is_reported_as_unavailable():
    # La fixture par défaut refuse toute connexion.
    with pytest.raises(backend_client.BackendUnavailable):
        asyncio.run(backend_client.declare_arrival(7, 200))


@pytest.mark.parametrize(
    "status,body",
    [
        (500, {"detail": "Internal Server Error"}),
        (401, {"detail": "Clé API invalide ou manquante"}),
        (409, {"detail": "pas un refus métier"}),
        (200, {"status": "ok"}),  # pas de mission dans la réponse
    ],
)
def test_any_unexpected_answer_counts_as_unavailable_never_as_success(monkeypatch, status, body):
    monkeypatch.setattr(backend_client.httpx, "AsyncClient", _client_answering(status, body))

    with pytest.raises(backend_client.BackendUnavailable):
        asyncio.run(backend_client.finish_mission(7, 200))


def test_wallets_are_unknown_when_the_backend_is_down():
    wallets = asyncio.run(backend_client.fetch_wallets(42))

    assert wallets is None
    assert backend_client.wallet_balance(wallets, "USD") is None


def test_payment_amount_and_provider_come_from_the_recorded_quote(live_backend):
    """Le bot n'envoie que les numéros de mission et de devis : montant,
    devise, prestataire et urgence sont relus par le backend."""
    mission_id, quote_id = live_backend.accepted_quote(42, 7, amount=100.0, urgent=True)

    result = asyncio.run(backend_client.create_payment_intent(mission_id, quote_id, "+243810000000", "mpesa", 42))

    assert result["mission"]["payment_status"] == "paid_escrow"
    assert result["money"]["funding"]["total"] == "100.00"
    assert result["money"]["funding"]["commission"] == "15.00"  # urgente : 15 %
    assert result["money"]["funding"]["reference"] == "SIM-PAY-000001"
    assert live_backend.mission(mission_id).provider_telegram_id == 7


def test_mission_creation_is_numbered_by_the_backend_and_replayable(live_backend):
    data = {
        "service": "service_plomberie", "commune": "Gombe", "currency": "USD", "description": "Fuite",
        "urgent": False, "photo_file_ids": ["photo-1"], "voice_file_ids": ["voix-1"],
        "destination_latitude": -4.3076, "destination_longitude": 15.3125,
        "destination_landmark": "Portail bleu après la poste",
    }

    # 7 et le client 42 sont tous deux plombiers vérifiés à Gombe : le
    # backend prévient 7, jamais le client lui-même.
    live_backend.provider(7, services=("service_plomberie",), communes=("Gombe",))
    live_backend.provider(42, services=("service_plomberie",), communes=("Gombe",))
    first = asyncio.run(backend_client.create_mission(42, data, "demande-a"))
    replay = asyncio.run(backend_client.create_mission(42, data, "demande-a"))

    assert first["created"] is True and replay["created"] is False
    assert replay["mission"]["mission_id"] == first["mission"]["mission_id"]
    assert first["mission"]["media"] == [
        {"channel": "telegram", "kind": "photo", "id": "photo-1"},
        {"channel": "telegram", "kind": "voice", "id": "voix-1"},
    ]
    assert first["alerted_provider_telegram_ids"] == [7]
    with pytest.raises(backend_client.MoneyRefused) as refused:
        asyncio.run(backend_client.create_mission(42, {**data, "description": "Autre"}, "demande-a"))
    assert refused.value.code == "creation_key_reused"
