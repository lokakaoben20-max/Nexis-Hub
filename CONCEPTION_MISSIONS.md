# Missions et devis : le backend est la seule mémoire

Plan complet : `/mnt/project-files/socle/plan-socle-missions-devis-2026-11-06.md`
(5 étapes). Ce document décrit les règles en place, étape par étape.

## Étape 1 : le backend crée et lit les missions

- `POST /api/bot/missions` (acteur obligatoire). Le client est l'acteur ; le
  backend attribue le numéro (séquence). Aucun canal ne choisit le numéro ni
  le client d'une mission.
- `creation_key` : choisie par le canal pour une demande, réutilisée à chaque
  nouvel essai. Même clé et même demande : la mission déjà créée est renvoyée
  (`created: false`). Même clé, demande différente : refus `creation_key_reused`.
  Unique par compte client (contrainte en base, qui tranche aussi deux
  demandes simultanées).
- Photos et notes vocales (`mission_media`) : rangées avec leur canal, parce
  qu'un identifiant de fichier n'a de sens que pour le canal qui l'a reçu.
- Prestataires prévenus (`mission_alerts`), écrits dans la même transaction
  que la mission. Le canal Telegram les choisit (seul canal des prestataires) ;
  le backend écarte le client lui-même. Seul un prestataire prévenu peut
  envoyer un devis (`provider_not_alerted`, 403), et les relances de 10 et
  20 minutes ne vont qu'aux prévenus.
- `GET /api/bot/missions/{id}` (acteur obligatoire) : client, prestataire
  choisi ou auteur d'un devis, prestataire prévenu, admin. Pour tout autre :
  404, comme un numéro inconnu. Seuls le client et l'admin voient la liste
  des prévenus.
- `GET /api/me/missions?role=client|provider` : missions commandées, ou
  confiées (devis accepté).
- `GET /api/admin/missions?status=` et `GET /api/admin/stats` : admin seulement.

## Étape 2 : le paiement se fait sur le devis enregistré

- Devis (`POST /api/bot/quotes`, acteur = prestataire prévenu) : seulement
  tant que la mission est ouverte (`pending` ou `quoted`), sinon
  `mission_not_open`. Jamais sur sa propre mission (`provider_is_client`).
- Acceptation (`POST /api/bot/quotes/{id}/accept`, acteur = client) : un seul
  devis accepté par mission, les autres sont refusés d'office. Rejouer la même
  acceptation renvoie le même résultat ; accepter un autre devis ensuite :
  `quote_not_open`. Un devis accepté ne se refuse plus.
- `GET /api/bot/quotes/{id}` : client de la mission, auteur du devis, admin.
  Pour tout autre : `quote_not_found` (404), comme un numéro inconnu.
- Paiement (wallet `POST /api/bot/missions/{id}/fund`, Mobile Money
  `POST /api/bot/missions/{id}/payment-intents`) : le canal n'envoie que le
  numéro du devis. Montant, devise, prestataire et urgence sont relus dans le
  devis et la mission enregistrés (`ledger.funding_terms`). Un devis non
  accepté : `quote_not_accepted`. Payer ne crée jamais de mission.

## Étape 3 : le bot Telegram passe par le backend

- Création : le bot choisit les prestataires à prévenir, envoie la demande
  avec une `creation_key` tirée au récapitulatif, et ne prévient que la liste
  renvoyée par le backend. Backend injoignable : rien n'est créé, personne
  n'est prévenu, la demande reste à l'écran pour un nouvel essai avec la même clé.
- Boutons des devis : `quote_accept_{id}`, `quote_reject_{id}`,
  `qpay_mobile_{id}`, `qpay_op_{id}_{opérateur}`, `qpay_wallet_{id}`, avec le
  numéro du devis du backend. Les anciens boutons (numéros de `db.py`) ne sont
  jamais interprétés : ils répondent « bouton plus actif ».
- Mes missions, historique, écrans admin : lus dans le backend. Backend
  injoignable : « service indisponible », jamais une liste locale.

## Étape 4 : la Mini App

- `/api/profile/{id}` lit les missions commandées et confiées dans le backend
  (`client_missions`, `provider_missions`) ; `null` si le backend ne répond
  pas, et la page affiche « Missions indisponibles pour le moment ».

## Étape 5 : `db.py` sans missions

- `db.py` n'a plus de tables `missions`, `quotes`, `reviews` ni de compteur de
  missions par client. Au premier démarrage, les lignes des anciennes tables
  sont écrites dans `<base>_anciennes_missions.json` à côté de la base, puis
  les tables sont supprimées. L'archive est écrite entière avant toute
  suppression ; si elle ne peut pas l'être, rien n'est supprimé. Une archive
  déjà présente n'est jamais écrasée : le bot refuse alors de démarrer.
- Le compteur « Missions totales » du profil vient du backend ; « ? » s'il
  ne répond pas.
- Restent dans `db.py` : profils clients et prestataires, services, demandes
  de service (chantier profils, à faire ensuite).

## Lieu exact de la mission

Plan : `/mnt/project-files/localisation/plan-localisation-temps-reel-2026-11-07.md`
(étape 1, prérequis du suivi du prestataire en route).

