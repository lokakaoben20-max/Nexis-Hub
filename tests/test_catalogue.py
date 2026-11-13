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
