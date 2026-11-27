# Instructions pour les agents IA (Manus, Copilot, Codex, Claude Code, etc.)

## Décisions de Ben en vigueur

Le document `claude/decisions-en-vigueur.md` liste les décisions de Ben en vigueur (détail dans `claude/journal-relais.md`). Il se trouve dans le projet « Nexis Hub Relais » et, en copie, dans le dépôt **privé** `lokakaoben20-max/nexis-hub-docs`, branche `claude/relais-docs`. **Ne jamais copier ces fichiers dans ce dépôt, qui est public.** **À lire au début de chaque session.** Quand une de ses décisions contredit une autre note de ce fichier, c'est le document qui compte. Une session sans accès à ce projet demande le fichier à Ben. Toute nouvelle décision de Ben s'y ajoute, et l'ancienne y est barrée avec ce qui la remplace.

- **Le nom s'écrit « NexisHub », en un mot** (depuis le 25 novembre 2026). Les mentions « Nexis Hub » plus bas dans ce fichier sont l'ancienne forme : ne pas les suivre pour les textes visibles (exception voulue : VoiceOver et TalkBack lisent « Nexis Hub »).

Ce fichier est le point d'entrée commun pour **tout outil IA** qui travaille sur ce dépôt
(remplace l'ancien `MANUS_HANDOFF.md`, qui était spécifique à un seul outil — son contenu
a été fusionné ici).

## État actuel

- Le dépôt à jour est la branche d'intégration `feature/mobile-money` (HEAD du 2026-11-20 : `fed4a85a`). Les branches de travail doivent partir de cette base, pas de `main`, `develop/nexis-unification` ou `agent/frontend-ux`.
- Le backend V5 est la source de vérité métier et financière dans PostgreSQL. `db.py` a été supprimé le 2026-11-14.
- Le bot et la Mini App utilisent Redis pour les états de conversation. Le dépôt fournit Postgres 17 et Redis 7 dans `docker-compose.yml`.
- Les migrations du backend sont gérées par Alembic. Toujours exécuter `python -m alembic upgrade head` avant de lancer le backend.
- Les tâches planifiées n'utilisent plus Celery : `backend/app/taches.py` porte le calendrier, lancé localement avec `python -m backend.app.taches planificateur`.
- Les flows Telegram sont extraits dans `telegram_bot/` et chargés dans le même processus que `main.py`.
- `whatsapp_bot/` (étape 4 du plan WhatsApp) est un processus séparé (`python -m whatsapp_bot`, rôle Docker `whatsapp`) : webhook Meta signé, chaque message traité une fois (Redis + idempotence du backend), inscription client, menu, refus prestataire, création d'une mission pas à pas (`whatsapp_bot/demande.py`, étape 5), « Mes demandes », décision sur les devis (`whatsapp_bot/devis.py`) et paiement wallet ou Mobile Money (`whatsapp_bot/paiement.py`), étape 6, suivi d'une demande payée (arrivée, fin, problème, avis) et « Mon solde » (`whatsapp_bot/suivi.py`), étape 7, litige : contester la décision et proposer un accord (`whatsapp_bot/litige.py`), étape 7b. Il ne parle au backend que par son API. Toute écriture ouverte à WhatsApp passe par `_run_idempotent` ; une règle qui valide elle-même utilise `transactions.commit(db)` pour rester dans la transaction de la clé. Tests : `whatsapp_bot/tests/` avec le faux serveur Meta (`whatsapp_bot/fake_meta.py`).

### Démarrage local — état du code au 2026-11-20

À lancer depuis la racine du dépôt, dans des terminaux séparés :

1. Copier `.env.example` en `.env`, renseigner le jeton Telegram, l'URL Postgres et une clé `BACKEND_API_KEY_TELEGRAM` identique dans les processus backend, bot et Mini App (32 caractères au moins).
2. Démarrer Postgres 17 et Redis 7 : `docker compose up -d`.
3. Appliquer le schéma : `python -m alembic upgrade head`.
4. Démarrer le backend : `python -m uvicorn backend.app.main:app --reload`.
5. Démarrer le bot : `python main.py`.
6. Démarrer le calendrier local des tâches : `python -m backend.app.taches planificateur`.