- Création (`POST /api/bot/missions`) : `destination` obligatoire, avec
  `latitude`, `longitude` et `landmark` (repère écrit). Le backend vérifie :
  point réel dans un rectangle large autour de Kinshasa, seule zone servie
  (`crud.SERVICE_AREA`, sinon `destination_outside_service_area`), repère de
  3 à 300 caractères (`invalid_destination`). Coordonnées arrondies à
  6 décimales, espaces du repère normalisés. Le lieu fait partie de la demande
  idempotente : même `creation_key` avec un autre lieu, `creation_key_reused`.
- En base : `bot_missions.destination_latitude`, `destination_longitude`,
  `destination_landmark`, tous remplis ou tous vides (contrainte
  `ck_bot_missions_destination_complete` ; vides = mission créée avant cette
  étape).
- Le lieu n'est **jamais** dans la vue de la mission, ni dans les alertes ou
  les notifications. Il a sa propre route,
  `GET /api/bot/missions/{id}/destination` (`crud.destination_access`) :
  - client et admin : toujours ;
  - prestataire choisi : seulement si la mission est payée (`paid_escrow`) et
    `confirmed` ou `in_progress` (il doit s'y rendre ou y travailler) ;
  - prestataire prévenu, auteur d'un devis, prestataire choisi avant paiement
    ou après l'intervention, mission en litige : `destination_not_available`
    (403), il garde la commune ;
  - toute autre personne : `mission_not_found` (404), comme un numéro inconnu ;
  - mission sans lieu enregistré : `destination_unknown` (404).
- Bot Telegram : après la commune, le client envoie le point (bouton
  « 📍 Envoyer ma position » de Telegram, ou 📎 → Position pour un autre
  point ; une position en direct n'est lue qu'une fois, jamais suivie), puis
  écrit le repère. Le repère apparaît dans le récapitulatif. Si le backend
  refuse le lieu à la confirmation, rien n'est créé, personne n'est prévenu,
  et le client renvoie seulement le lieu avant de revenir au récapitulatif.
- Prestataire : bouton « 📍 Voir le lieu » sur les messages de paiement reçu,
  de démarrage et de fin ; le bot lit le lieu dans le backend à l'appui et
  l'envoie comme position Telegram avec le repère.

## Arrivée confirmée

Conception : `/mnt/project-files/localisation/confirmation-arrivee-et-devis-sur-place-2026-11-08.md`
(étapes 1 et 2, décisions de Ben du 8 novembre 2026). Code : `backend/app/presence.py`.

- Plus de « Démarrer la mission » : une mission payée (`confirmed` +
  `paid_escrow`) démarre quand l'arrivée du prestataire est **confirmée**, et
  seulement ainsi. Aucune route ne laisse le prestataire démarrer seul
  (`ledger.start_mission` reste interne ; `ledger.begin_work` démarre sans
  valider, dans la transaction de la présence).
- Confirmée par **un geste avec preuve** :
  - le client appuie « ✅ Oui, il est là » (`POST …/presence/confirm`) ;
  - ou le prestataire tape le **code de présence** à 4 chiffres que le client
    lui donne (`POST …/presence/code`).
  Le « 📍 Je suis arrivé » du prestataire (`POST …/presence/arrived`) ne
  confirme rien : il pose la question au client. La première réponse valide
  fait foi (verrou de la mission) : une seule présence enregistrée.
- Code de présence : HMAC de la clé `PRESENCE_CODE_KEY` (≥ 32 caractères, sinon
  `presence_not_configured`, 503) et du numéro de mission, jamais enregistré.
  Donné au client seulement (dans la question et `GET …/presence`), tant que
  la mission payée attend l'arrivée ; jamais au prestataire, jamais dans un
  journal. Code mal formé : `invalid_presence_code`, non compté. Mauvais code :
  `wrong_presence_code` avec `attempts_left`, compté et enregistré avant le
  refus. 5 mauvais codes : `presence_code_locked`, admin et client prévenus ;
  seul l'appui du client confirme ensuite.
- Question au client : photo (selfie d'inscription) et prénom du prestataire,
  code, rappel « n'acceptez et ne payez un devis que dans Nexis », boutons
  « Oui, il est là », « Pas encore », « Ce n'est pas lui ». Reposée par un
  nouvel appui du prestataire au plus toutes les 2 minutes, ou aussitôt après
  un « pas encore ».
- « Pas encore » (`…/presence/not-yet`) : rien ne bouge ; le prestataire est
  prévenu une fois par question.
- « Ce n'est pas lui » (`…/presence/wrong-person`), après confirmation dans le
  bot : litige ouvert dans la même transaction (fonds gelés, lieu caché au
  prestataire), admin et prestataire prévenus.
- Table `mission_presence` (une ligne par mission, créée au premier
  événement), contraintes : `confirmed_at`/`confirmed_by` ensemble,
  `confirmed_by` ∈ {client, presence_code}, 0 à 5 essais, code bloqué si et
  seulement si 5 essais.
- Messages envoyés par le backend après validation : l'autre partie est
  prévenue, celui qui vient d'agir voit la réponse dans son canal.
- Pas encore fait (étapes suivantes du document) : rappels automatiques au
  client (5 et 10 min) et alerte admin après 20 min de blocage, attendus avec
  le nouveau planificateur (PR #13) ; argent du module B (visite de 5 $, devis
  sur place, rappels au prestataire) ; zone d'arrivée automatique (suivi en
  route, backend hébergé) ; WhatsApp. En attendant le module B, l'arrivée
  confirmée démarre aussi les missions des services du module B.
