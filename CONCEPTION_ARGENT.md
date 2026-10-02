# Conception : l'argent de Nexis Hub, backend V5 seule source de vérité

Branche : `feature/argent-backend`. Décidé par Ben le 2026-10-02. Remplace
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
| `client` | telegram_id | wallet client |
| `provider` | telegram_id | wallet prestataire |
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
| Paiement wallet | client −total, escrow +total (refusé si solde insuffisant) |
| Libération (client confirme, auto 24 h, admin « payer le prestataire ») | escrow −total, provider +net, platform +commission |
| Remboursement total (admin) | escrow −total, client +total (frais compris) |
| Partage à p % (admin) | escrow −total, provider +net×p, client +net×(1−p), platform +commission |

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
- `GET /api/bot/wallets/{telegram_id}`

Refus métier : HTTP 409 (ou 404 / 403) avec un code stable (`already_paid`,
`insufficient_balance`, `not_paid`, `invalid_state`, `mission_disputed`,
`already_settled`, `not_mission_client`, `not_mission_provider`,
`invalid_percentage`…) et l'état courant de la mission, que le bot recopie.

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

Migration Alembic : création des deux tables et des colonnes de litige
(`dispute_opened_at`, `dispute_deadline`) ; chaque solde wallet existant
devient une opération « solde d'ouverture » (external → wallet) ; chaque
mission encore en escrow reçoit son opération de paiement ; puis les colonnes
de solde sont supprimées. `bot_transactions` est conservée en lecture seule
(historique), plus jamais écrite. Côté SQLite, colonnes de solde et table
`backend_outbox` supprimées au démarrage du bot.

## Hors périmètre, prévu pour la suite

- Paiement Mobile Money réel (phase 6) : l'agrégateur confirmera le paiement
  et appellera la même opération `fund` ; le simulateur actuel garde sa
  référence `SIM-…`.
- Retraits vers Mobile Money : nouvelle opération provider → external, qui
  ne pourra jamais toucher un compte escrow.
- Traitement automatique des litiges dont le délai de 48 h est dépassé.

## Tests

- Règles du registre : chaque opération, sommes nulles, soldes, arrondis,
  partage aux bornes (0 %, 100 %, décimales), remboursement total.
- Idempotence et concurrence : double paiement, double règlement, paiement
  wallet pendant un autre débit, rejeu identique.
- Sécurité : mauvais client, mauvais prestataire, litige après règlement,
  libération auto d'une mission en litige, admin non configuré.
- Bot : chaque bouton en succès, en refus et backend injoignable.
- Migration : soldes d'ouverture et escrows en cours retrouvés à l'identique.
