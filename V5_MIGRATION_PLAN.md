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

**Statut : ✅ Terminée.** Postgres local via `docker-compose.yml`, schéma dans
`backend/app/models.py`, migrations Alembic (`backend/alembic/`), endpoints
existants réécrits contre la DB. `db.py` reste en fallback, inchangé.

## Phase 1 — Compléter la logique métier du backend

**Objectif** : que le backend V5 porte réellement toute la logique déjà présente
dans `db.py`/`main.py` pour les flows synchronisés (pas seulement stocker/relire).

- Migrer, flow par flow, la logique métier de `db.py` vers `backend/app/`.
- Ajouter les endpoints manquants au fur et à mesure que `main.py` en a besoin.
- Étendre les tests `backend/tests/` en parallèle de chaque flow migré.

**Risque** : moyen — c'est ici que les bugs de migration de logique apparaissent.

**Statut : logique métier portée côté backend, bot pas encore basculé dessus.**
Le schéma a été étendu (`bot_providers`/`bot_users`/`bot_missions` + nouvelles
tables `bot_quotes`, `bot_transactions`) et `backend/app/crud.py` reproduit
fidèlement la logique de `db.py` : calcul du module prestataire, matching scoré
(`find_matching_providers`), cycle de vie des devis (`create_quote`,
`accept_quote` qui rejette les autres devis), garde-fous de transition d'état
(`start_mission` refuse sans `paid_escrow`), calcul de commission
(15%/10% selon urgence), paiement wallet avec validation de solde, libération
d'escrow avec crédit du wallet prestataire. 26 tests backend passent (SQLite en
test, validé aussi manuellement contre Postgres réel).

**Important — ce qui n'a PAS changé** : `main.py` (le bot) continue d'utiliser
`db.py`/SQLite comme source de vérité pour ces flows ; il ne consomme pas
encore les nouveaux endpoints du backend. Le backend est maintenant *capable*
de porter cette logique, mais le bascule réel du bot vers le backend est une
étape à part, plus risquée (ça change la source de vérité de données de
production), à valider explicitement avant de l'entamer — voir Phase 3 pour le
découplage complet du bot.

**2026-08-02 — premier bascule réel amorcé (flow inscription/profil) :**
En creusant le flow choisi comme point de départ (inscription client/prestataire),
on a trouvé que les changements de **statut**, **langue** et **services** du
prestataire, ainsi que le **compteur d'ignorés consécutifs**, n'étaient jamais
synchronisés vers le backend (seul `db.py` les recevait) — le backend dérivait
silencieusement dès qu'un prestataire changeait de statut ou de langue. Corrigé :

- Ajout des endpoints `PATCH /api/bot/users/{id}/language` et
  `PATCH /api/bot/providers/{id}/language` côté backend (`crud.py`/`main.py`),
  avec tests.
- `main.py` synchronise désormais vers le backend : changement de statut
  (`sync_provider_status_to_backend`), changement de langue client/prestataire
  (`sync_user_language_to_backend`/`sync_provider_language_to_backend`),
  modification des services (`sync_provider_services_to_backend`), et le
  compteur d'ignorés (`sync_provider_ignored_increment_to_backend`/`_reset_to_backend`).
  Tous ces appels sont enveloppés dans `_safe_backend_call` (nouveau helper),
  qui avale toute exception réseau/HTTP — cohérent avec l'exigence de
  tolérance aux pannes réseau du backend (voir AGENTS.md).
- `get_user_language`/`get_provider_language` sont devenues des fonctions
  `async` **backend-first** : elles lisent `/api/profile/{id}` en priorité et
  ne retombent sur `db.py` que si le backend est injoignable ou n'a pas encore
  l'utilisateur/prestataire. C'est le premier vrai bascule de lecture vers le
  backend sur ce projet.

**Volontairement laissé de côté** : l'affichage du profil prestataire
(`profil_prestataire`, `provider_trust_line`, page wallet) continue de lire
`db.py`, car `badge`/`rating`/`total_missions`/`success_rate`/soldes wallet
sont mis à jour par la logique mission/paiement qui, elle, n'est pas encore
câblée sur le backend en production — basculer leur lecture maintenant
afficherait des données obsolètes (souvent à zéro). Ces champs ne pourront
être basculés qu'une fois le flow mission/paiement migré à son tour.

**2026-08-02 — flow suivant : devis (matching/quotes).** Même constat que
pour l'inscription : `create_quote`/`accept_quote`/`reject_quote` n'étaient
jamais synchronisés vers le backend alors que les endpoints existaient déjà
(`POST /api/bot/quotes`, `.../accept`, `.../reject`). Point d'attention
spécifique à ce flow : l'id local du devis (`db.py`, SQLite autoincrement) et
l'id backend (`bot_quotes.id`, Postgres autoincrement) sont deux séquences
indépendantes qui divergent — impossible de réutiliser l'id local pour piloter
l'API backend. Solution : `clavier_devis_client` encode maintenant les deux ids
dans le `callback_data` (`client_accept_quote_{local}:{backend}`, `-` si le
sync de création a échoué), et `_parse_quote_callback_ids` les sépare côté
handler. Le matching (`find_matching_providers`) reste sur `db.py` — mêmes
raisons que pour l'affichage du profil (score dépend de rating/badge non à
jour côté backend).

