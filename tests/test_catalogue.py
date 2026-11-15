"""Catalogue du bot : celui du backend, chargé au démarrage, sans liste de
secours. Un contenu inattendu est refusé en bloc."""

import asyncio

import pytest

from telegram_bot import catalogue


def _body(**overrides):
    body = {
        "services": [
            {"key": "service_plomberie", "icon": "🔧", "names": {"fr": "Plomberie", "ln": "Plomberie", "en": "Plumbing"}},
            {"key": "service_electricite", "icon": "⚡", "names": {"fr": "Electricité", "ln": "Kura", "en": "Electricity"}},
        ],
        "communes": ["Gombe", "Autre commune"],
    }
    body.update(overrides)
    return body


def test_the_backend_catalogue_fills_the_bot_lists():
    catalogue.fill(_body())

    assert catalogue.SERVICES == {"service_plomberie": "🔧 Plomberie", "service_electricite": "⚡ Electricité"}
    assert catalogue.COMMUNES == [("Gombe", "commune_gombe"), ("Autre commune", "commune_autre")]
    assert catalogue.service_label("service_electricite", "en") == "⚡ Electricity"
    assert catalogue.service_label("service_disparu") == "service_disparu", "ancienne mission : la clé brute"
    assert catalogue.commune_from_callback("commune_autre") == "Autre commune"


@pytest.mark.parametrize(
    "overrides",
    [
        {"services": []},
        {"communes": []},
        {"services": [{"key": "service_plomberie"}]},
        {"communes": ["Kalamu", "Kalamu nord"]},  # même bouton « commune_kalamu »
        {"services": _body()["services"] * 2},
    ],
)
def test_an_unexpected_catalogue_is_refused_and_the_previous_one_kept(overrides):
    catalogue.fill(_body())
    before = dict(catalogue.SERVICES), list(catalogue.COMMUNES)

    with pytest.raises(catalogue.CatalogueUnavailable):
        catalogue.fill(_body(**overrides))

    assert (catalogue.SERVICES, catalogue.COMMUNES) == before


def test_the_bot_refuses_to_start_without_the_catalogue():
    with pytest.raises(catalogue.CatalogueUnavailable):
        asyncio.run(catalogue.load("http://127.0.0.1:8000", {}, attempts=2, delay=0))


def test_the_bot_loads_the_catalogue_from_the_live_backend(live_backend):
    from telegram_bot.backend_client import BACKEND_AUTH_HEADERS, BACKEND_BASE_URL

    catalogue.SERVICES.clear()
    asyncio.run(catalogue.load(BACKEND_BASE_URL, BACKEND_AUTH_HEADERS, attempts=1))

    assert "service_plomberie" in catalogue.SERVICES
    assert ("Gombe", "commune_gombe") in catalogue.COMMUNES


def test_the_service_rules_come_from_the_backend_and_shape_the_buttons(live_backend):
    """« Autre service » : ni mission pour un client (son besoin part à
    l'équipe), ni choix pour un prestataire ; au plus 3 services."""
    from telegram_bot import keyboards
    from telegram_bot.backend_client import BACKEND_AUTH_HEADERS, BACKEND_BASE_URL

    asyncio.run(catalogue.load(BACKEND_BASE_URL, BACKEND_AUTH_HEADERS, attempts=1))

    assert catalogue.PROVIDER_RULES == {"max_services": 3, "excluded_services": ("service_autre",)}
    assert "service_autre" not in catalogue.client_service_keys()
    assert "service_autre" not in catalogue.provider_service_keys()
    assert "service_autre" in catalogue.provider_service_keys(["service_autre"]), "profil d'avant la règle"
    assert catalogue.provider_service_refusal(["service_plomberie"], "service_autre") == "service_not_for_providers"
    three = ["service_plomberie", "service_electricite", "service_nettoyage"]
    assert catalogue.provider_service_refusal(three, "service_coiffure") == "too_many_services"
    assert catalogue.provider_service_refusal(three, "service_coiffure", original=["service_coiffure"]) is None

    client_buttons = [button.callback_data for row in keyboards.clavier_services().inline_keyboard for button in row]
    assert "service_autre" not in client_buttons and "client_need" in client_buttons
    provider_buttons = [button.callback_data for row in keyboards.clavier_modifier_services([]).inline_keyboard for button in row]
    assert "edit_service_service_autre" not in provider_buttons
