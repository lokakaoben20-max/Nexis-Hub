# Conception : pièce d'identité et vidéo du prestataire (côté serveur)

**Statut : proposition, à valider par Ben. Rien n'est codé côté serveur.**
La durée de conservation, celle de la vidéo surtout, est **à voir avec le
juriste** avant tout code. Rédigé le 2026-11-26, après les écrans des apps
natives (`docs/APPS_NATIVES.md`, « Pièce d'identité et vidéo du visage »).

## 1. Ce que l'app envoie

Une demande « Devenir prestataire » porte, en plus des services, des communes
et de la version des conditions acceptée :

| Élément | Format | Taille attendue | Taille refusée au-delà |
| --- | --- | --- | --- |
| Type de pièce | `voter_card`, `driving_licence` ou `passport` | — | — |
| Recto de la carte, ou page photo du passeport | JPEG, 1 600 px au plus grand côté | 150 à 500 Ko | 3 Mo |
| Verso de la carte (**pas pour un passeport**) | JPEG, idem | 150 à 500 Ko | 3 Mo |
| Vidéo du visage | MP4 (H.264), **sans piste audio**, 720p au plus, 2 Mbit/s | 1 à 5 Mo | 12 Mo |
| Consignes de la vidéo | `["left","right"]` ou `["right","left"]` (ordre tiré au sort par l'app) | — | — |
| Durée de la vidéo | secondes (1 à 25) | — | — |

L'app ne décide rien : elle a seulement guidé la prise (carte cadrée, recto
reconnu à la photo de la personne, mouvements de tête faits). **C'est l'équipe
NexisHub qui vérifie la personne.** Aucune image ne part vers un service d'IA
extérieur (règle d'AGENTS.md, inchangée).

## 2. Envoi : deux temps, comme les photos de service

On reprend le modèle déjà en place pour les photos d'un nouveau service
(`backend/app/fichiers.py`, `POST /api/me/files/service-photos`) :

1. **Envoi de chaque fichier** : `POST /api/app/v1/me/identity-files` avec
   l'usage (`identity_recto`, `identity_verso`, `identity_video`). Réponse :
   un identifiant de 128 bits. Le fichier n'est encore rattaché à rien.
2. **Demande** : `POST /api/app/v1/me/provider-application` avec les trois
   identifiants, l'ordre des consignes, la durée, les services, les communes,
   la version des conditions et une **clé d'idempotence** (`idempotency.py`) :
   un double appui ou une reprise après coupure ne crée jamais deux demandes.

Pourquoi deux temps : sur un réseau mobile lent, un fichier qui échoue se
renvoie seul, sans renvoyer les autres.

Contrôles du serveur, chacun testé :

- **type réel** lu dans le contenu, jamais dans le nom : JPEG pour les faces,
  MP4 (boîte `ftyp`) pour la vidéo ;
- **la vidéo n'a pas de son** : le serveur lit les pistes du MP4 et refuse
  toute piste `soun` (la règle « sans son » ne dépend pas seulement de l'app) ;
- **métadonnées retirées** des JPEG (EXIF, position GPS) sans réencoder
  l'image ; même chose pour les métadonnées de lieu du MP4 ;
- tailles maximales ci-dessus ; au plus 3 demandes par compte et par 24 h ;
- verso obligatoire pour une carte, **refusé pour un passeport** ;
- la demande n'est acceptée que si les fichiers appartiennent au compte,
  ne sont rattachés à aucune autre demande et sont encore là ;
- **appareil attesté** (App Attest sur iOS, Play Integrity sur Android,
  `devices.attestation = 'verified'`, déjà dans `app_sessions.py`) : seule
  l'app NexisHub authentique peut envoyer ces fichiers. C'est la seule
  protection serveur contre une image injectée à la place de la caméra.
  **À décider par Ben** : refuser l'étape sur un appareil non attesté, ou
  l'accepter en le signalant à l'équipe.

## 3. Stockage

- **Même mécanisme chiffré** que les photos (AES-256-GCM, un nonce par
  fichier, l'identifiant lié au chiffré, écriture atomique, ligne en base
  validée seulement après l'écriture). Le fichier n'est jamais en base.
- **Clé à part** : `IDENTITY_FILES_ENCRYPTION_KEY`, distincte de
  `FILES_ENCRYPTION_KEY`. Une fuite de la clé des photos de service n'ouvre
  pas les pièces d'identité. Proposition, **à valider par Ben**.
- `stored_files` gagne les usages `identity_recto`, `identity_verso`,
  `identity_video` et le type `video/mp4` (migration Alembic, avec
  `server_default` là où il faut).
- Nouvelle table **`provider_identity_submissions`**, une ligne par dossier
  envoyé :

| Colonne | Rôle |
| --- | --- |
| `id` | numéro du dossier |
| `account_id` | le compte |
| `document_type` | `voter_card`, `driving_licence`, `passport` |
| `recto_file_id`, `verso_file_id`, `video_file_id` | les fichiers (uniques : un fichier n'appartient qu'à un dossier) ; `verso_file_id` vide pour un passeport, imposé par une contrainte en base |
| `head_turns`, `video_seconds` | consignes données et durée |
| `platform`, `app_version`, `device_id`, `device_attestation` | d'où vient l'envoi |
| `status` | `submitted`, `approved`, `rejected`, `superseded` (un nouveau dossier remplace l'ancien), `withdrawn` |
| `decided_by`, `decided_at`, `reason_code` | décision de l'équipe |
| `purge_due_at`, `purged_at` | conservation (section 5) |
| `legal_hold_reason` | suspension de l'effacement (section 5) |

- `provider_profiles.id_document_file_id` et `selfie_file_id` (identifiants
  Telegram) restent pour le parcours Telegram tant qu'il existe ; l'app ne
  les remplit plus. Les rapprocher fera partie de l'étape Telegram.

## 4. Lecture et décision

- **Lecture par l'équipe seulement**, avec un rôle dédié (par exemple
  `identity_reviewer` dans `admin_roles`) : les admins des litiges ne voient
  pas les pièces s'ils n'en ont pas besoin. Lecture par
  `GET /api/admin/identity-submissions/{id}/files/{usage}`, en flux, jamais
  mise en cache.
- **Chaque ouverture est inscrite** (`identity_file_reads` : qui, quand,
  quel fichier, depuis quel canal). La personne peut demander qui a consulté
  son dossier.
- La personne ne relit pas ses fichiers par l'API (elle les avait sur son
  téléphone) ; elle voit seulement l'état de son dossier.
- **Décision** : les routes `verify` / `reject` existantes prennent le numéro
  du dossier. Un refus porte un motif court (`unreadable`, `document_expired`,
  `face_mismatch`, `video_incomplete`, `other`) et un texte pour la personne,
  qui peut envoyer un nouveau dossier. Le profil reste « en vérification »
  jusqu'à la décision ; rien d'automatique.

## 5. Conservation et suppression (à voir avec le juriste)

Le droit applicable est à confirmer par le juriste. Piste : le Code du
numérique (ordonnance-loi n° 23/010 du 13 mars 2023), dont le titre sur les
données personnelles pose la limitation de la durée de conservation. Une
vidéo du visage peut être vue comme une donnée biométrique : le juriste dira
s'il faut une déclaration ou une autorisation préalable auprès de l'autorité
de protection des données.

**Proposition de départ** (chiffres à confirmer ou corriger par le juriste) :

| Cas | Recto et verso | Vidéo |
| --- | --- | --- |
| Fichier envoyé mais jamais rattaché à un dossier | effacé après 24 h | effacé après 24 h |
| Dossier refusé ou remplacé | effacé 30 jours après (délai pour contester) | effacée 30 jours après |
| Dossier accepté | gardé tant que le compte prestataire existe, puis N mois (à fixer) | **effacée peu après l'acceptation (par exemple 30 jours)** ; il reste la ligne « vérifié par X le JJ/MM » |
| Compte supprimé à la demande de la personne | effacé sous 30 jours, sauf blocage légal | idem |

- **Blocage légal** (`legal_hold_reason`) : une fraude signalée ou une
  enquête en cours suspend l'effacement, posé par un admin avec une raison,
  inscrit au journal.
- **Effacement réel** : une tâche quotidienne `purge-identite`
  (`backend/app/taches.py`, verrou Postgres comme les autres) efface le
  fichier chiffré (disque ou bucket), pose `deleted_at` et `purged_at`, et
  vide l'empreinte. Elle est idempotente (relancée, elle ne casse rien).
- **Sauvegardes** : elles contiennent aussi ces fichiers. Leur durée de vie
  doit être bornée (par exemple 35 jours), sinon l'effacement n'est pas réel.
  À régler avec l'hébergement.

## 5 bis. Preuves de réalisations (décision de Ben, 2026-11-26)

**Facultatives**, l'équipe peut en demander. La galerie est permise ici
seulement. **Photos de travaux montrées aux clients après l'accord de
l'équipe** (deuxième décision de Ben, même jour) ; **diplômes et
attestations vus par l'équipe seulement** (le client voit « Diplôme vérifié
par NexisHub »).

- **Envoi** : comme les pièces, en deux temps. `POST
  /api/app/v1/me/work-proof-files` (usages `work_photo` et `certificate`,
  JPEG seulement, 3 Mo au plus, métadonnées retirées), puis `PUT
  /api/app/v1/me/work-proofs` qui **remplace** l'ensemble envoyé (par
  service : 1 à 5 photos et une phrase de 200 signes au plus ; 3
  attestations au plus ; seulement des services de la demande prestataire),
  avec une clé d'idempotence. La demande prestataire peut les porter dès le
  départ.
- **Table `provider_work_proofs`** : compte, service, ordre, fichier, phrase,
  date ; et `work_proof_requests` : compte, services demandés, admin, date,
  date de réponse. Mêmes fichiers chiffrés que les pièces, clé à part ou non
  selon la décision 2.
- **Demande de l'équipe** : `POST /api/admin/providers/{id}/work-proof-requests`
  (services voulus, raison inscrite). Le prestataire reçoit une notification
  par la boîte d'envoi (app, et Telegram ou WhatsApp quand ils seront
  branchés) ; la demande est close par le prochain envoi. Une demande ne
  bloque rien toute seule : c'est l'équipe qui décide.