**2026-08-02 — dernier flow de cette série : paiement/escrow.** Contrairement
aux deux flows précédents, ici la synchronisation vers le backend existait déjà
(`sync_payment_to_backend` sur `mark_quote_paid`/`mark_quote_paid_with_wallet`,
`sync_mission_status_to_backend` sur `start_mission`/`finish_mission`/
`release_payment`). Le bug était ailleurs : ces `await` n'étaient pas protégés
par `_safe_backend_call`. Concrètement, le paiement (mouvement d'argent réel)
avait déjà eu lieu en local au moment de l'appel réseau — si le backend était
injoignable, l'exception remontait et plantait le handler *après* le paiement,
donc ni le client ni le prestataire ne recevaient leur confirmation malgré un
paiement effectivement passé. Corrigé en enveloppant les 5 appels concernés
(`paiement_mobile_money`, `paiement_wallet`, `prestataire_demarre_mission`,
`prestataire_termine_mission`, `client_confirme_mission_terminee`), plus
`sync_mission_to_backend` dans `persist_mission_creation` qui avait le même
défaut. Tests de régression ajoutés pour chacun (backend down ⇒ le sync
retourne `None` au lieu de lever). **Aucun changement de source de vérité** :
`db.py` reste seul à exécuter la logique de paiement réelle ; le backend n'est
encore qu'un miroir best-effort pour ce flow, volontairement — trop risqué pour
basculer sans supervision explicite (argent réel en jeu, voir Phase 6).

**Bilan de cette série (inscription → devis → paiement)** : tous les flows
identifiés au départ ont maintenant une synchronisation backend complète et
tolérante aux pannes réseau.

**2026-08-03 — correction du libellé ci-dessus, après audit.** L'ancienne
formulation ("porter la logique de calcul mission-dérivée... côté backend")
supposait à tort que cette logique existe déjà dans `db.py` et qu'il suffirait
de la recopier côté backend. Un audit détaillé (recherche de chaque écriture
de `rating`/`badge`/`total_missions`/`success_rate`/wallet sur `providers`/
`users` dans `db.py`, comparaison avec `backend/app/crud.py`) montre que ce
n'est vrai que pour les soldes wallet :

- **Soldes wallet (`wallet_balance_usd/cdf`)** : ✅ déjà à parité complète entre
  `db.py` et `backend/app/crud.py` (`mark_quote_paid_with_wallet`,
  `release_payment`). Rien à faire ici.
- **`providers.total_missions`** : n'est incrémenté **nulle part**, ni dans
  `db.py` ni dans le backend (seul `users.total_missions`, côté client, est
  incrémenté à la création de mission).
- **`providers.success_rate`** : n'est calculé **nulle part** ; aucune formule
  n'existe (ni completed/disputed, ni autre).
- **`providers.rating`** : n'est jamais écrit ; la table `reviews` (`db.py`)
  existe dans le schéma mais est totalement inutilisée (aucun `INSERT`, aucun
  handler Telegram de notation, rien pour moyenner vers `providers.rating`).
- **`providers.badge` (tiers `partner`/`expert`/`premium`)** : seul le binaire
  `verified`/`pending` est utilisé (`set_provider_verified`, admin). Les tiers
  ne sont référencés que dans un dict de score utilisé pour le matching
  (`badge_scores`), jamais assignés à un prestataire.
- Trouvé au passage : `add_visit_fee_to_provider` (`db.py`) est du **code
  mort** — jamais appelée nulle part (ni bot ni tests), donc ce n'est pas un
  gap de synchronisation actif. Laissé tel quel pour l'instant (décision du
  2026-08-03), à traiter séparément si besoin.

