# Instructions pour les agents IA (Manus, Copilot, Codex, Claude Code, etc.)

Ce fichier est le point d'entrée commun pour **tout outil IA** qui travaille sur ce dépôt.
S'il existe un guide plus spécifique à un outil (ex. `MANUS_HANDOFF.md`), il reste valable
pour le détail, mais les règles ci-dessous priment en cas de conflit.

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

## Structure du projet

- `main.py` : handlers Telegram, logique du bot, synchronisation vers le backend V5.
- `db.py` : couche de persistance legacy SQLite (fallback pendant la migration).
- `messages.py` : textes du bot (fr / ln / en).
- `backend/app/main.py` : backend V5 minimal (FastAPI), persistance JSON sur disque.
- `mini_app/` : mini-app web liée au projet.
- `tests/` et `backend/tests/` : tests de régression.

## Avant toute modification

1. Lancer les tests : `c:/Users/CECBK/nexis_hub_bot/.venv/Scripts/python.exe -m pytest -q`
2. Vérifier la branche courante et le statut git (`git status`, `git branch`).
3. Ne pas committer `.venv/`, `__pycache__/`, `*.db`, `.env` (voir `.gitignore`).

## Points sensibles à ne pas casser

- Les handlers Telegram utilisent des callbacks et états FSM.
- Les fonctions de synchronisation vers le backend V5 doivent rester tolérantes aux erreurs réseau.
- Toute évolution du backend V5 doit rester cohérente avec la vision définie dans `nexis-hub-v5`
  (schéma de données, terminologie des statuts) même si l'implémentation reste incrémentale ici.
