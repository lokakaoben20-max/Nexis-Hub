"""Configuration vérifiée au démarrage (nexis_config.py) et journaux masqués
(nexis_logs.py)."""

import io
import json
import logging

import pytest

import nexis_config
import nexis_logs

SECRET = "s" * 40

ARGENT = {
    "COLLECTION_FEE_RATE": "0.025",
    "PAYOUT_FEE_RATE": "0.01",
    **{f"{p}_{d}": "1" for p in nexis_config.MONTANTS_PAR_DEVISE for d in nexis_config.DEVISES},
}


@pytest.fixture
def env(monkeypatch):
    for nom in list(ARGENT) + [v for role in nexis_config.ROLES.values() for v in role] + [
        "APP_ENV", "WEBHOOK_URL", "WEBHOOK_SECRET_TOKEN",
    ]:
        monkeypatch.delenv(nom, raising=False)

    def poser(**valeurs):
        for nom, valeur in valeurs.items():
            monkeypatch.setenv(nom, valeur)

    return poser


def _backend_complet(env, app_env="production", passerelle="flexpay"):
    env(
        APP_ENV=app_env,
        DATABASE_URL="postgresql+psycopg://u@h/nexis",
        BACKEND_API_KEY_TELEGRAM=SECRET,
        APP_CODE_HMAC_KEY=SECRET,
        BOT_TOKEN="123:abc",
        PAYMENT_GATEWAY=passerelle,
        **ARGENT,
    )


def test_rien_n_est_impose_en_developpement(env):
    assert nexis_config.problemes("backend") == []
    assert nexis_config.verifier("bot") == "developpement"


def test_un_environnement_inconnu_est_refuse(env):
    env(APP_ENV="prod")
    with pytest.raises(nexis_config.ConfigurationInvalide, match="APP_ENV"):
        nexis_config.verifier("backend")


def test_un_backend_complet_demarre_en_production(env):
    _backend_complet(env)
    assert nexis_config.verifier("backend") == "production"


def test_en_production_aucun_reglage_d_argent_ne_prend_de_valeur_par_defaut(env):
    _backend_complet(env)
    env(PAYOUT_MINIMUM_CDF="", COLLECTION_FEE_RATE="0.5", PAYOUT_FEE_RATE="abc")
    erreurs = nexis_config.problemes("backend")
    assert "PAYOUT_MINIMUM_CDF manquant" in erreurs
    assert "COLLECTION_FEE_RATE hors limites" in erreurs
    assert "PAYOUT_FEE_RATE n'est pas un nombre" in erreurs


def test_toutes_les_erreurs_sont_donnees_d_un_coup_sans_les_valeurs(env):
    env(APP_ENV="production", BACKEND_API_KEY_TELEGRAM="court-et-secret", DATABASE_URL="sqlite:///x.db")
    with pytest.raises(nexis_config.ConfigurationInvalide) as erreur:
        nexis_config.verifier("backend")
    texte = str(erreur.value)
    assert "BACKEND_API_KEY_TELEGRAM trop court" in texte
    assert "DATABASE_URL doit viser Postgres" in texte
    assert "BOT_TOKEN manquant" in texte
    assert "court-et-secret" not in texte and "x.db" not in texte


def test_l_ancien_reglage_admin_est_refuse_hors_developpement(env):
    """Les admins sont en base : un ADMIN_TELEGRAM_ID oublié ferait croire
    que cette personne est admin alors que plus rien ne le lit."""
    _backend_complet(env)
    env(ADMIN_TELEGRAM_ID="42")
    for role in ("backend", "taches", "bot"):
        assert any(e.startswith("ADMIN_TELEGRAM_ID n'est plus utilisé") for e in nexis_config.problemes(role))


def test_paiement_simule_interdit_en_production_et_obligatoire_en_test(env):
    _backend_complet(env, passerelle="simulation")
    assert "PAYMENT_GATEWAY=simulation interdit en production" in nexis_config.problemes("taches")
    _backend_complet(env, app_env="test", passerelle="flexpay")
    assert any("simulation en test" in e for e in nexis_config.problemes("backend"))
    _backend_complet(env, app_env="test", passerelle="simulation")
    assert nexis_config.problemes("backend") == []


def test_le_bot_heberge_est_en_webhook_https_avec_secret(env):
    env(
        APP_ENV="test", BOT_TOKEN="123:abc", BACKEND_BASE_URL="http://backend.interne", BACKEND_API_KEY_TELEGRAM=SECRET,
        REDIS_URL="rediss://r", MINI_APP_URL="https://app.example.org", BOT_RUN_MODE="polling",
    )
    assert "BOT_RUN_MODE doit valoir webhook hors développement" in nexis_config.problemes("bot")
    env(BOT_RUN_MODE="webhook", WEBHOOK_URL="http://bot.example.org")
    erreurs = nexis_config.problemes("bot")
    assert "WEBHOOK_SECRET_TOKEN manquant" in erreurs
    assert "WEBHOOK_URL doit être en https" in erreurs
    env(WEBHOOK_URL="https://bot.example.org", WEBHOOK_SECRET_TOKEN=SECRET)
    assert nexis_config.problemes("bot") == []


@pytest.mark.parametrize(
    "texte, interdit",
    [
        ("GET https://api.telegram.org/bot123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw/sendMessage", "AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw"),
        ("contact partagé +243 812 345 678", "812 345 678"),
        ("numéro 0812345678 refusé", "0812345678"),
        ("payeur 243812345678", "243812345678"),
        ("intl +33 6 12 34 56 78", "6 12 34 56 78"),
        ("headers={'X-API-Key': 'cle-tres-secrete'}", "cle-tres-secrete"),
        ("Authorization: Bearer abc.def.ghi", "abc.def.ghi"),
        ("set_webhook secret_token=deadbeefcafe", "deadbeefcafe"),
    ],
)
def test_les_donnees_sensibles_sont_masquees(texte, interdit):
    assert interdit not in nexis_logs.masquer(texte)


@pytest.mark.parametrize(
    "texte",
    [
        "mission NXH-0042 payée 150.00 USD, intention 12",
        "relance le 2026-11-07 19:25:13 pour le prestataire 987654321",
        "Échec d'envoi de notification Telegram à 5123456789",
        "montant 125000000.00 CDF",
    ],
)
def test_dates_montants_et_identifiants_telegram_restent_lisibles(texte):
    assert nexis_logs.masquer(texte) == texte


def test_une_ligne_json_par_evenement_masquee_jusque_dans_l_exception(monkeypatch):
    sortie = io.StringIO()
    monkeypatch.setattr(nexis_logs.sys, "stdout", sortie)
    racine = logging.getLogger()
    avant = (list(racine.handlers), racine.level)
    try:
        nexis_logs.configurer("backend", json_=True)
        journal = logging.getLogger("nexis.test")
        journal.info("client %s", "+243812345678")
        try:
            raise RuntimeError("jeton 123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw")
        except RuntimeError:
            journal.exception("échec")
    finally:
        racine.handlers[:], _ = avant
        racine.setLevel(avant[1])
    lignes = [json.loads(ligne) for ligne in sortie.getvalue().splitlines()]
    assert [ligne["severity"] for ligne in lignes] == ["INFO", "ERROR"]
    assert lignes[0]["service"] == "backend" and "812345678" not in lignes[0]["message"]
    assert "AAHdqTcv" not in lignes[1]["exception"]
