# Conception : l'argent de Nexis Hub, backend V5 seule source de vérité

Décidée par Ben le 2026-10-02, initialement sur `feature/argent-backend`,
puis fusionnée dans `feature/v5-migration` (`aa15372`). Remplace
`PLAN_LITIGES_BACKEND.md` et la file de rejeu `backend_outbox`, qui étaient
des étapes transitoires.

## Principe

Un seul endroit décide et enregistre l'argent : le backend V5 (Postgres).
Le bot Telegram demande, puis affiche ; `db.py` ne contient plus aucun solde,
aucune transaction, aucune règle d'argent. Si le backend ne répond pas, aucune
action d'argent n'a lieu et l'utilisateur est invité à réessayer.

Frontière nette : **tout ce qui suit le paiement est décidé par le backend**
(paiement, démarrage, fin, confirmation, libération automatique, litige,
résolution). Ce qui précède le paiement (création de mission, devis,
acceptation) reste dans `db.py` comme aujourd'hui ; la demande de paiement
porte elle-même les informations nécessaires (mission, client, prestataire,
montant, devise, urgence), le backend ne dépend donc d'aucune recopie
antérieure.

## Comptes Nexis : l'argent ne dépend d'aucun canal

Décidé par Ben le 2026-10-02 (fil « Architecture du bot WhatsApp ») : les
clients pourront passer par WhatsApp ou Telegram, les prestataires
uniquement par Telegram, la Mini App ou la future application.

- `accounts` : une personne pour Nexis Hub. Elle peut être cliente,
  prestataire ou les deux, avec **un seul wallet**, une langue partagée et
  les rôles `client` / `provider` synchronisés depuis ses profils.
- `channel_identities` : une porte d'entrée vers un compte (`telegram` +
  telegram_id aujourd'hui, `whatsapp` + wa_id demain). Unique sur (canal,
  identifiant) et un seul canal de chaque type par compte.
- Le registre ne connaît que l'identifiant du compte, jamais un identifiant
  Telegram ou WhatsApp. Ajouter WhatsApp, c'est rattacher une identité au
  compte : aucun mouvement d'argent à migrer.
- Chaque mission payée retient les comptes du client et du prestataire
  (`client_account_id`, `provider_account_id`) ; le règlement crédite ces
  comptes, quel que soit le canal.
- Un prestataire peut commander comme client, jamais sur sa propre mission :
  le backend refuse le devis et le paiement (`provider_is_client`).
- `phone_e164` et `phone_verified_at` ne sont remplis qu'après une preuve de
  possession du numéro. Les numéros historiques restent dans les profils
  Telegram : leur provenance (contact partagé ou texte libre) n'est pas
  enregistrée et ils ne peuvent donc pas servir à relier des comptes.
- La migration actuelle ajoute les attributs du compte ci-dessus et les
  initialise depuis les profils. Les numéros existants ne sont pas importés
  comme vérifiés ; si un compte a deux profils, la langue client devient la
  langue commune initiale. Les changements de langue suivants sont propagés
  au compte depuis les parcours Telegram.
- Le passage des missions, devis, avis, demandes de service et des API à des
  références `account_id` reste à réaliser avant l'ouverture de WhatsApp ;
  cette migration doit conserver les identifiants Telegram comme identités
  de canal et garder les montants du registre inchangés.

## Registre (ledger) en partie double

Deux tables, écrites uniquement par `backend/app/ledger.py` :

- `money_operations` : une ligne par opération (paiement, libération,
  remboursement, partage, solde d'ouverture). Champs : type, mission, phase,
  auteur (telegram_id), référence de paiement, détails, date.
  **Contrainte d'unicité (mission, phase)** avec deux phases :
  `funding` (au plus un paiement par mission) et `settlement` (au plus un
  règlement par mission : libération, remboursement ou partage). Un double
  clic, un rejeu ou deux requêtes simultanées ne peuvent donc jamais payer
  deux fois : la base le refuse.
- `ledger_entries` : les mouvements d'une opération. Compte = (type,
  identifiant, devise), montant signé en `Numeric(14, 2)` (jamais de float).
  **La somme des mouvements d'une opération vaut toujours 0.**

Comptes :

| Compte | Identifiant | Rôle |
| --- | --- | --- |
| `external` | — | argent venu de l'extérieur (Mobile Money) |
| `wallet` | id du compte Nexis | wallet unique de la personne |
| `escrow` | mission_id | argent bloqué d'une mission |
| `platform` | — | commissions de Nexis Hub |

Un solde = somme des mouvements du compte. Les colonnes
`wallet_balance_usd/cdf` disparaissent des tables backend ; l'API continue de
renvoyer ces deux champs, calculés depuis le registre.

## Opérations et règles

Montants : commission 10 % (15 % si urgent) du devis, arrondi au centime
(arrondi commercial). Le client paie le montant du devis ; le prestataire
reçoit le devis moins la commission.

| Opération | Mouvements |
| --- | --- |
| Paiement Mobile Money | external −total, escrow +total |
| Paiement wallet | wallet client −total, escrow +total (refusé si solde insuffisant) |
| Libération (client confirme, auto 24 h, admin « payer le prestataire ») | escrow −total, wallet prestataire +net, platform +commission |
| Remboursement total (admin) | escrow −total, wallet client +total (frais compris) |
| Partage à p % (admin) | escrow −total, wallet prestataire +net×p, wallet client +net×(1−p), platform +commission |

États d'une mission payée (`status` / `payment_status`) :