- **Figées pendant la vérification du prestataire** : `PUT …/work-proofs`
  refusé (`409 portfolio_locked`) tant que la demande prestataire est en
  attente, sauf demande ouverte de l'équipe (et seulement pour les services
  demandés) ; de nouveau permis une fois le prestataire accepté.
- **Revue par l'équipe** : colonne `review` sur chaque service
  (`pending`, `approved`, `rejected`), `reviewed_by`, `reviewed_at`, raison
  si refus ; `certificates_verified_at` sur le compte. `POST
  /api/admin/providers/{id}/work-proofs/{service}/review` (accord ou refus,
  raison inscrite) et `POST …/certificates/verify`. Le prestataire est
  prévenu par la boîte d'envoi. Au remplacement (`PUT …/work-proofs`), le
  serveur compare : service identique (mêmes fichiers dans le même ordre,
  même phrase) → décision gardée ; sinon → `pending`. Diplômes changés →
  vérification retirée. L'app n'envoie jamais de décision (si elle en
  envoie une, elle est ignorée).
- **Lecture par l'équipe** : rôle chargé des prestataires, chaque ouverture
  inscrite, comme les pièces.
- **Lecture par un client** : `GET
  /api/app/v1/quotes/{id}/provider-showcase`, seulement pour un client qui a
  reçu ce devis. Renvoie les services `approved` (photos par adresses
  signées de courte durée, phrase) et un booléen « diplôme vérifié » ;
  **jamais** un fichier `certificate`, ni un service en attente ou refusé,
  ni une donnée de la pièce d'identité. Photos approuvées servies depuis un
  stockage séparé des pièces (elles deviennent publiques pour les clients,
  les pièces jamais). Retrait immédiat si le service repasse en attente, si
  le prestataire les retire ou si le compte est suspendu.