**Conclusion** : rating / tiering de badge / `total_missions` prestataire /
`success_rate` ne sont pas un travail de *migration* mais une **fonctionnalité
à concevoir puis construire de zéro** (formule de note, seuils de badge,
définition du taux de succès sont des décisions produit, pas des détails
d'implémentation à déduire du code existant). Ce travail n'a pas encore été
lancé — à planifier explicitement avec l'utilisateur avant de coder quoi que
ce soit ici, en cohérence avec la règle "une seule phase/décision active à la
fois" (voir `AGENTS.md`).

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

**Statut : les 4 tâches identifiées sont portées** (`backend/app/tasks.py`,
`backend/app/celery_app.py`, `backend/app/notify.py`). Nouvelle migration
Alembic (`a92fb549a950`) : `created_at`/`status_changed_at` sur `bot_missions`,
`created_at` sur `bot_quotes` — nécessaires pour mesurer "depuis combien de
temps" une tâche périodique doit agir, absents jusqu'ici du schéma backend.
`send_provider_reminders` est une version simplifiée par rapport au fichier
source : le flow bot actuel diffuse une mission aux 3 meilleurs prestataires
simultanément (pas un par un avec escalade séquentielle), donc la tâche
re-notifie les mêmes prestataires matchés à 10 min et 20 min plutôt que de
réattribuer à un "prestataire suivant" — voir le commentaire dans
`backend/app/tasks.py`. Notifications envoyées par appel HTTP synchrone direct
à l'API Telegram (`backend/app/notify.py`), pas par `aiogram.Bot` (le worker
Celery est un process séparé, sans boucle asyncio). Commandes worker/beat
documentées dans `AGENTS.md`.

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

**Statut : premier flow pilote extrait (inscription/profil)**, `telegram_bot/`
(`backend_client.py`, `keyboards.py`, `registration.py`). Deux précisions par rapport à
l'objectif ci-dessus, découvertes pendant l'extraction :

- **Pas encore un service séparé.** Le bot fait du long-polling Telegram — un seul
  process peut consommer les updates avec le token du bot à la fois. `telegram_bot/`
  est pour l'instant un module importé dans le même process que `main.py`
  (`dp.include_router(registration.router)`), pas un service déployé indépendamment.
  Le vrai découplage en process attend que davantage de flows soient migrés.
- **Double écriture maintenue, pas encore "plus jamais d'accès à la DB".**
  `find_matching_providers` (flow mission, pas migré) et la Mini App lisent encore
  `db.py` pour le statut/les services/la langue du prestataire. Le flow migré écrit
  donc toujours dans `db.py` **et** le backend (comme avant l'extraction) — couper
  l'écriture locale maintenant ferait lire une donnée périmée à ces deux lecteurs.
  La coupure complète viendra quand le flow mission/matching sera migré à son tour.
- Petit correctif au passage : `create_mission` (`backend/app/crud.py`) ne posait
  jamais `status="pending"` à la création (contrairement au `DEFAULT 'pending'` SQL de
  `db.py`) — trou de parité comblé, un test existant mis à jour en conséquence.
  `profil_prestataire` (menu prestataire) lisait aussi `badge`/`rating`/
  `total_missions` depuis `db.py`, jamais alimentés côté legacy — bascule vers les
  champs backend réellement calculés (`backend/app/crud.py._recompute_provider_stats`,
  Phase 1).

**Second flow extrait : mission/devis** (`telegram_bot/mission.py`, 16 handlers).
Couvre la création de la demande côté client (choix du service → confirmation →
diffusion aux 3 prestataires matchés) et la réponse du prestataire (acceptation,
saisie du devis, envoi au client, ou passage). **S'arrête volontairement à l'envoi du
devis** : acceptation du devis, paiement, lifecycle et notation restent dans `main.py`
— la partie argent mérite son propre commit, avec sa propre relecture.

Détail d'implémentation à connaître : les handlers extraits utilisent `callback.bot` /
`message.bot` (fourni par aiogram sur chaque événement) au lieu de l'instance globale
`bot` de `main.py`. C'est ce qui permet à un router séparé d'envoyer des messages sans
réimporter `main`, et ce qui rend les envois sortants mockables en test.

**Trois bugs corrigés au passage dans ce flow** :
- L'alerte envoyée aux prestataires matchés était figée en français
  (`get_message("new_mission_alert", "fr", ...)`) : un prestataire lingala ou
  anglophone la recevait dans la mauvaise langue. Idem pour les légendes des photos et
  notes vocales, écrites en dur en français.
- **11 clés de traduction n'existaient que dans `ln.json`** (`ask_client_phone`,
  `phone_required`, `client_registered`, `mission_saved`, `provider_registered`,
  `provider_choose_services`…). Comme `get_message` retombe sur le français quand une
  clé manque, et que le français ne l'avait pas non plus, un client francophone **ou
  anglophone** voyait littéralement `[Message manquant : ask_client_phone]` au premier
  écran d'inscription. Complété dans `fr.json` et `en.json`.
- `tests/test_translations_parity.py` ajouté comme garde-fou : il parse l'AST des
  fichiers source pour extraire les clés réellement passées à `get_message("...")` et
  vérifie qu'elles existent dans les trois langues. Une simple parité de clés entre
  fichiers ne conviendrait pas — le projet contient une dizaine de clés mortes
  présentes dans une seule langue, qui feraient échouer le test sans qu'aucun
  utilisateur ne soit affecté.

**Prochain flow candidat** : acceptation du devis → paiement → lifecycle → notation.
C'est le dernier gros bloc de `main.py`, et celui qui touche à l'argent : à extraire
avec la même prudence (double écriture, aucun changement de source de vérité).

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