### Admins et interrupteurs Mobile Money

Les rôles admin sont conservés dans `admin_roles`. Utiliser `python -m backend.app.admins ajouter <telegram_id> --raison "..."`, `python -m backend.app.admins retirer <telegram_id> --raison "..."` ou `python -m backend.app.admins liste`. La raison est obligatoire pour ajouter ou retirer un rôle, pas pour afficher la liste. `ADMIN_TELEGRAM_ID` ne confère aucun rôle et sa présence est refusée hors développement.

Les admins Telegram peuvent afficher l'état avec `/interrupteurs`, couper un flux avec `/couper encaissements <raison>` ou `/couper versements <raison>`, et le rouvrir avec `/rouvrir encaissements <raison>` ou `/rouvrir versements <raison>`. En secours depuis le serveur : `python -m backend.app.interrupteurs etat`, puis les sous-commandes `couper` / `rouvrir` avec `--raison`.

**Adresse publique :** le code de cette branche ne lit pas `NEXIS_PUBLIC_URL`. Il lit `MINI_APP_URL` pour le lien Mini App et `WEBHOOK_URL` pour le webhook Telegram. Le tunnel de test indiqué (`https://nexishub.dpdns.org`) n'est donc pas encore un réglage unique reconnu par le code ; ne pas présenter cette unification comme déjà implémentée.

## Exigence de qualité (non négociable, demandée par Ben le 2026-10-02)

Nexis Hub manipule de l'argent réel. Ben veut un produit très solide et n'acceptera
jamais de solution provisoire. Cette exigence s'applique à tout agent et à toute tâche,
et passe avant la rapidité.

- **Aucune solution provisoire.** Pas de contournement, pas de pansement, pas d'état
  intermédiaire fragile, pas de « on corrigera plus tard ».
- **Proposer la bonne solution**, même si elle est plus grosse que prévu : avec son
  découpage en étapes, ses risques et les tests qui la prouvent. Chaque étape livrée doit
  être complète et correcte en elle-même.
- **Si ce n'est pas faisable proprement maintenant, le dire** au lieu de livrer un
  demi-correctif : expliquer ce qui manque (décision, accès, prérequis) et ce qu'il faut
  pour le faire correctement.
- **Toute règle qui touche à l'argent** (paiement, escrow, wallet, commission, litige,
  remboursement, versement) :
  - a **une seule source de vérité** ;
  - est **atomique** (tout ou rien, jamais à moitié écrite) ;
  - est **idempotente** (un double clic, un rejeu ou une relance ne paie jamais deux fois) ;
  - est **testée**, y compris les cas d'échec et de panne ;
  - **échoue en sécurité** : en cas de doute ou de service injoignable, on refuse
    l'opération plutôt que de risquer un mauvais mouvement d'argent.
- Une recommandation présentée à Ben est la solution définitive visée, jamais une
  étape « en attendant ».

## Intelligence artificielle dans le produit (décidé par Ben le 2026-11-20)

Ceci concerne l'IA **dans Nexis** (assistants, tri, détection), pas les agents qui codent.

- **L'IA aide, elle ne décide jamais seule** une action irréversible. Aucune IA ne déclenche,
  ne bloque ni ne calcule un mouvement d'argent (paiement, libération, remboursement,
  retrait, partage de litige), ne valide ni ne refuse un prestataire, ne sanctionne personne
  et ne fixe aucun prix. Ces décisions restent au backend (règles écrites et testées) ou à un
  humain de l'équipe Nexis.
- Toute suggestion d'IA est **tracée** (entrée, réponse, qui l'a suivie ou écartée) et
  **contestable** par la personne concernée.
- **Consentement et confidentialité** : aucune donnée personnelle (pièce d'identité, selfie,
  numéro, position) n'est envoyée à un service d'IA extérieur sans avis juridique préalable
  et accord explicite de Ben.
- L'**antifraude** commence par des **règles explicites** (seuils, journal d'alertes, revue
  humaine, recours), pas par de l'IA.