- **Aucune IA** ne les analyse (pas de recherche d'image inversée
  automatique) sans nouvelle décision de Ben.
- **Conservation** (à confirmer par le juriste) : tant que le compte
  prestataire existe ; effacées 30 jours après une demande refusée ou la
  fermeture du compte ; les fichiers remplacés sont effacés par la même
  tâche `purge-identite`.

## 6. Ce qui sera testé

Type réel refusé (PNG renommé, MP4 avec son), taille, fichier d'un autre
compte, fichier déjà rattaché, appareil non attesté, double envoi avec la
même clé d'idempotence, coupure entre l'écriture du fichier et la ligne en
base, lecture sans le rôle, journal de lecture, tâche d'effacement (dates,
blocage légal, relance), migration sur base vide (`alembic upgrade head` puis
`alembic check`).

Pour les preuves de réalisations : service hors de la demande refusé,
6 photos refusées, phrase trop longue refusée, remplacement idempotent,
fichiers remplacés effacés, demande de l'équipe close par l'envoi ; la route
du client ne renvoie que l'approuvé (jamais un diplôme, un service en attente
ou refusé), seulement au client qui a reçu le devis ; un service modifié
repasse en attente et disparaît du client ; une décision envoyée par l'app
est ignorée ; un envoi pendant la vérification sans demande de l'équipe est
refusé.

## 7. Décisions attendues de Ben

1. Valider l'envoi en deux temps et la nouvelle table.
2. Clé de chiffrement séparée pour les pièces : oui ou non.
3. Appareil non attesté : refuser l'étape ou l'accepter avec un signal.
4. Rôle dédié pour lire les pièces.
5. Durées de conservation, **après l'avis du juriste** (la vidéo d'abord).
6. ~~Passeport~~ : tranché par Ben le 2026-11-26, accepté avec la seule page
   photo (fait dans les apps). D'autres pièces (carte de réfugié, titre de
   séjour, pièce étrangère) : plus tard. L'app lit la zone de lecture
   automatique pour reconnaître la page, sans garder le texte ; le serveur
   ne la lit pas non plus tant que Ben ne l'a pas décidé.