- paiement : `confirmed` / `paid_escrow`
- démarrage : `in_progress` (prestataire de la mission uniquement)
- fin : `awaiting_confirmation` (prestataire uniquement)
- confirmation client : `completed` / `released`
- litige : `disputed`, fonds gelés ; ouvrable par le client de la mission
  depuis `confirmed`, `in_progress` ou `awaiting_confirmation`, jamais après
  un règlement
- résolution admin : `cancelled` / `refunded`, `completed` / `released`, ou
  `completed` / `split`
- libération auto 24 h : seulement depuis `awaiting_confirmation`, donc
  jamais une mission en litige

Atomicité : chaque opération est une seule transaction SQL (mission
verrouillée `FOR UPDATE`, wallet client verrouillé pour un paiement wallet,
écriture de l'opération, des mouvements et du nouvel état, puis commit). En
cas d'erreur, rien n'est écrit.

Idempotence : rejouer la même demande (même mission, même phase, mêmes
paramètres) renvoie le résultat déjà enregistré sans rien réécrire ; une
demande différente sur une phase déjà prise est refusée (409).

## API backend

Remplacent les anciens endpoints de recopie (`/api/bot/payments`,
`/api/bot/missions/status`, `/quotes/{id}/pay`, `/pay-wallet`,
`/missions/{id}/release`), supprimés :

- `POST /api/bot/missions/{id}/fund`
- `POST /api/bot/missions/{id}/start`
- `POST /api/bot/missions/{id}/finish`
- `POST /api/bot/missions/{id}/confirm`
- `POST /api/bot/missions/{id}/dispute`
- `POST /api/bot/missions/{id}/dispute/resolve` (`refund`, `release`, `split` + pourcentage, admin)
- `GET /api/bot/missions/{id}`
- `GET /api/bot/wallets/{telegram_id}` (résout l'identité Telegram vers le compte Nexis)

Refus métier : HTTP 409 (ou 404 / 403) avec un code stable (`already_paid`,
`insufficient_balance`, `not_paid`, `invalid_state`, `mission_disputed`,
`already_settled`, `not_mission_client`, `not_mission_provider`,
`provider_is_client`, `invalid_percentage`…) et l'état courant de la mission, que le bot recopie.

## Bot

- Chaque bouton d'argent appelle le backend ; en cas de succès, le bot
  recopie l'état renvoyé dans `db.py` (statut, payment_status, montants,
  prestataire) pour les écrans et les listes admin ; en cas de refus, il
  recopie aussi l'état et affiche le motif traduit ; backend injoignable :
  message « réessaie dans un instant », rien n'est écrit.
- Les soldes affichés (wallet client, wallet prestataire, écran de paiement)
  viennent uniquement du backend ; injoignable = « solde indisponible ».
- Les actions admin sur l'argent exigent `ADMIN_TELEGRAM_ID` configuré (avant,
  sans cette variable, tout le monde était admin).
- Supprimés : soldes et transactions dans `db.py`, fonctions de paiement,
  libération et litige de `db.py`, file `backend_outbox` et son rejeu,
  `backfill_wallets_to_backend.py`, comparaison des wallets dans
  `audit_backend_parity.py`.

## Migration des données

Migration Alembic : création des comptes Nexis (un par telegram_id connu,
avec son identité `telegram`), des deux tables du registre et des colonnes
de litige et de comptes des missions ; le solde client et le solde
prestataire d'une même personne sont additionnés dans son wallet unique, en
une opération « solde d'ouverture » (external → wallet) ; chaque
mission encore en escrow reçoit son opération de paiement ; puis les colonnes
de solde sont supprimées. `bot_transactions` est conservée en lecture seule
(historique), plus jamais écrite. Côté SQLite, colonnes de solde et table
`backend_outbox` supprimées au démarrage du bot.

Migration d'identité multicanal (`e6f7a8b9c0d1`) : ajoute les rôles,
la langue et les champs de numéro vérifié au compte. Les rôles et la langue
sont repris des profils Telegram ; aucun numéro historique n'est déclaré
vérifié faute de preuve de provenance. Une contrainte unique ne s'applique
qu'aux numéros dont la vérification est enregistrée.

## Hors périmètre, prévu pour la suite

- Paiement Mobile Money réel (phase 6) : l'agrégateur confirmera le paiement
  et appellera la même opération `fund` ; le simulateur actuel garde sa
  référence `SIM-…`.
- Retraits vers Mobile Money : nouvelle opération provider → external, qui
  ne pourra jamais toucher un compte escrow.
- Traitement automatique des litiges dont le délai de 48 h est dépassé.

## Tests

- Règles du registre : chaque opération, sommes nulles, soldes, arrondis,
  partage aux bornes (0 %, 100 %, décimales), remboursement total, wallet
  unique client et prestataire, refus d'un prestataire sur sa propre mission,
  wallet retrouvé par un autre canal rattaché au même compte.
- Idempotence et concurrence : double paiement, double règlement, paiement
  wallet pendant un autre débit, rejeu identique.
- Sécurité : mauvais client, mauvais prestataire, litige après règlement,
  libération auto d'une mission en litige, admin non configuré.
- Identité de compte : rôles cumulés quand une personne a les deux profils,
  langue client initiale puis synchronisation de langue, numéros historiques
  jamais marqués vérifiés, unicité des seuls numéros vérifiés.
- Bot : chaque bouton en succès, en refus et backend injoignable.
- Migration : soldes d'ouverture et escrows en cours retrouvés à l'identique.
