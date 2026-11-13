"""Profils lus et écrits par le bot dans le backend (telegram_bot/backend_client.py).

Toujours au nom de la personne qui écrit ; le backend applique ses règles et
rend le profil. Backend injoignable : `BackendUnavailable`, rien n'est gardé
ailleurs pour plus tard."""

import asyncio

import pytest

from telegram_bot import backend_client


def test_a_client_registers_and_changes_language_and_name(live_backend):
    me = asyncio.run(backend_client.save_client_profile(42, "Laura", "+243810000042", "ln", phone_verified=True))
    assert me["profile_type"] == "client"
    assert (me["client"]["first_name"], me["client"]["phone_number"], me["language"]) == ("Laura", "+243810000042", "ln")

    asyncio.run(backend_client.set_my_language(42, "en"))
    renamed = asyncio.run(backend_client.set_my_name(42, "Laure"))

    assert (renamed["client"]["first_name"], renamed["language"]) == ("Laure", "en")
    assert asyncio.run(backend_client.get_language(42)) == "en"
    assert asyncio.run(backend_client.fetch_me(42))["client"]["first_name"] == "Laure"


def test_an_unknown_person_is_a_guest_and_has_no_account_to_change(live_backend):
    assert asyncio.run(backend_client.fetch_me(555))["profile_type"] == "guest"
    assert asyncio.run(backend_client.get_language(555)) == "fr"
    with pytest.raises(backend_client.MoneyRefused) as refused:
        asyncio.run(backend_client.set_my_language(555, "ln"))
    assert refused.value.code == "account_not_found"


def test_a_provider_registers_waits_for_validation_then_sets_availability(live_backend):
    data = {
        "full_name": "Bob Kabila",
        "phone_number": "+243810000077",
        "services": ["service_plomberie"],
        "communes": ["Gombe", "Lemba"],
        "language": "fr",
        "id_document_file_id": "piece",
        "selfie_file_id": "selfie",
        "portfolio_file_ids": ["photo-1"],
        "phone_verified": True,
    }
    me = asyncio.run(backend_client.save_provider_profile(77, data))
    assert (me["provider"]["status"], me["provider"]["services"], me["provider"]["communes"]) == (
        "pending_verification",
        ["service_plomberie"],
        ["Gombe", "Lemba"],
    )
    with pytest.raises(backend_client.MoneyRefused) as refused:
        asyncio.run(backend_client.set_my_availability(77, "available"))
    assert refused.value.code == "provider_not_verified"

    live_backend.grant_admin(999)
    asyncio.run(backend_client.admin_decide_provider(999, me["account_id"], "verify"))
    offline = asyncio.run(backend_client.set_my_availability(77, "offline"))
    services = asyncio.run(backend_client.set_my_services(77, ["service_plomberie", "service_electricite"]))

    assert offline["provider"]["status"] == "offline"
    assert services["provider"]["services"] == ["service_plomberie", "service_electricite"]


def test_a_service_outside_the_catalogue_is_refused(live_backend):
    live_backend.provider(77)
    with pytest.raises(backend_client.MoneyRefused) as refused:
        asyncio.run(backend_client.set_my_services(77, ["service_peinture"]))
    assert refused.value.code == "unknown_service"


def test_the_catalogue_comes_from_the_backend(live_backend):
    body = asyncio.run(backend_client.fetch_catalogue())
    assert body["services"][0]["key"] == "service_plomberie"
    assert "Gombe" in body["communes"]


def test_an_unreachable_backend_changes_nothing_and_says_so():
    # La fixture par défaut refuse toute connexion.
    with pytest.raises(backend_client.BackendUnavailable):
        asyncio.run(backend_client.save_client_profile(42, "Laura", None, "fr"))
    with pytest.raises(backend_client.BackendUnavailable):
        asyncio.run(backend_client.set_my_availability(77, "available"))
    assert asyncio.run(backend_client.my_profile(42)) is None
    assert asyncio.run(backend_client.get_language(42)) == "fr"