- Aucune fonctionnalité d'IA n'est présentée comme « opérationnelle » sans test de bout en
  bout, ni sans mesure du coût, de la qualité (y compris en lingala) et des faux positifs.
- **Ordre décidé** : pas d'IA avant le lancement. Après le lancement, avec de vraies données :
  1) pilote d'**assistant interne pour l'équipe admin** (résumé d'un litige avant décision,
  tri des alertes et des « Mon besoin n'est pas dans la liste ») ; 2) plus tard, assistant
  client limité (aider à choisir le bon service), après relecture du lingala, avis juridique
  et vérification des règles Meta sur l'IA dans WhatsApp ; 3) en dernier, aide au contrôle
  des pièces d'identité, seulement si l'avocat l'autorise. L'aide à la rédaction des devis
  n'est pas prévue : le prix reste la décision du prestataire.
- **Exception décidée par Ben le 2026-11-26 : guidage de la prise d'identité, sur le
  téléphone.** Dans l'étape « Pièce d'identité » de « Devenir prestataire » (apps natives),
  l'analyse d'image **sur le téléphone** est autorisée dès maintenant pour guider la prise :
  Vision / VisionKit / AVFoundation sur iOS, CameraX + ML Kit (scanner de documents,
  visages, angle de la tête) sur Android. Elle sert seulement à cadrer la carte et la
  photographier toute seule, à dire si la face montrée est le recto ou le verso, et à
  vérifier que chaque mouvement de tête demandé pendant la vidéo est fait. **Elle ne
  valide ni ne refuse personne** : c'est l'équipe NexisHub qui vérifie la personne. Jamais
  de photo ni de vidéo choisie dans la galerie (scanner ML Kit avec
  `setGalleryImportAllowed(false)`). La règle de confidentialité ci-dessus reste entière :
  **aucune pièce ni aucun selfie n'est envoyé à un service d'IA extérieur** sans l'avis du
  juriste et l'accord de Ben.
  Les **preuves de réalisations** (photos de travaux déjà faits, diplômes ou
  attestations) sont la seule partie de « Devenir prestataire » où la galerie est
  permise (décision de Ben, même jour) : elles sont **facultatives**, l'équipe peut en
  demander plus tard, et aucune IA ne les analyse. Les **photos de travaux** sont
  montrées aux clients, avec la phrase du prestataire, **seulement après l'accord de
  l'équipe** (service par service ; un service modifié repasse par l'équipe). Les
  **diplômes et attestations** restent vus **par l'équipe seulement** : le client voit
  « Diplôme vérifié par NexisHub », jamais le document. Pendant que l'équipe vérifie le prestataire,
  ses réalisations sont figées (sauf demande de l'équipe).

## Objectif du projet

Ce dépôt contient un bot Telegram pour Nexis Hub avec une migration progressive vers une
architecture V5 backend-driven. Le spec V5 a été défini par Manus (voir `nexis-hub-v5`
ci-dessous) ; la mise en œuvre actuelle doit rester alignée avec cette vision et servir de
base de travail pour la suite.

## Design des interfaces Nexis Hub

Pour tout travail d'interface dans le projet (application Flutter, Mini App,
aperçus web et futurs écrans), lire et appliquer le guide
[Frontend Design d'Anthropic](https://github.com/anthropics/skills/blob/main/skills/frontend-design/SKILL.md).
Pour les parcours Telegram et WhatsApp, appliquer les mêmes principes de
hiérarchie, de libellés et de retour après une action, selon les capacités du canal.

- Partir de l'interface réellement déployée et des décisions de design validées
  par Ben. Conserver l'identité Nexis : bleu vif `#0A63F0` comme couleur principale, monogramme blanc sur l’icône, Unbounded pour les
  titres et Inter pour le texte, avec une mise en page premium et épurée.
- Prendre les maquettes validées par Ben comme référence visuelle pour chaque
  nouvel écran. Réutiliser les composants Nexis, notamment les champs, boutons,
  pictogrammes et espacements. Comparer le rendu côte à côte avec les écrans
  validés du même parcours avant de le présenter.
- Donner la priorité à l'action utile sur chaque écran. Limiter le mouvement
  aux interactions et aux indications ponctuelles, respecter la réduction des
  animations et vérifier les états de focus et la lisibilité.
- Vérifier les écrans modifiés dans un aperçu à largeur de téléphone, avec les
  langues et les états concernés. Distinguer dans le compte rendu le rendu
  observé dans l'aperçu des résultats vérifiés uniquement par les tests.

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

## Profils : le backend est la seule mémoire (chantier profils terminé le 2026-11-14)

Il n'y a plus de base locale : `db.py` et son fichier SQLite ne font plus partie du
code (supprimés à l'étape 4). Profils,
langue, disponibilité, services proposés, catalogue (services et communes) et choix
des prestataires prévenus d'une mission passent tous par le backend, au nom de la
personne (routes `/api/me/*`). Backend injoignable = « service indisponible », jamais
une copie locale. Le catalogue est lu une fois au démarrage du bot
(`telegram_bot/catalogue.py`) : sans lui, le bot refuse de démarrer.

- La reprise des profils de l'ancien fichier SQLite se fait une seule fois, sur le PC,
  bot et Mini App arrêtés : `python -m outils.reprise_profils_sqlite nexis_hub.db`
  (rapport), puis la même commande avec `--appliquer`.
- Le fichier `nexis_hub.db` d'un PC n'est ni lu ni effacé par le code : seul le script de
  reprise l'ouvre, en lecture seule. Ne jamais le committer (`*.db` dans `.gitignore`).
- Les tests du bot tournent contre le vrai backend en mémoire (fixture `live_backend`
  de `tests/conftest.py`) : lance toute la suite (`pytest -q`), pas seulement les tests
  du module que tu modifies.

### Ports (les services peuvent tourner en même temps)

| Service | Port | Commande |
| --- | --- | --- |
| Backend V5 | 8000 | `.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload` |
| Mini App | 8001 | `.venv\Scripts\python.exe -m uvicorn mini_app.app:app --reload --host 127.0.0.1 --port 8001` |
| Bot Telegram (polling, défaut) | — | `.venv\Scripts\python.exe main.py` |
| Bot Telegram (webhook, optionnel) | 8002 | `BOT_RUN_MODE=webhook` dans `.env` + `.venv\Scripts\python.exe main.py` |
| Redis (étapes en cours du bot + registre des updates du webhook) | 6379 | `docker compose up -d redis` |
| Tâches planifiées (relances, devis expirés, libérations, Mobile Money, rapports) | — | `.venv\Scripts\python.exe -m backend.app.taches planificateur` |

Ne remets pas la Mini App sur le port 8000 : il appartient au backend V5
(`BACKEND_BASE_URL`). Voir [mini_app/README.md](mini_app/README.md).

Le port 8002 (mode webhook) est le port d'**écoute local** du bot — c'est le
tunnel (ngrok/Cloudflare Tunnel) qui doit le cibler, pas un port exposé
directement sur le réseau. Voir la section démarrage du bot ci-dessous et
le skill `demarrage-local` pour le détail du geste manuel (tunnel à relancer
à chaque session, `WEBHOOK_URL` à mettre à jour dans `.env`).

**Image Docker de production** (`Dockerfile`, `docker/lancer.sh`) : une seule
image, un rôle par processus (`backend`, `miniapp`, `bot`, `webhook-setup`,
`migration`, `tache <nom>`, `planificateur`, `calendrier`,
`controle-registre`). Utilisateur non root, code en lecture seule,
`APP_ENV=production` par défaut (donc configuration complète exigée).
Derrière un répartiteur de charge, poser `FORWARDED_ALLOW_IPS` (lu par uvicorn)
pour que l'adresse du client soit la bonne. Aucun rôle n'écrit à côté du code :
le bot et la Mini App ne gardent rien en local, tout passe par le backend.

**Tâches planifiées : plus de Celery.** `backend/app/taches.py` porte le
calendrier (UTC) et un verrou par tâche (verrou consultatif Postgres) : une
tâche ne tourne jamais deux fois en même temps. Sur le PC, la commande
`planificateur` ci-dessus ; en production, Cloud Scheduler lance
`python -m backend.app.taches lancer <nom>` aux mêmes heures
(`python -m backend.app.taches calendrier` affiche les expressions cron).
Pas de `.delay()` : un envoi qui doit survivre à une panne passe par une
boîte d'envoi en base vidée par une tâche (exemple : l'alerte « Nouvel
appareil », `Device.alert_due_at`, tâche `alertes-nouvel-appareil`).
Toujours lancer depuis la racine du dépôt (`messages` y est importé).

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
- `outils/reprise_profils_sqlite.py` : reprise unique des profils de l'ancien fichier SQLite.
- `messages.py` : textes du bot (fr / ln / en).
- `backend/app/main.py` : backend V5 minimal (FastAPI), persistance JSON sur disque.
- `mini_app/` : mini-app web liée au projet.
- `tests/` : tests de régression pour le bot et la migration V5.
- `backend/tests/` : tests du backend V5.

## Fichiers à consulter en priorité

- [main.py](main.py) : pour les flows bot et la synchronisation V5.
- [backend/app/main.py](backend/app/main.py) : pour les endpoints V5.
- [tests/conftest.py](tests/conftest.py) : fixture `live_backend`, le vrai backend en mémoire pour les tests du bot.
- [backend/tests/test_main.py](backend/tests/test_main.py) : pour les tests backend.

## État actuel

- Le backend V5 persiste dans PostgreSQL, et `db.py` a été supprimé le 2026-11-14 : il n'y a plus de couche SQLite métier locale.
- Redis conserve les états du bot et les updates webhook.
- Les tâches périodiques sont pilotées par `backend/app/taches.py`, sans Celery ni worker/beat Celery.
- Les flows Telegram (inscription, mission/devis, paiement/lifecycle, admin, tableau de bord) sont extraits dans `telegram_bot/` mais tournent dans le même processus que `main.py`.
- Le backend possède des routes explicitement ouvertes au canal WhatsApp et une garde par canal. Le service `whatsapp_bot/` reçoit le webhook Meta (inscription, menu, refus prestataire) ; il n'est encore branché sur aucun compte Meta réel.

## Avant toute modification

1. Démarrer Postgres si besoin : `docker compose up -d` (voir `docker-compose.yml`).
2. Installer les dépendances figées : `pip install --require-hashes -r requirements.txt -r requirements-dev.txt`
   (`requirements.in` liste les dépendances directes ; `requirements.txt` en est la version figée,
   à régénérer avec la commande écrite en tête de `requirements.in`, jamais à la main).
3. Lancer les tests : `c:/Users/Ben L/OneDrive/Desktop/Startup_Nexis_Hub/nexis_hub_bot/.venv/Scripts/python.exe -m pytest -q`
   (les tests backend utilisent SQLite par défaut, pas besoin de Postgres pour les faire passer).
   Pour les faire tourner sur un vrai Postgres, comme la CI : `NEXIS_TEST_BACKEND_DB=postgres` et
   `NEXIS_TEST_POSTGRES_URL=postgresql+psycopg://<utilisateur>@localhost:5432/<base>_test`
   (base jetable dont le nom finit par `_test` ; une base neuve est créée puis supprimée par test).
4. La CI (`.github/workflows/ci.yml`) refait tout à chaque push : ruff, pip-audit, gitleaks,
   tests sur Postgres 17 et sur SQLite (aucun test sauté), `alembic upgrade head` + `alembic check`
   sur une base vide. Une PR ne se fusionne que si tout est vert.
5. Vérifier la branche courante et le statut git (`git status`, `git branch`, `git remote -v`).
6. Ne pas committer `.venv/`, `__pycache__/`, `*.db`, `.env` (voir `.gitignore`).

### Argent (règle de structure)

Le registre du backend (`backend/app/ledger.py`) est la seule source de
vérité de l'argent : paiement, démarrage et fin de mission, confirmation,
libération, litige, décision admin, soldes. Le bot et la Mini App demandent
et recopient l'état renvoyé, sans aucune copie locale. Backend injoignable = aucune action d'argent. Les wallets sont
rattachés à un compte Nexis (`accounts` + `channel_identities`), jamais à un
canal. Détails : `CONCEPTION_ARGENT.md`.

### Conditions d'utilisation (règle de structure)

La case « J'ai lu et j'accepte » est obligatoire sur tous les canaux, à
l'inscription et à la bascule client -> prestataire ; une nouvelle version
se recoche avant toute nouvelle action. Seule source : `backend/app/conditions.py`.
Chaque route du backend déclare `@needs_terms(...)` ou `@terms_exempt`, sinon
le backend refuse de démarrer. Sans version publiée
(`python -m backend.app.conditions publier ...`), personne ne s'inscrit.
Détails : `CONCEPTION_CONDITIONS.md`.

Le schéma Postgres est géré uniquement par Alembic : lancer
`alembic upgrade head` avant de démarrer le backend (il ne crée plus ses
tables au démarrage).

### Lancer le bot

Le bot garde les étapes en cours (inscription, mission, devis, notation) dans
Redis (`telegram_bot/fsm_storage.py`, variable `REDIS_URL`, défaut
`redis://localhost:6379/0`) pour qu'un redémarrage ne les efface pas. Il refuse
de démarrer si Redis ne répond pas : lancer `docker compose up -d` avant.

```bash
c:/Users/Ben L/OneDrive/Desktop/Startup_Nexis_Hub/nexis_hub_bot/.venv/Scripts/python.exe main.py
```

Par défaut (`BOT_RUN_MODE` absent ou `polling` dans `.env`) : long-polling
classique, aucun tunnel nécessaire. Pour tester le mode webhook (voir
`telegram_bot/webhook_server.py`, `V5_MIGRATION_PLAN.md` section Phase 3) :
lancer un tunnel local (`ngrok http 8002` ou équivalent), copier son URL
HTTPS dans `WEBHOOK_URL`, générer un `WEBHOOK_SECRET_TOKEN`
(`python -c "import secrets; print(secrets.token_hex(32))"`), passer
`BOT_RUN_MODE=webhook` dans `.env`, enregistrer l'adresse chez Telegram
**une fois** avec `python -m telegram_bot.webhook_setup` (à refaire
seulement si l'adresse ou le secret changent), puis relancer la commande
ci-dessus. Le serveur n'enregistre jamais le webhook lui-même : il vérifie
au démarrage que Telegram envoie bien chez lui et refuse de démarrer sinon.
Il traite chaque update avant de répondre à Telegram, une seule fois
(registre Redis `telegram_bot/update_ledger.py`) : Redis est obligatoire.

### Clés de service du backend (une par canal)

Le backend reconnaît le canal qui l'appelle à sa clé (`X-API-Key`) :
`BACKEND_API_KEY_TELEGRAM` pour le bot et la Mini App (obligatoire, même valeur
dans le `.env` des trois), `BACKEND_API_KEY_WHATSAPP` pour le futur service
WhatsApp (vide tant qu'il ne tourne pas). L'ancienne clé unique
`BACKEND_API_KEY` n'existe plus : si elle est encore dans le `.env`, la
renommer en `BACKEND_API_KEY_TELEGRAM` (même valeur), sinon backend, bot et
Mini App refusent de démarrer avec un message qui le dit. Une route du backend
est fermée à WhatsApp sauf `@open_to(...)` ; une action de prestataire porte
`@provider_action` et ne peut jamais être ouverte à WhatsApp (voir
`backend/tests/test_whatsapp_channel.py` et le skill `securite-backend`).

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

- Branche d'intégration à jour : `feature/mobile-money` (au 2026-11-20). Créer une branche dédiée depuis cette base pour chaque tâche, sans utiliser `main`.

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

**Migration webhook Telegram : terminée et validée en conditions réelles
(2026-08-09, commit `1eae8aa`).** L'utilisateur a choisi le "vrai
découplage" (webhooks) comme chantier, périmètre volontairement restreint
après clarification : webhooks seulement, `db.py` reste couplé comme avant
dans `telegram_bot/` (chantier séparé, non lancé), exposition HTTPS via
tunnel local (ngrok) — aucun hébergement de production n'existe. Nouveau
`telegram_bot/webhook_server.py` (`build_webhook_app`/`run_webhook`),
`main.py` en mode dual via `BOT_RUN_MODE` (`polling` par défaut,
`webhook` optionnel), `tests/test_webhook_server.py` (6 tests, secret
token vérifié en temps constant), `aiohttp` ajouté à `requirements.txt`,
nouveau bloc `WEBHOOK_*`/`BOT_RUN_MODE` dans `.env.example`. Suite
complète : 198 passed. Revu par `security-reviewer` (correctif appliqué :
garde du secret déplacée dans `build_webhook_app` elle-même, pas
seulement dans `run_webhook`).

**Test end-to-end réel effectué le 2026-08-09** : ngrok installé
(`winget install Ngrok.Ngrok`, nécessite `ngrok update` après coup — la
version winget est trop ancienne pour l'API ngrok actuelle) et configuré
par l'utilisateur (compte + authtoken), tunnel lancé sur le port 8002,
`BOT_RUN_MODE=webhook` + `WEBHOOK_URL`/`WEBHOOK_SECRET_TOKEN` posés dans
`.env` local (jamais commité), bot lancé et `/start` envoyé depuis
Telegram réel — réponse confirmée par l'utilisateur. Le mode webhook
fonctionne bout en bout, pas seulement en test synthétique.

**Bug `sqlite3.Row` dans `afficher_missions_client` : corrigé et committé**
(commit `0012891`), dans une session séparée qui a démarré depuis la
tâche de suivi `spawn_task` laissée plus haut.

**Chantier de coupure `db.py`, étape A : terminée et committée**
(commit `bb04d3c`, `feat: lire le profil prestataire depuis le backend V5
en priorité`). Audit complet fait avant de coder (3 agents d'exploration
+ vérification manuelle des fichiers cités) : le vrai périmètre est bien
plus gros que "remplacer ~40 appels" — litiges, services proposés et
stats admin n'ont **aucun** équivalent backend, un bug backend bloque la
lecture des missions prestataire, et `find_matching_providers` a un
algorithme de score différent côté backend. Roadmap complète (étapes A-D)
documentée dans `V5_MIGRATION_PLAN.md`, section "Chantier de coupure
db.py". Étape A codée : 4 sites de lecture pure (nom/trust-line/services
prestataire, cohérence langue client) basculés backend-first avec repli
identique à avant, zéro écriture touchée —
`telegram_bot/mission.py::devis_message_recu`,
`telegram_bot/payment.py::client_confirme_mission_terminee`,
`telegram_bot/dashboard.py::afficher_services_prestataire`,
`telegram_bot/registration.py::afficher_profil_client`. Point technique à
retenir : `BotProvider.rating` (backend) n'est **jamais** alimenté, comme
`providers.rating` dans `db.py` — le champ réellement recalculé
(`crud._recompute_provider_stats`) est `average_rating`, d'où un mapping
explicite plutôt qu'un forward direct du dict backend.

**Bug réel trouvé par `backend-parity-auditor` en revue, corrigé avant
commit** : `telegram_bot/backend_client.py::load_profile_from_backend`
propageait `fallback_user` (un `sqlite3.Row` venant de `db.py`) tel quel
dans `{"client": fallback_user, ...}`, alors que tous les appelants font
`.get()` dessus (dict uniquement — `sqlite3.Row` n'a pas cette méthode).
Résultat : `AttributeError` pour tout client ouvrant son profil pendant
que le backend est indisponible — bug préexistant depuis la Phase 3
pilote (commit `99c7526`), pas introduit par l'étape A, mais une
troisième occurrence du même anti-pattern y avait été ajoutée sans le
voir (le test écrit dans la foulée mockait `load_profile_from_backend`
directement, court-circuitant le vrai chemin de repli — corrigé aussi,
`test_afficher_profil_client_survives_backend_unavailable` exerce
maintenant le vrai chemin). Correctif à la racine (fonction partagée,
pas chaque appelant) : `load_profile_from_backend` normalise désormais
`fallback_user` en dict avant de le renvoyer.

**Étape B : terminée et poussée** (commit `c838383`). Bug backend
`profile()` corrigé (`provider_missions` filtrait sur
`BotMission.telegram_id` au lieu de `provider_telegram_id`) +
`dashboard.py::afficher_missions_prestataire` migré vers ce endpoint.
Vérifié avant de corriger : la Mini App a son propre `/api/profile/{id}`
séparé (port 8001, `mini_app/app.py`), non affecté par ce fix backend
V5 (port 8000).

**Étape C : terminée** (backend `9ba1de6`, câblage bot 2026-10-02).
Création et décision admin des services proposés recopiées au backend,
db.py reste la référence (la Mini App n'écrit que dans db.py). Id backend
dans `service_requests.backend_request_id`. Décision admin désormais unique
(`db.py::decide_pending_service_request`), règle stricte validée par
l'utilisateur. Détail dans `V5_MIGRATION_PLAN.md`.

**Étape D : terminée côté code le 2026-10-02** (session cloud depuis le
téléphone, commits `633fb0b` à aujourd'hui) : double versement fermé
(backend et bot, remboursement bloqué si le backend ne répond pas),
matching "mélange" (éligibilité db.py, classement backend via
`POST /api/bot/providers/rank`), prestataires non validés empêchés de se
rendre disponibles, boutons admin prestataire sur `telegram_id`. **Reste en
attente** : la lecture des soldes wallet depuis le backend est codée sur la
branche `claude/project-thread-een159` (commit `c83e373`), à fusionner
seulement si `audit_backend_parity.py` ne montre aucun écart de wallet sur
les vraies bases ; deux textes lingala (`dispute_already_released`,
`provider_status_locked`) à faire relire. Détail dans `V5_MIGRATION_PLAN.md`.

**Prochaine étape — à décider avec l'utilisateur.**

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

## Reprise identité multicanal / WhatsApp — état vérifié le 2026-11-20

La référence produit reste [`docs/ARCHITECTURE_WHATSAPP.md`](docs/ARCHITECTURE_WHATSAPP.md). Le code ci-dessous a été vérifié sur `feature/mobile-money`, HEAD `fed4a85a`.

- Les comptes Nexis, les profils par compte, les wallets par compte et les rôles admin persistés dans `admin_roles` sont dans le backend PostgreSQL.
- Le backend résout l'acteur depuis son canal et son identifiant. La clé de service identifie le canal ; les routes WhatsApp sont ouvertes explicitement et les écritures multicanales sont protégées par idempotence.
- Les routes client WhatsApp sont présentes côté backend, dont `POST /api/whatsapp/client`. Le service `whatsapp_bot/` (étape 4) reçoit le webhook Meta signé et gère inscription, menu, refus prestataire création de mission (étape 5), décision sur les devis et paiement (étape 6), suivi d'une demande payée et « Mon solde » (étape 7), contestation et accords amiables (étape 7b). Une mission d'un client WhatsApp n'a pas de `telegram_id` : le client d'une mission est toujours `client_account_id`.
- Les tâches périodiques tournent via `python -m backend.app.taches planificateur`; Celery n'est plus utilisé.
- Notifications : tout message à une autre personne que celle qui agit passe par la table `notifications` (`backend/app/notifications.py`), écrite avec l'événement par `backend/app/evenements.py`. Ne jamais envoyer directement depuis le bot ou le backend : un test l'interdit. Expéditeur Telegram : `backend/app/notify.py` ; expéditeur WhatsApp et statuts Meta : étape 8.
- Le code ne lit pas `NEXIS_PUBLIC_URL` : `MINI_APP_URL` et `WEBHOOK_URL` restent deux réglages distincts. Le tunnel Cloudflare de test `nexishub.dpdns.org` n'est pas encore exposé comme configuration unique.

Avant de poursuivre WhatsApp : étendre le service de canal (`whatsapp_bot/`, étapes 5 à 7), puis brancher l'expéditeur WhatsApp sur la table `notifications` et la configuration publique commune. Garder cette note et la section d'état au début du fichier synchronisées avec le code.
