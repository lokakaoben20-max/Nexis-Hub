---
name: tests-projet
description: À utiliser en écrivant ou modifiant des tests (dossiers tests/ et backend/tests/), ou en lançant pytest sur ce projet. Couvre le style de test à reproduire, pourquoi vérifier qu'un test échoue vraiment avant de le croire, et pourquoi la suite est lente ici.
---

# Tests — conventions et réalités de ce projet

99 tests, deux dossiers : `tests/` (legacy `db.py` + bot) et `backend/tests/`
(FastAPI + SQLAlchemy). Zéro fixture partagée, zéro `conftest.py` — chaque
fichier est autonome, à reproduire plutôt que d'introduire un nouveau
mécanisme.

## Style à reproduire

**Legacy (`tests/`)** : fonctions simples, base SQLite pointée sur `tmp_path` :

```python
def test_x(tmp_path):
    db.DB_PATH = tmp_path / "test_nexis_hub.db"
    db.init_db()
    ...
```

**Backend (`backend/tests/`)** : `TestClient` + rechargement de module pour
repartir d'une base propre à chaque test :

```python
def test_x(tmp_path, monkeypatch):
    backend_main, database_module = _reload_backend_with_db(monkeypatch, tmp_path)
    with TestClient(backend_main.app) as test_client:
        ...
```

`_reload_backend_with_db` (déjà défini dans `backend/tests/test_main.py`) fait
`importlib.reload` sur `database`, `models`, `main` dans cet ordre précis —
nécessaire parce que `DATABASE_URL` est lu une seule fois à l'import.

Pour un flow mission complet, réutiliser `_setup_mission_with_quote` et
`_complete_mission_flow`, déjà écrits, plutôt que reconstruire la séquence
devis→paiement→démarrage→fin→libération à la main.

## Un test qui passe ne prouve rien tout seul

Un test vert peut simplement ne rien vérifier d'utile. Avant de faire
confiance à un test nouveau ou modifié sur un point sensible (auth, calcul
d'argent), casser volontairement le code qu'il est censé protéger et
confirmer que le test échoue :

```bash
# Exemple réel : vérifier que les tests d'auth de mini_app/app.py mordent
# vraiment, pas seulement qu'ils passent.
# 1. Désactiver temporairement hmac.compare_digest(...) dans verify_telegram_init_data
# 2. Relancer les tests d'auth ciblés -> ils DOIVENT échouer
# 3. Restaurer le fichier, confirmer `git diff` vide
```

C'est ce qui a validé `tests/test_mini_app.py` : désactiver la vérification
de signature fait tomber immédiatement les tests de falsification de payload
et de token différent — la preuve que le test réagit au bon mécanisme, pas
à un effet de bord.

## La suite est lente — ce n'est pas votre code qui rame

Observé sur cette machine : 66 tests entre 90s et 460s selon les runs, 99
tests ~250s. Pas de lenteur particulière liée à un test donné — c'est
probablement le dossier OneDrive (`Startup_Nexis_Hub/nexis_hub_bot`) et/ou
l'antivirus Windows qui scannent chaque fichier SQLite temporaire créé sous
`tmp_path`. Conséquences pratiques :

- Toujours lancer `pytest` avec `run_in_background: true` (ou l'équivalent
  Bash `run_in_background`) et attendre la notification plutôt que de bloquer
  dessus.
- Ne jamais interrompre un run en cours pour "gagner du temps" sans relancer
  ensuite — un run tué en arrête aussi l'information (on ne sait plus s'il
  serait passé).
- Avant de conclure qu'un changement a cassé un test, vérifier qu'on n'a pas
  simplement lu la sortie d'un run précédent ou tronqué.

## Avant de committer un changement sur `crud.py` ou `db.py`

Lancer la suite complète (`pytest -q`), pas seulement les tests du fichier
touché : `crud.py` et `db.py` sont partagés entre plusieurs flows (voir le
skill `parite-donnees`), un changement localisé peut casser un test ailleurs.
