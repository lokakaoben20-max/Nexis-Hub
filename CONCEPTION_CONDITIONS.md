# Conception : la case des conditions d'utilisation, obligatoire partout

Demandée par Ben le 2026-11-20 : une case à cocher obligatoire pour les
conditions générales d'utilisation (CGU), sur **toutes les plateformes** (app
mobile, bot Telegram, Mini App, WhatsApp), juste après l'inscription d'un
client ou d'un prestataire, à la première inscription **et** quand un client
devient prestataire. Sans la case cochée, on ne continue pas.

Remplace la branche `claude/project-thread-saq7uu` (octobre 2026, jamais
fusionnée), écrite avant les comptes Nexis, les routes au nom de l'acteur et
la Mini App branchée au backend. Différence de fond : l'ancienne conception
laissait tout passer tant qu'aucun texte n'était publié ; celle-ci bloque.

## Règles (une seule source : `backend/app/conditions.py`)

1. **Le backend décide, les canaux affichent.** Aucun canal ne garde une
   trace locale de l'acceptation.
2. **Une acceptation appartient au compte Nexis**, jamais à un identifiant de
   canal : une personne qui relie WhatsApp à son compte Telegram ne recoche
   rien.
3. **Documents exigés** :

   | Rôle | Documents |
   | --- | --- |
   | Client | `cgu` |
   | Prestataire | `cgu` et `conditions_prestataires` |

   Un client qui devient prestataire coche les conditions des prestataires
   (et les CGU si une nouvelle version est entrée en vigueur entre-temps).
4. **L'inscription porte la case.** `PUT /api/me/client-profile`,
   `PUT /api/me/provider-profile` (inscription et bascule) et
   `POST /api/whatsapp/client` reçoivent `terms: {surface, documents}`. Le
   profil et l'acceptation sont écrits **dans la même transaction** : sans
   case, rien n'est créé (ni compte, ni profil). Refus `terms_not_accepted`
   (409) avec la liste `missing` des versions à cocher.
5. **On accepte le texte qu'on a vu.** Une acceptation nomme une version ;
   si ce n'est plus celle en vigueur : `terms_version_outdated` (409), le
   canal remontre la case avec la nouvelle version, rien n'est enregistré.
6. **Nouvelle version en vigueur** : chacun recoche avant toute **nouvelle
   action** (`terms_not_accepted`). Restent toujours possibles : lire,
   finir ce qui est engagé (présence, fin de mission, confirmation, litige,
   accord amiable, note), **retirer son propre argent**, se mettre hors
   ligne, refuser une alerte ou un devis, régler sa langue, sécurité du
   compte, admin. Une personne qui refuse les nouvelles conditions n'est
   jamais privée de son argent.
7. **Aucune version publiée = personne ne passe** (`terms_unavailable`, 503).
   La case est obligatoire : on ne laisse pas entrer sans elle faute de
   texte. Publier les versions est une étape de la mise en service.
