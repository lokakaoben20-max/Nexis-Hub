"""Tâches planifiées sans Celery (backend/app/taches.py) : calendrier, verrou,
planificateur local. Le verrou est testé sur Postgres en CI
(NEXIS_TEST_BACKEND_DB=postgres), comme en production."""

import importlib
import threading
from datetime import datetime, timedelta, timezone

import pytest

from backend.app import taches as _taches  # noqa: F401  (pré-import, voir test_tasks.py)


@pytest.fixture
def taches(monkeypatch, backend_db_url):
    monkeypatch.setenv("DATABASE_URL", backend_db_url)
    database = importlib.reload(importlib.import_module("backend.app.database"))
    module = importlib.import_module("backend.app.taches")
    monkeypatch.setattr(module, "database", database)
    yield module
    database.engine.dispose()


def _remplacer(monkeypatch, taches, nom, fonction):
    ancienne = taches.CALENDRIER[nom]
    monkeypatch.setitem(taches.CALENDRIER, nom, taches.Tache(fonction, ancienne.frequence))


def test_le_calendrier_reprend_les_frequences_de_celery(taches):
    assert {nom: tache.frequence.cron for nom, tache in taches.CALENDRIER.items()} == {
        "relances-prestataires": "*/10 * * * *",
        "devis-expires": "0 * * * *",
        "liberations-automatiques": "0 * * * *",
        "verification-mobile-money": "*/2 * * * *",
        "rapprochement-quotidien": "0 6 * * *",
        "analytics-quotidiennes": "0 8 * * *",
    }


def test_les_taches_dues_suivent_l_heure_utc(taches):
    def a(h, m):
        return datetime(2026, 11, 7, h, m, 30, tzinfo=timezone.utc)

    assert taches.taches_dues(a(6, 0)) == [
        "relances-prestataires", "devis-expires", "liberations-automatiques",
        "verification-mobile-money", "rapprochement-quotidien",
    ]
    assert taches.taches_dues(a(6, 2)) == ["verification-mobile-money"]
    assert taches.taches_dues(a(6, 3)) == []
    # 9 h à Kinshasa (UTC+1) = 8 h UTC : l'heure d'un fuseau ne trompe pas le calendrier.
    kinshasa = timezone(timedelta(hours=1))
    assert "analytics-quotidiennes" in taches.taches_dues(datetime(2026, 11, 7, 9, 0, tzinfo=kinshasa))


@pytest.mark.parametrize(
    "arguments",
    [{"toutes_les_minutes": 7}, {"toutes_les_minutes": 5, "heure": 3}, {"heure": 24}, {"minute": 60}],
)
def test_une_frequence_impossible_est_refusee(taches, arguments):
    with pytest.raises(ValueError):
        taches.Frequence(**arguments)


def test_une_tache_lancee_s_execute_une_fois(taches, monkeypatch):
    appels = []
    _remplacer(monkeypatch, taches, "devis-expires", lambda: appels.append(1) or 3)

    assert taches.lancer("devis-expires") == "faite"
    assert appels == [1]


def test_une_tache_deja_en_cours_ailleurs_ne_tourne_pas_une_seconde_fois(taches, monkeypatch):
    appels = []
    _remplacer(monkeypatch, taches, "verification-mobile-money", lambda: appels.append(1))

    with taches.verrou("verification-mobile-money") as tenu:
        assert tenu
        # Sur Postgres : une autre connexion, comme une autre instance.
        assert taches.lancer("verification-mobile-money") == "deja_en_cours"
    assert appels == []

    assert taches.lancer("verification-mobile-money") == "faite"
    assert appels == [1]


def test_deux_lancements_simultanes_une_seule_execution(taches, monkeypatch):
    entree, sortie = threading.Event(), threading.Event()
    appels = []

    def lente():
        appels.append(1)
        entree.set()
        sortie.wait(5)

    _remplacer(monkeypatch, taches, "liberations-automatiques", lente)
    resultats = []
    premier = threading.Thread(target=lambda: resultats.append(taches.lancer("liberations-automatiques")))
    premier.start()
    assert entree.wait(5)
    resultats.append(taches.lancer("liberations-automatiques"))
    sortie.set()
    premier.join(5)

    assert sorted(resultats) == ["deja_en_cours", "faite"]
    assert appels == [1]


def test_une_tache_en_echec_remonte_l_erreur_et_libere_le_verrou(taches, monkeypatch):
    def en_panne():
        raise RuntimeError("agrégateur injoignable")

    _remplacer(monkeypatch, taches, "rapprochement-quotidien", en_panne)
    with pytest.raises(RuntimeError):
        taches.lancer("rapprochement-quotidien")
    with taches.verrou("rapprochement-quotidien") as tenu:
        assert tenu


def test_les_verrous_de_taches_differentes_sont_independants(taches):
    assert taches.cle_de_verrou("devis-expires") == taches.cle_de_verrou("devis-expires")
    assert taches.cle_de_verrou("devis-expires") != taches.cle_de_verrou("liberations-automatiques")
    assert 0 <= taches.cle_de_verrou("devis-expires") < 2**63
    with taches.verrou("devis-expires") as premier, taches.verrou("liberations-automatiques") as second:
        assert premier and second


def test_le_planificateur_lance_chaque_tache_due_une_fois_par_minute_et_survit_aux_echecs(taches, monkeypatch):
    lancees = []
    for nom in taches.CALENDRIER:
        def fonction(nom=nom):
            lancees.append(nom)
            if nom == "devis-expires":
                raise RuntimeError("panne")
        _remplacer(monkeypatch, taches, nom, fonction)

    instants = iter([
        datetime(2026, 11, 7, 7, 0, 1, tzinfo=timezone.utc),
        datetime(2026, 11, 7, 7, 0, 2, tzinfo=timezone.utc),   # même minute : rien de plus
        datetime(2026, 11, 7, 7, 0, 40, tzinfo=timezone.utc),
        datetime(2026, 11, 7, 7, 2, 0, tzinfo=timezone.utc),
        datetime(2026, 11, 7, 7, 2, 1, tzinfo=timezone.utc),
    ])
    arret = threading.Event()

    def horloge():
        try:
            return next(instants)
        except StopIteration:
            arret.set()
            return datetime(2026, 11, 7, 7, 2, 2, tzinfo=timezone.utc)

    monkeypatch.setattr(arret, "wait", lambda delai: None)
    taches.planificateur(arret=arret, horloge=horloge)

    assert lancees == [
        "relances-prestataires", "devis-expires", "liberations-automatiques", "verification-mobile-money",
        "verification-mobile-money",
    ]


def test_la_ligne_de_commande(taches, monkeypatch, capsys):
    assert taches.main(["calendrier"]) == 0
    assert "verification-mobile-money\t*/2 * * * *" in capsys.readouterr().out

    _remplacer(monkeypatch, taches, "devis-expires", lambda: 0)
    assert taches.main(["lancer", "devis-expires"]) == 0

    def en_panne():
        raise RuntimeError("panne")

    _remplacer(monkeypatch, taches, "devis-expires", en_panne)
    assert taches.main(["lancer", "devis-expires"]) == 1
    with pytest.raises(SystemExit):
        taches.main(["lancer", "tache-inconnue"])
