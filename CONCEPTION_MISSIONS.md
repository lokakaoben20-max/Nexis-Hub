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

`db.py` garde encore ses tables de missions et devis, dont le bot et la Mini App
ne se servent plus : l'étape 5 les supprime.