8. **Idempotence** : cocher de nouveau une version déjà acceptée ne crée
   rien (unicité compte + version en base, compte verrouillé pendant
   l'écriture). Sur WhatsApp, le même message rejoué rend la même réponse.
9. **Prestataires proposés aux missions** : seulement ceux qui ont accepté
   la version en vigueur des conditions des prestataires
   (`profils.eligible_providers`). Se rendre « disponible » l'exige aussi.

## Données (migration `a9b0c1d2e3f4`, tables neuves et vides)

- `legal_document_versions` : `document_key`, `version`, `language`, `text`
  (texte exact publié), `text_sha256`, `effective_at`, `published_at`.
  Unique sur (`document_key`, `version`). **Jamais modifiée ni effacée** :
  un texte corrigé est une nouvelle version. Version en vigueur = la
  dernière dont `effective_at` est passée (on peut annoncer une version à
  l'avance).
- `legal_acceptances` : `account_id`, `version_id`, `role` (client ou
  prestataire), `surface` (`telegram_bot`, `mini_app`, `whatsapp`, `app`),
  `language` (langue de l'écran), `accepted_at`. **Ajout seul**, unique sur
  (`account_id`, `version_id`).

Conservation de ces preuves : question ouverte pour le juriste (comme les
autres données d'argent), rien n'est effacé en attendant.

## Chaque route déclare ce qu'elle exige

Dans `backend/app/main.py`, chaque route porte `@needs_terms(CLIENT)`,
`@needs_terms(PROVIDER)` ou `@terms_exempt`. Une route sans déclaration
**empêche le démarrage** (`check_route_policies`), et la liste exacte des
routes qui exigent la case est fixée par
`backend/tests/test_conditions_api.py` : toute nouvelle route est un choix
explicite.

Exigent la case : créer une mission, accepter un devis, payer (wallet ou
Mobile Money), envoyer un besoin hors catalogue (client) ; envoyer un devis,
proposer un service au catalogue, changer ses services ou ses communes,
envoyer une photo de réalisation, demander un service de plus
(prestataire).

## API

Bots (`X-API-Key` du canal, en-têtes d'acteur) :

- `GET /api/me/terms` : `missing` (à recocher pour les rôles de la
  personne), `role` (à envoyer avec), `by_role` (écran d'inscription ou de
  bascule), `complete`.
- `POST /api/me/terms` : `{role, surface, documents}` pour un rôle que la
  personne a déjà (`role_not_held` sinon). Idempotente pour WhatsApp.
- `GET /api/legal/documents/{cle}` et `/{cle}/{version}` : texte exact.

Application (`/api/app/v1`, session) : `GET /legal/documents/...`,
`GET /me/terms`, `POST /me/terms` (surface `app`). L'inscription dans l'app,
quand elle sera construite, portera la case comme les routes du bot
(`conditions.accept_for_signup`).

## Canaux

- **Bot Telegram** (`telegram_bot/conditions.py`, `registration.py`) :
  dernier écran de l'inscription client (après « Partager mon numéro ») et
  prestataire (après les photos) : un bouton par document (page de lecture,
  ou texte envoyé en morceaux sans adresse publique), un bouton ☐/☑️
  « J'ai lu et j'accepte » et « Valider ». Le filtre `ConditionsGate`
  montre la case avant toute nouvelle action quand une version manque (liste
  d'exemptions identique aux routes exemptées du backend). Backend
  injoignable : on bloque. Résultat « rien ne manque » gardé 5 minutes, et
  oublié dès que le backend refuse une action pour cette raison.
- **Mini App** : vraie case à cocher à l'inscription prestataire (et à la
  bascule), écran « Nouvelles conditions » avant tout le reste si une
  version manque, page de lecture publique `/conditions/{cle}/{version}`
  (texte exact échappé), aussi utilisée par le bot.
- **WhatsApp** (le service n'existe pas encore) : contrat prêt et testé.
  L'inscription envoie `terms` avec la surface `whatsapp` ; l'écran sera un
  message avec le lien de lecture et un bouton de réponse « J'accepte ».
- **Application** : contrat prêt et testé (voir API).

## Mise en service (sur le PC de Ben, puis sur l'hébergement)

```
python -m alembic upgrade head
python -m backend.app.conditions publier cgu 2026-11-20 chemin\cgu.md
python -m backend.app.conditions publier conditions_prestataires 2026-11-20 chemin\prestataires.md
python -m backend.app.conditions liste
```

Tant que ces deux versions ne sont pas publiées, aucune inscription n'aboutit
et aucune nouvelle action n'est possible. Les textes actuels sont des projets
en attente du juriste : en test, publier le projet ; avant le lancement,
publier la version validée (une nouvelle version, jamais une réécriture).
Une version annoncée à l'avance : `--en-vigueur 2026-12-01T00:00` (UTC).

## Tests

- `backend/tests/test_conditions.py` : règles, contraintes de la base,
  prestataires proposés, commande d'exploitation.
- `backend/tests/test_conditions_api.py` : inscriptions (Telegram, WhatsApp),
  bascule, nouvelle version, ce qui reste ouvert, déclaration de chaque route.
- `backend/tests/test_app_public_api.py` : routes de l'application.
- `backend/tests/test_conditions_migration.py` : migration sur Postgres.
- `tests/test_conditions_bot.py`, `tests/test_mini_app.py` : écrans et filtre.

Les autres tests partent d'un monde « rien à cocher » (fixture
`_conditions_hors_sujet` de `conftest.py`) ; ceux de la règle portent la
marque `conditions_reelles` et gardent la vraie exigence.
