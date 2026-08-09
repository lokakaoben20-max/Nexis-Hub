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
  (`main.py`, `mini_app/app.py` et `telegram_bot/` au minimum).
- Préfère **ajouter** une fonction plutôt que changer une signature déjà utilisée.
- La Mini App n'a pas de tests de bout en bout du bot : lance toute la suite
  (`pytest -q`), pas seulement les tests du module que tu modifies.

Corollaire pour les flows déjà extraits vers `telegram_bot/` (Phase 3) : ils écrivent
**toujours** dans `db.py` en plus du backend. Tant que `find_matching_providers` et la
Mini App lisent `db.py`, supprimer une écriture locale sous prétexte que « le backend
l'a » fait diverger silencieusement ces deux lecteurs.

Ce couplage disparaîtra le jour où la Mini App passera par le backend V5 au lieu de
`db.py` — chantier non lancé, voir [V5_MIGRATION_PLAN.md](V5_MIGRATION_PLAN.md).

### Ports (les services peuvent tourner en même temps)

| Service | Port | Commande |
| --- | --- | --- |
| Backend V5 | 8000 | `.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload` |
| Mini App | 8001 | `.venv\Scripts\python.exe -m uvicorn mini_app.app:app --reload --host 127.0.0.1 --port 8001` |
| Bot Telegram (polling, défaut) | — | `.venv\Scripts\python.exe main.py` |
| Bot Telegram (webhook, optionnel) | 8002 | `BOT_RUN_MODE=webhook` dans `.env` + `.venv\Scripts\python.exe main.py` |
| Redis (broker Celery) | 6379 | `docker compose up -d redis` |
| Worker Celery | — | `.venv\Scripts\python.exe -m celery -A backend.app.celery_app worker --loglevel=info --pool=solo` |
| Beat Celery (planificateur) | — | `.venv\Scripts\python.exe -m celery -A backend.app.celery_app beat --loglevel=info` |

Ne remets pas la Mini App sur le port 8000 : il appartient au backend V5
(`BACKEND_BASE_URL`). Voir [mini_app/README.md](mini_app/README.md).

Le port 8002 (mode webhook) est le port d'**écoute local** du bot — c'est le
tunnel (ngrok/Cloudflare Tunnel) qui doit le cibler, pas un port exposé
directement sur le réseau. Voir la section démarrage du bot ci-dessous et
le skill `demarrage-local` pour le détail du geste manuel (tunnel à relancer
à chaque session, `WEBHOOK_URL` à mettre à jour dans `.env`).

**Worker Celery : toujours `python -m celery`, jamais `celery` seul.** Invoqué
directement, l'exécutable `celery` place son propre dossier (`Scripts/`) en
tête de `sys.path` au lieu de la racine du projet — `backend/app/tasks.py`
(qui importe `messages` à la racine) échoue alors avec `ModuleNotFoundError`.
`python -m celery`, lancé depuis la racine du dépôt, résout ce problème.
`--pool=solo` est nécessaire sous Windows (le pool par défaut, `prefork`, n'y
fonctionne pas).

## Structure du projet

- `main.py` : handlers Telegram, logique du bot, synchronisation vers le backend V5.
- `telegram_bot/` : flows Telegram extraits de `main.py` (Phase 3 du plan de migration,
  voir [V5_MIGRATION_PLAN.md](V5_MIGRATION_PLAN.md)) — même process que `main.py` pour
  l'instant (`dp.include_router(...)`), pas encore un service séparé.
  `registration.py` (inscription/profil), `mission.py` (mission/devis),
  `backend_client.py` (appels au backend V5), `keyboards.py` (claviers partagés).
  **Dans ces modules, ne jamais importer `bot` depuis `main.py`** : utiliser
  `callback.bot` / `message.bot`, fournis par aiogram sur chaque événement. Un
  `from main import ...` réexécute tout `main.py` sous le nom `__main__` quand le bot
  tourne via `python main.py`, et crée un second `Bot`/`Dispatcher`.
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
- **Phase 2 terminée** (Celery + Redis, tâches asynchrones).
- **Phase 3 en cours** : 3 flows sur 5 extraits vers `telegram_bot/` (inscription/profil,
  mission/devis, paiement/lifecycle/notation) + vérification obligatoire des prestataires
  ajoutée dans la foulée. Il reste l'admin (12 handlers) et l'affichage missions/wallet
  (6 handlers) — voir "Prochaine étape logique" ci-dessous.

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

