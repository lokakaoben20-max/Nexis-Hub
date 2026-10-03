# Conception : enregistrer l'acceptation des conditions

Rédigée le 2026-10-03 à la demande de Ben (fil « Conditions d'utilisation et
documents légaux »). Les textes juridiques eux-mêmes sont des projets en
attente du juriste ; ce chantier construit seulement le mécanisme qui prouve
qui a accepté quelle version, quand et par quel canal.

## Principe

Une acceptation appartient à un **compte Nexis** (`accounts.id`), jamais à un
identifiant Telegram ou WhatsApp : une personne qui relie WhatsApp à son
compte n'a pas à réaccepter. Le backend V5 est la seule source de vérité
(fonctionnalité neuve, construite backend-first, sans copie dans `db.py`).

## Données

Deux tables, écrites uniquement par `backend/app/legal.py` :

- `legal_document_versions` : une version publiée d'un document.
  Champs : `document_key`, `version`, `url` (texte complet consultable),
  `text_sha256` (empreinte du texte exact publié), `effective_at` (date
  d'entrée en vigueur), `created_at`. Unique sur (`document_key`, `version`).
  **Une version publiée n'est jamais modifiée** : un texte corrigé est une
  nouvelle version.
- `legal_acceptances` : un choix d'une personne sur une version.
  Champs : `account_id`, `version_id`, `decision` (`accepted` ou `refused`),
  `channel` (`telegram`, `whatsapp`, `mini_app`), `language`, `decided_at`.
  **Table en ajout seul** : aucune ligne n'est modifiée ni supprimée, même à
  la clôture d'un compte (elle ne contient aucune donnée personnelle hors
  `account_id`). La décision qui compte est la plus récente pour cette
  version : un retrait de consentement s'enregistre comme un refus.

Documents (clés fixes dans le code) :

| Clé | Contenu (dossier juridique) | Exigé de |
| --- | --- | --- |
| `conditions_generales` | Documents 1 à 3 et 5 : conditions générales, paiement et wallet, litiges, conduite | Tout le monde |
| `donnees_transferts` | Consentement aux traitements et aux transferts hors RDC (document 6) | Tout le monde |
| `conditions_prestataires` | Document 4 | Prestataires |

## Règles

1. **Version en vigueur** d'un document : la dernière publiée dont
   `effective_at` est passée. Publier une version à date future permet
   d'annoncer un changement avant qu'il s'applique (CGU, article 14).
2. **Ce qui manque** à un compte : chaque document exigé pour son rôle dont la
   version en vigueur n'a pas, comme décision la plus récente, `accepted`.
3. **Document jamais publié = rien à accepter.** Tant qu'aucune version n'est
   publiée (cas actuel : textes en attente du juriste), personne n'est
   bloqué. La publication des trois versions validées est une étape de la
   mise en service, dans la liste de lancement.
4. **On accepte la version qu'on a vue** : une acceptation porte une version
   précise ; si ce n'est plus la version en vigueur, elle est refusée
   (`terms_version_outdated`) et le bot montre la nouvelle.
5. **Idempotence** : renvoyer la même décision que la plus récente ne crée pas
   de ligne. Le compte est verrouillé (`FOR UPDATE`) pendant l'écriture, pour
   que deux clics simultanés ne produisent pas deux lignes.
6. **Le paiement le vérifie aussi** : `POST /missions/{id}/fund` refuse un
   client à qui il manque une acceptation (`terms_not_accepted`, 409), même si
   le bot a laissé passer. Le contrôle du bot est le confort, celui du backend
   est la garantie.

## API backend

- `GET /api/bot/legal/status?channel=telegram&external_id=…&role=client|provider`
  : versions en vigueur exigées et manquantes (clé, version, url).
- `POST /api/bot/legal/decisions` : `channel`, `external_id`, `document_key`,
  `version`, `decision`, `language`. Crée le compte Nexis au besoin (comme
  le registre d'argent). Refus : 404 `legal_version_not_found`, 409
  `terms_version_outdated`, 422 sur décision ou canal inconnus.
- Publication : script `backend/publish_legal_version.py` (clé, version, url,
  fichier du texte, date d'entrée en vigueur). Il calcule l'empreinte du
  fichier et refuse une version déjà publiée. Pas d'endpoint : publier est un
  acte d'exploitation, pas une action du bot.

## Bot Telegram

- Un filtre (middleware aiogram) passe devant chaque message et chaque bouton,
  sauf `/start`, le choix de la langue et les boutons d'acceptation. Il
  demande au backend ce qui manque ; s'il manque quelque chose, il affiche
  l'écran d'acceptation du premier document manquant (texte court, bouton
  « Lire les conditions » vers l'url de la version, « J'accepte »,
  « Refuser ») et l'action demandée n'est pas exécutée.
- Rôle : `provider` si la personne est inscrite comme prestataire ou appuie
  sur « Prestataire », sinon `client`.
- Un résultat « rien ne manque » est gardé 10 minutes en mémoire par
  personne ; une nouvelle version en vigueur est donc exigée au plus tard
  10 minutes après son entrée en vigueur.
- **Backend injoignable : on bloque**, avec « service momentanément
  indisponible, réessayez ». On ne peut pas savoir si une acceptation manque,
  donc on n'exécute pas l'action (même règle que l'argent).
- L'admin (`ADMIN_TELEGRAM_ID`) n'est pas filtré : il exploite la plateforme,
  il n'en est pas utilisateur.

## Hors de ce chantier

- **WhatsApp** : l'API est déjà indépendante du canal ; le bot WhatsApp
  l'utilisera à son étape 4 (inscription).
- **Mini App** : elle lit et écrit encore `db.py` ; elle passera par la même
  API quand elle sera branchée sur le backend.
- **Textes définitifs** : ceux du bot reprennent les projets de l'onglet
  « Textes dans le bot » du dossier juridique. Ils ne sont visibles qu'une
  fois une version publiée, donc après validation par le juriste.

## Migration

Nouvelle migration Alembic qui crée les deux tables (tables neuves, aucune
donnée existante). Elle suit aujourd'hui `d4e5f6a7b8c9` ; elle sera **rebasée
sur `e6f7a8b9c0d1`** (migration d'identité préparée sur le PC de Ben, pas
encore poussée) avant toute fusion. Tant que ce rebasage n'est pas fait, la
branche ne doit pas être fusionnée : deux têtes Alembic bloqueraient
`alembic upgrade head`.

## Tests

- Backend : version en vigueur (date future ignorée), exigences par rôle,
  acceptation, refus puis acceptation, retrait de consentement, idempotence,
  version périmée, version inconnue, rien de publié = rien d'exigé, compte
  créé au premier choix, même compte via un autre canal relié, paiement
  refusé sans acceptation et accepté après, publication refusée en double.
- Bot : écran affiché et action bloquée s'il manque une acceptation,
  enchaînement des documents, acceptation enregistrée, refus, backend
  injoignable bloque, admin et `/start` non filtrés, cache de 10 minutes.
