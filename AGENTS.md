# Instructions pour les agents IA (Manus, Copilot, Codex, Claude Code, etc.)

Ce fichier est le point d'entrée commun pour **tout outil IA** qui travaille sur ce dépôt
(remplace l'ancien `MANUS_HANDOFF.md`, qui était spécifique à un seul outil — son contenu
a été fusionné ici).

## Objectif du projet

Ce dépôt contient un bot Telegram pour Nexis Hub avec une migration progressive vers une
architecture V5 backend-driven. Le spec V5 a été défini par Manus (voir `nexis-hub-v5`
ci-dessous) ; la mise en œuvre actuelle doit rester alignée avec cette vision et servir de
base de travail pour la suite.

## Dépôt de référence

- **Ce dépôt (`Nexis-Hub` / `origin`) est le seul dépôt actif au quotidien.** C'est ici que vit
  le code réel du bot, et c'est ici que tout agent doit committer son travail.
- `nexis-hub-v5` (remote `v5`) définit **l'architecture cible à terme** (schéma de données,
  event sourcing, découpage microservices Telegram/WhatsApp/backend, Postgres/Redis/Kafka/Celery).
  Aujourd'hui il ne contient que des modèles et des tâches en `pass`/TODO — aucune logique métier.
  La migration vers cette architecture est un **chantier à part entière, planifié explicitement**
  (pas une fusion ad-hoc par un agent qui travaillerait dessus de son côté). Tant que ce chantier
  n'a pas été lancé et validé avec l'utilisateur, continue à développer dans ce dépôt en gardant
  `nexis-hub-v5/backend/app/models.py` comme référence de schéma cible.

## Règle d'or : un seul agent actif à la fois

- Avant de committer, vérifie `git status` et `git log --oneline -5` pour t'assurer qu'aucun
  autre outil n'a un travail en cours non fusionné.
- Ne crée pas de branche ou de worktree "de service" sans nom explicite validé par l'utilisateur
  (évite les noms auto-générés type `xxx-xxx-xxx`).
- Ne pousse jamais directement sur `main`. Travaille sur une branche (`feature/...`), ouvre une PR.

## Couplage à connaître : `db.py` est utilisé par le bot ET la Mini App

Un essai de travail en parallèle (Codex sur le bot, Claude Code sur la Mini App) a été
tenté le 2026-08-05 puis abandonné le jour même : on revient à la règle d'or ci-dessus,
**un seul agent à la fois**. Ce qui reste utile de cet essai, c'est le couplage qu'il a
mis en évidence :

`mini_app/app.py` importe une quinzaine de fonctions de `db.py`
(`get_user_by_telegram_id`, `create_provider`, `start_mission`, `finish_mission`,
`update_provider_services`…), exactement comme `main.py`. **Modifier la signature ou le
comportement d'une fonction de `db.py` pour le bot casse donc la Mini App sans que rien
ne le signale** — et l'inverse est vrai aussi.

- Avant de toucher à une fonction existante de `db.py`, vérifie ses appelants
  (`main.py` et `mini_app/app.py` au minimum).
- Préfère **ajouter** une fonction plutôt que changer une signature déjà utilisée.
- La Mini App n'a pas de tests de bout en bout du bot : lance toute la suite
  (`pytest -q`), pas seulement les tests du module que tu modifies.

Ce couplage disparaîtra le jour où la Mini App passera par le backend V5 au lieu de
`db.py` — chantier non lancé, voir [V5_MIGRATION_PLAN.md](V5_MIGRATION_PLAN.md).

### Ports (les trois services peuvent tourner en même temps)

| Service | Port | Commande |
| --- | --- | --- |
| Backend V5 | 8000 | `.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload` |
| Mini App | 8001 | `.venv\Scripts\python.exe -m uvicorn mini_app.app:app --reload --host 127.0.0.1 --port 8001` |
| Bot Telegram | — | `.venv\Scripts\python.exe main.py` |

Ne remets pas la Mini App sur le port 8000 : il appartient au backend V5
(`BACKEND_BASE_URL`). Voir [mini_app/README.md](mini_app/README.md).

## Structure du projet

- `main.py` : handlers Telegram, logique du bot, synchronisation vers le backend V5.
- `db.py` : couche de persistance legacy SQLite (fallback pendant la migration).
- `messages.py` : textes du bot (fr / ln / en).
- `backend/app/main.py` : backend V5 minimal (FastAPI), persistance JSON sur disque.
- `mini_app/` : mini-app web liée au projet.
- `tests/` : tests de régression pour le bot et la migration V5.
- `backend/tests/` : tests du backend V5.

## Fichiers à consulter en priorité

- [main.py](main.py) : pour les flows bot et la synchronisation V5.
- [db.py](db.py) : pour la logique legacy et les fonctions métier.
- [backend/app/main.py](backend/app/main.py) : pour les endpoints V5.
- [tests/test_bot_backend_sync.py](tests/test_bot_backend_sync.py) : pour les tests de synchronisation bot/backend.
- [backend/tests/test_main.py](backend/tests/test_main.py) : pour les tests backend.