Par défaut (`BOT_RUN_MODE` absent ou `polling` dans `.env`) : long-polling
classique, aucun tunnel nécessaire. Pour tester le mode webhook (voir
`telegram_bot/webhook_server.py`, `V5_MIGRATION_PLAN.md` section Phase 3) :
lancer un tunnel local (`ngrok http 8002` ou équivalent), copier son URL
HTTPS dans `WEBHOOK_URL`, générer un `WEBHOOK_SECRET_TOKEN`
(`python -c "import secrets; print(secrets.token_hex(32))"`), passer
`BOT_RUN_MODE=webhook` dans `.env`, puis relancer la commande ci-dessus.
L'URL ngrok change à chaque relance du tunnel (offre gratuite) : à remettre
à jour dans `.env` à chaque session. Aucun hébergement de production
n'existe encore pour ce projet — le webhook n'est utilisable qu'avec un
tunnel local pour l'instant.

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

## Prochaine étape logique — reprendre ici (2026-08-08)

**Phase 3, flow 3 (paiement/lifecycle/notation) : terminé**, puis deux
correctifs et une nouvelle feature construits dans la foulée sur ce même flow :

1. **Extraction paiement/lifecycle/notation** vers `telegram_bot/payment.py`
   (13 handlers + `RatingFlow`), 5 `sync_*` ajoutées à `backend_client.py`,
   claviers + rich-message vers `keyboards.py`. Tests dans
   `tests/test_payment_flow_extraction.py`.
2. **Trou de sécurité corrigé** : `accept_quote`/`reject_quote`/
   `mark_quote_paid*`/`release_payment` (db.py) ne vérifiaient pas que
   l'appelant était le client propriétaire — ajout d'un paramètre
   `client_telegram_id` obligatoire partout, 5 tests de régression.
3. **Écart d'argent backend corrigé** : le bot n'appelait que deux endpoints
   génériques (`/api/bot/missions/status`, `/api/bot/payments`) qui posaient
   des flags sans jamais créditer les wallets Postgres. Étendus pour créer
   de vraies `BotTransaction` et créditer réellement, avec idempotence basée
   sur l'existence de transaction (pas sur `payment_status`, qui peut être
   réécrit sans condition — piège trouvé par `security-reviewer`).
4. **Système de litiges construit** (motif client → statut `disputed` réel +
   gel de `release_payment` → résolution admin : rembourser / payer / partager
   à l'amiable). Deux failles réelles trouvées en revue et corrigées avant
   commit : `open_dispute` sans garde d'état permettait de rouvrir un litige
   sur une mission déjà réglée (double paiement) ; le partage à l'amiable ne
   transmettait pas la part réduite du prestataire au backend (sur-crédit).
   Voir le commit `a405532` pour le détail complet.

Suite complète à jour : **171 passed**. Chaque étape a été revue par
`security-reviewer`/`backend-parity-auditor` (et `i18n-reviewer` pour les
nouvelles clés de message) avant son commit.

**Restent en attente de décision utilisateur, pas construits** :
- Le **partage à l'amiable** ne recalcule pas `success_rate`/`total_missions`
  côté SQLite local (contrairement au backend, corrigé) — `db.py` ne calcule
  ces stats nulle part (confirmé par une note plus bas dans ce fichier),
  cohérent avec l'existant, mais à garder en tête si ces stats deviennent
  affichées côté bot un jour.
- L'étiquette technique `"Mission : NXH-XXXX"` (~100 occurrences dans
  `ln.json`) — l'utilisateur a mis cette question de côté sans trancher.
- Le **partage à l'amiable côté client** : aujourd'hui uniquement déclenché
  par l'admin (aucune demande explicite du client pour un partage) — comme
  voulu.

