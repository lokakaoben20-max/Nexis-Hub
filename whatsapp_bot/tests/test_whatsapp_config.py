"""Réglages du service WhatsApp : refus de démarrer plutôt qu'un webhook
ouvert ou un envoi vers une mauvaise adresse."""

import pytest

from whatsapp_bot import config

GOOD = {
    "WHATSAPP_APP_SECRET": "a" * 32,
    "WHATSAPP_VERIFY_TOKEN": "v" * 32,
    "WHATSAPP_ACCESS_TOKEN": "jeton",
    "WHATSAPP_PHONE_NUMBER_ID": "100000000000001",
    "BACKEND_API_KEY_WHATSAPP": "k" * 32,
}
HOSTED = {
    "BACKEND_BASE_URL": "https://api.nexis.example",
    "REDIS_URL": "redis://redis:6379/0",
    "NEXIS_BOT_USERNAME": "NexisHubBot",
    "MINI_APP_URL": "https://nexis.example/app/",
}


@pytest.fixture
def env(monkeypatch):
    for name in [*GOOD, *HOSTED, "WHATSAPP_GRAPH_URL", "APP_ENV"]:
        monkeypatch.delenv(name, raising=False)

    def apply(values):
        for name, value in values.items():
            monkeypatch.setenv(name, value)

    return apply


def test_development_needs_the_secrets_too(env):
    with pytest.raises(config.ConfigurationError) as error:
        config.load()
    message = str(error.value)
    assert all(name in message for name in GOOD)


def test_development_with_secrets_starts(env):
    env(GOOD)
    settings = config.load()
    assert settings.graph_url == config.DEFAULT_GRAPH_URL
    assert settings.telegram_bot_link is None


def test_short_secrets_are_refused_and_never_printed(env):
    env({**GOOD, "WHATSAPP_VERIFY_TOKEN": "court-et-secret"})
    with pytest.raises(config.ConfigurationError) as error:
        config.load()
    assert "WHATSAPP_VERIFY_TOKEN trop court" in str(error.value)
    assert "court-et-secret" not in str(error.value)


def test_hosted_service_refuses_the_fake_meta_and_missing_links(env):
    env({**GOOD, "APP_ENV": "production", "WHATSAPP_GRAPH_URL": "http://127.0.0.1:8011/v23.0"})
    with pytest.raises(config.ConfigurationError) as error:
        config.load()
    message = str(error.value)
    assert "WHATSAPP_GRAPH_URL doit être en https" in message
    assert all(name in message for name in HOSTED)


def test_hosted_service_with_everything_starts(env):
    env({**GOOD, **HOSTED, "APP_ENV": "production"})
    settings = config.load()
    assert settings.telegram_bot_link == "https://t.me/NexisHubBot"
    assert settings.public_site == "https://nexis.example"