## État actuel

- Le bot est connecté à un backend V5 pour plusieurs flows clés : inscription utilisateur,
  création de mission, profil, lifecycle mission, paiement.
- **Phase 0 de la migration V5 terminée** (voir [V5_MIGRATION_PLAN.md](V5_MIGRATION_PLAN.md)) :
  le backend V5 persiste maintenant dans PostgreSQL (via SQLAlchemy + Alembic), plus dans un
  fichier JSON. Le contrat d'API vu par le bot (`main.py`) n'a pas changé.
- La couche legacy SQLite (`db.py`) reste présente comme fallback pendant la migration.

## Avant toute modification

1. Démarrer Postgres si besoin : `docker compose up -d` (voir `docker-compose.yml`).
2. Lancer les tests : `c:/Users/Ben L/OneDrive/Desktop/Startup_Nexis_Hub/nexis_hub_bot/.venv/Scripts/python.exe -m pytest -q`
   (les tests backend utilisent SQLite en mémoire, pas besoin de Postgres pour les faire passer).
3. Vérifier la branche courante et le statut git (`git status`, `git branch`, `git remote -v`).
4. Ne pas committer `.venv/`, `__pycache__/`, `*.db`, `.env` (voir `.gitignore`).

### Lancer le bot

```bash
c:/Users/Ben L/OneDrive/Desktop/Startup_Nexis_Hub/nexis_hub_bot/.venv/Scripts/python.exe main.py
```

### Lancer le backend V5 en local

```bash
docker compose up -d
c:/Users/Ben L/OneDrive/Desktop/Startup_Nexis_Hub/nexis_hub_bot/.venv/Scripts/python.exe -m uvicorn backend.app.main:app --reload
```

### Migrations de base de données (Alembic)

```bash
# Générer une migration après avoir modifié backend/app/models.py
c:/Users/Ben L/OneDrive/Desktop/Startup_Nexis_Hub/nexis_hub_bot/.venv/Scripts/python.exe -m alembic revision --autogenerate -m "description"

# Appliquer les migrations
c:/Users/Ben L/OneDrive/Desktop/Startup_Nexis_Hub/nexis_hub_bot/.venv/Scripts/python.exe -m alembic upgrade head
```

## Branch Git actuelle

- Branche de travail : `feature/v5-migration`

## Prochaine étape logique

1. Continuer la migration des flows encore dépendants de la DB legacy.
2. Rendre le backend V5 plus complet (base de données réelle si souhaité).
3. Réduire progressivement les dépendances à l'ancienne logique locale.
4. Vérifier que chaque évolution reste cohérente avec le spec V5 défini par Manus.
5. Voir [V5_MIGRATION_PLAN.md](V5_MIGRATION_PLAN.md) pour le plan de migration détaillé
   vers l'architecture cible `nexis-hub-v5`.

## Migration vers un autre profil Windows (transfert local, même machine)

**Statut : ✅ Terminée (2026-08-03).** Le projet vit maintenant à
`C:\Users\Ben L\OneDrive\Desktop\Startup_Nexis_Hub\nexis_hub_bot` (sous OneDrive, pas
directement sous `C:\Users\Ben L\` comme prévu initialement — chemin définitif).

Ce qui a été fait pour finaliser le transfert :
- Dossier `nexis_hub_bot` (avec `.git`, historique complet) et `.env` copiés avec succès.
- `backend/`, `mini_app/`, `tests/` étaient absents après la copie initiale (27 fichiers
  manquants côté disque bien que suivis par Git) — restaurés avec `git checkout -- backend
  mini_app tests`.
- L'ancien `.venv` (chemins `C:\Users\CECBK\...`) était cassé (`Scripts/python.exe` absent) —
  supprimé et recréé. Aucun Python n'était installé sur ce profil (juste le stub Windows
  Store) : installé via `winget install --id Python.Python.3.14` (3.14.6), puis
  `python -m venv .venv` + `pip install -r requirements.txt pytest`.
- Chemins absolus mis à jour dans ce fichier (`c:/Users/Ben L/OneDrive/Desktop/
  Startup_Nexis_Hub/nexis_hub_bot/.venv/Scripts/python.exe`).
- Suite de tests validée : `62 passed` avec `pytest -q`.
- Docker (pour Postgres local) est disponible sur ce profil.

## Points sensibles à ne pas casser

- Les handlers Telegram utilisent des callbacks et états FSM.
- Les fonctions de synchronisation vers le backend V5 doivent rester tolérantes aux erreurs réseau.
- Toute évolution du backend V5 doit rester cohérente avec la vision définie dans `nexis-hub-v5`
  (schéma de données, terminologie des statuts) même si l'implémentation reste incrémentale ici.
- Les tests sont un bon garde-fou avant toute modification majeure.
