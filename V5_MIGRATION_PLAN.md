# Plan de migration vers l'architecture cible (`nexis-hub-v5`)

Ce document décrit comment passer du bot monolithique actuel (`Nexis-Hub`) à
l'architecture cible définie dans le repo `nexis-hub-v5` (Postgres, Redis, Kafka,
Celery, microservices Telegram/WhatsApp/backend, IA). Voir [AGENTS.md](AGENTS.md)
pour le statut des deux dépôts.

## Principe directeur

Chaque phase doit rester **déployable et fonctionnelle seule**, sans dépendre des
phases suivantes. On ne casse jamais le bot en prod pour une phase future non finie.
Une seule phase active à la fois, une PR par phase (voir la règle "un seul agent
actif" dans `AGENTS.md`).

## Phase 0 — Vraie base de données pour le backend V5 (fondation)

**Objectif** : remplacer la persistance JSON du backend V5 actuel par PostgreSQL,
sans toucher au bot (`main.py`) ni à ses appels HTTP existants.

- Mettre en place PostgreSQL (local via Docker, ou service managé).
- Porter le schéma de `nexis-hub-v5/backend/app/models.py` (SQLAlchemy) dans
  `backend/app/models.py` de ce dépôt, adapté aux besoins déjà couverts
  (inscription, mission, profil, lifecycle, paiement).
- Ajouter Alembic pour les migrations de schéma.
- Réécrire les endpoints existants de `backend/app/main.py` pour lire/écrire en base
  au lieu du fichier JSON. Les contrats d'API (routes, formats de réponse) ne
  changent pas pour le bot.
- Garder la couche SQLite legacy (`db.py`) comme fallback tant que cette phase
  n'est pas validée en conditions réelles.

**Risque** : faible. Le bot ne voit aucune différence de comportement.
**Prérequis à valider avec toi** : où héberger Postgres (local/dev vs cloud dès
maintenant), et si tu veux garder le fallback JSON en secours pendant la transition.

## Phase 1 — Compléter la logique métier du backend

**Objectif** : que le backend V5 porte réellement toute la logique déjà présente
dans `db.py`/`main.py` pour les flows synchronisés (pas seulement stocker/relire).

- Migrer, flow par flow, la logique métier de `db.py` vers `backend/app/`.
- Ajouter les endpoints manquants au fur et à mesure que `main.py` en a besoin.
- Étendre les tests `backend/tests/` en parallèle de chaque flow migré.

**Risque** : moyen — c'est ici que les bugs de migration de logique apparaissent.
**Sortie de phase** : tous les flows métier existants tournent sur Postgres via le
backend, `db.py` n'est plus utilisé que comme fallback théorique.

## Phase 2 — Tâches asynchrones (Celery + Redis)

**Objectif** : sortir les traitements différés (relances, expiration de devis,
libération auto d'escrow, analytics) d'un code bot qui les gère probablement par
polling/synchronicité aujourd'hui, vers des tâches planifiées fiables.

- Ajouter Redis (broker Celery) + Celery worker/beat.
- Porter les tâches de `nexis-hub-v5/backend/app/tasks.py` et `celery_app.py`,
  en remplaçant les corps `pass`/TODO par la vraie logique (déjà identifiée dans
  les commentaires du fichier source : relances 10/20 min, expiration devis,
  auto-libération après 24h, analytics quotidiennes).
- Vérifier qu'aucune tâche cron/manuelle existante ne fait doublon.

**Risque** : moyen. Nécessite un environnement Redis qui tourne en continu (dev et
prod).

## Phase 3 — Découplage du bot Telegram en service séparé

**Objectif** : extraire les handlers Telegram de `main.py` (87 Ko, fortement
couplé à `db.py`) vers un service `telegram_bot/` qui ne parle au reste du système
que via l'API du backend — plus jamais d'accès direct à la DB depuis le bot.

- Ne démarrer cette phase qu'une fois les phases 0–1 stables : c'est le plus gros
  refactor, à faire sur une base backend déjà fiable.
- Découper `main.py` progressivement (par flow) plutôt qu'en un seul big-bang.
- Les FSM/callbacks Telegram sont identifiés comme point sensible (voir
  `AGENTS.md`) — prévoir des tests de non-régression avant/après chaque
  extraction de flow.

**Risque** : élevé — c'est le refactor le plus invasif du plan.

## Phase 4 — Canal WhatsApp

**Objectif** : ajouter `whatsapp_bot/` comme second canal, une fois que le
backend est channel-agnostic (conséquence de la phase 3).

**Risque** : faible techniquement si la phase 3 est bien faite ; dépend surtout
des accès WhatsApp Business API (à obtenir en amont).

## Phase 5 — Fonctionnalités IA (NLP, transcription, anti-fraude)

**Objectif** : brancher OpenAI (GPT-4o mini pour l'analyse de mission, Whisper
pour la transcription vocale, détection de fraude) sur les tâches Celery de la
phase 2, une par une.

**Risque** : faible à moyen. Introduit un coût variable (API OpenAI) — à
budgétiser. Peut être fait en parallèle des phases 3/4 puisqu'il touche le
backend, pas les canaux.

## Phase 6 — Paiement réel (Mobile Money) et SMS

**Objectif** : remplacer/étendre le flow de paiement actuel par une vraie
intégration escrow (CinetPay, FlexPay) et les notifications SMS (Africa's
Talking).

**Risque** : élevé — argent réel en jeu. Nécessite tests approfondis en
sandbox avant activation, et probablement une revue de sécurité dédiée avant
mise en prod (voir le skill `security-review` si besoin le moment venu).

## Phase 7 — Event sourcing / bus d'événements (Kafka) — optionnel

**Objectif** : le `EventBus`/`EventStore` de `nexis-hub-v5/backend/app/events.py`
est actuellement en mémoire, pas branché sur Kafka. À évaluer **seulement si le
volume/l'échelle le justifie** — c'est la partie la plus coûteuse en complexité
opérationnelle (cluster Kafka à maintenir) pour un bénéfice qui n'est utile qu'à
partir d'une certaine charge ou d'un besoin réel de découplage inter-services.

**Recommandation** : reporter cette phase tant que les phases 0–4 n'ont pas
révélé un vrai besoin de bus d'événements (ex. plusieurs consommateurs
indépendants des mêmes événements).

## Phase 8 — Infra de prod (Docker Compose partout, CI, monitoring)

- Généraliser `docker-compose.yml` (déjà présent dans `nexis-hub-v5`) à
  l'ensemble des services une fois qu'ils existent réellement dans ce dépôt.
- Reprendre `.github/workflows/ci.yml` de `nexis-hub-v5` comme base de CI.
- Ajouter Sentry (déjà prévu dans `config.py` de `nexis-hub-v5`) pour le suivi
  d'erreurs en prod.

## Décisions à prendre avec toi avant de lancer la Phase 0

1. Environnement Postgres : local (Docker) pour commencer, ou tu as déjà un
   hébergement cible en tête ?
2. Est-ce qu'on garde `db.py` (SQLite) comme fallback pendant toute la migration,
   ou on fixe une date de suppression une fois la Phase 1 validée ?
3. Budget/accès déjà disponibles pour les briques externes (OpenAI, CinetPay/
   FlexPay, Africa's Talking, WhatsApp Business API) — ça conditionne à quel
   moment les phases 4–6 sont réellement lançables, indépendamment de l'ordre
   technique ci-dessus.