**Groupe admin : terminé et committé (2026-08-09, commit `05e7c95`, pas encore
poussé).** 18 handlers (`cmd_admin`, `admin_home`, `admin_stats`,
`admin_providers`, `admin_missions`, `admin_clients`, `admin_disputes`,
`admin_litige_rembourser`, `admin_litige_payer_prestataire`,
`admin_litige_demarrer_partage`, `admin_litige_partage_recu`,
`admin_service_requests`, `admin_accept_service`, `admin_reject_service`,
`admin_verify_provider`, `admin_reject_provider`, `admin_suspend_provider`,
`admin_unsuspend_provider`) extraits vers `telegram_bot/admin.py`, avec
`is_admin`/`ADMIN_TELEGRAM_ID` (copie locale, même pattern que
`registration.py`) et FSM `AdminDisputeSplit`. Claviers admin déplacés vers
`keyboards.py`, `sync_provider_verified/suspended/unsuspended_to_backend`
vers `backend_client.py`. Correctif au passage : 6 handlers
(`admin_accept_service`, `admin_verify_provider`, `admin_reject_provider`,
`admin_suspend_provider`, `admin_unsuspend_provider`, `admin_reject_service`)
utilisaient encore le `bot` global de `main.py` — passés à `callback.bot`.
Tests existants (`test_dispute_flow.py`, `test_provider_verification.py`,
`test_bot_backend_sync.py`) mis à jour pour patcher `telegram_bot.admin`/
`telegram_bot.backend_client` au lieu de `main`. Nouveau
`test_admin_flow_extraction.py` (7 tests). Suite complète : **178 passed**.
Revu par `security-reviewer` et `backend-parity-auditor` avant commit,
aucune régression trouvée.

**Groupe missions/wallet : terminé et committé (2026-08-09, commit
`d76600d`, pas encore poussé).** Dernier groupe restant — 10 handlers
(`afficher_services_prestataire`, `proposer_service_manquant`,
`recevoir_nom_service_manquant`, `recevoir_description_service_manquant`
avec FSM `ProviderServiceRequest`, `afficher_missions_client`,
`afficher_wallet_client`, `afficher_missions_prestataire`,
`afficher_wallet_prestataire`, `afficher_historique_client`,
`afficher_aide_client`) + helpers (`mission_value`/`mission_id`/
`format_mission_client`/`format_mission_provider`/`build_help_rich_message`/
`build_history_rich_message`/`STATUS_LABELS`/`PAYMENT_STATUS_LABELS`/
`fetch_backend_missions`) extraits vers `telegram_bot/dashboard.py`. Nouveau
`test_dashboard_flow_extraction.py` (14 tests) — ce groupe n'avait aucun
test dédié avant. Suite complète : **192 passed**. Revu par
`security-reviewer` et `backend-parity-auditor` avant commit (deux
corrections mineures appliquées : garde `isinstance(dict)` dans
`fetch_backend_missions`, mock de test corrigé).

**Phase 3 (extraction de `main.py` vers `telegram_bot/`) : intégralement
terminée.** `main.py` ne contient plus que le bootstrap (113 lignes :
démarrage, `/start`, `/app`, `fonctionnalite_a_venir`). Tous les flows
métier vivent désormais dans `telegram_bot/` : `registration.py`,
`mission.py`, `payment.py`, `admin.py`, `dashboard.py` — plus
`backend_client.py`/`keyboards.py` pour le code partagé.

Nettoyage transversal découvert en cours de route (pas des régressions,
des ré-exports/imports morts déjà présents avant cette session) :
`from telegram_bot.mission import provider_trust_line` dans `main.py`
n'était jamais utilisé par `main.py` lui-même, mais `tests/test_provider_trust_line.py`
comptait dessus via `from main import provider_trust_line` — corrigé pour
importer directement depuis `telegram_bot.mission`. Plusieurs tests
(`test_v5_provider_profile.py`, `test_v5_profile_flow.py`,
`test_v5_payments_flow.py`, `test_v5_mission_lifecycle.py`,
`test_v5_missions_flow.py`, `test_v5_migration.py`,
`test_bot_backend_sync.py`) patchaient `main.httpx` et appelaient des
fonctions ré-exportées par `main.py` (`fetch_backend_profile`,
`load_profile_from_backend`, `_safe_backend_call`, etc.) — corrigés pour
référencer directement `telegram_bot.backend_client`/`telegram_bot.dashboard`.
**Leçon pour la suite** : après avoir retiré un import de `main.py`,
grep `from main import` en plus de `main\.` — un ré-export mort dans
`main.py` peut être invisible à `main\.` seul si le seul appelant importe
le symbole directement plutôt que d'accéder à l'attribut du module.

Bug préexistant découvert (pas une régression, code copié à l'identique) et
volontairement laissé en l'état, avec un test qui documente le comportement
actuel plutôt que de le masquer : dans `afficher_missions_client`,
`isinstance(mission, dict)` est `False` pour un `sqlite3.Row` (missions
locales, fallback quand le backend est indisponible), donc ces missions
s'affichent comme `<sqlite3.Row object at ...>` au lieu du texte formaté.
`afficher_historique_client` n'a PAS ce bug (appelle `format_mission_client`
directement, sans le garde `isinstance`). Correctif de suivi créé
séparément (spawn_task, pas encore traité).

Le vrai objectif de Phase 3 (un service `telegram_bot/` séparé, déployé
indépendamment plutôt que monté dans le même process via
`dp.include_router`) reste à faire — bloqué jusque-là par le long-polling
Telegram (un seul process consommateur par token), voir
`V5_MIGRATION_PLAN.md`.

**Commits `05e7c95` (groupe admin), `d76600d` (groupe missions/wallet),
`d6f455d` (doc Phase 3) : poussés sur `origin/feature/v5-migration`
(2026-08-09).**

**Migration webhook Telegram (2026-08-09, EN COURS).** L'utilisateur a
choisi le "vrai découplage" (webhooks) comme prochain chantier, périmètre
volontairement restreint après clarification : webhooks seulement, `db.py`
reste couplé comme avant dans `telegram_bot/` (chantier séparé, non lancé),
exposition HTTPS via tunnel local (ngrok/Cloudflare Tunnel) — aucun
hébergement de production n'existe. Voir le plan détaillé et son statut
d'avancement dans la session en cours ; résumé une fois terminé : nouveau
`telegram_bot/webhook_server.py` (`build_webhook_app`/`run_webhook`),
`main.py` en mode dual via `BOT_RUN_MODE` (`polling` par défaut,
`webhook` optionnel), `tests/test_webhook_server.py`, `aiohttp` ajouté à
`requirements.txt`, nouveau bloc `WEBHOOK_*`/`BOT_RUN_MODE` dans
`.env.example`.

**Bug `sqlite3.Row` dans `afficher_missions_client`** (signalé plus haut,
tâche de suivi `spawn_task`) : en cours de correction dans une session
séparée au moment de la rédaction de cette note — vérifier l'état réel
(`git log`, `git diff telegram_bot/dashboard.py`) avant de supposer que
c'est fait ou pas.

**Contexte produit à ne pas re-découvrir** : l'utilisateur a envoyé deux
documents de spec (`D:\NEXIS_HUB_Spec_Technique_Bot_v4.docx` et
`D:\NEXIS_HUB_v5_Spec_Technique.pdf`) et a confirmé explicitement que V5 est
l'architecture cible actuelle (déjà suivie via `V5_MIGRATION_PLAN.md`,
correspondance vérifiée ligne à ligne) et que les règles métier détaillées du
v4 (commissions par cas, modules prestataire A/B, badges, actions de
résolution de litige, textes d'écran) restent valables tant que rien de plus
récent ne les contredit — voir la mémoire persistante `spec_v4_v5_relationship`
pour le détail complet. Ne pas redemander cet arbitrage à l'utilisateur.

**Sujets déjà traités, ne pas refaire** : Phase 2 (Celery+Redis), extraction
inscription/profil, extraction mission/devis, vérification obligatoire des
prestataires, extraction paiement/lifecycle/notation, correctif propriétaire
devis/mission, miroir paiement/libération backend, système de litiges — tous
committés et poussés sur `feature/v5-migration` (commits `ae07050`, `99c7526`,
`117e60b`, `b60400e`, `6ca58a1`, `077b8d3`, `a69dd3a`, `a405532`). Extraction
groupe admin (commit `05e7c95`) et groupe missions/wallet (commit `d76600d`,
Phase 3 de découpage `main.py` intégralement terminée) : committées mais
**pas encore poussées** au moment de la rédaction de cette note — vérifier
`git log origin/feature/v5-migration..HEAD` avant de supposer que c'est déjà
sur le remote.

Voir aussi [V5_MIGRATION_PLAN.md](V5_MIGRATION_PLAN.md) pour le plan de migration
complet vers l'architecture cible `nexis-hub-v5`.

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
