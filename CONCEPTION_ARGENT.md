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
acceptation) est aussi enregistré par le backend seul (CONCEPTION_MISSIONS.md) :
la demande de paiement ne porte que les numéros de la mission et du devis
accepté, et le backend y relit montant, devise, prestataire et urgence.

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
- Les missions, devis, avis et demandes de service ont désormais des références
  vers `accounts`. Les profils Telegram restent les adaptateurs de canal ; les
  créations écrivent aussi l'identifiant canonique et l'acceptation du devis
  propage le compte prestataire à la mission. La migration de schéma
  `a1b2c3d4e5f6` rattache les lignes historiques aux identités Telegram déjà
  connues, sans modifier le registre ni ses montants.
- Les règles d'argent ne comparent que des comptes (`ledger`, `mobile_money`) :
  démarrer, terminer, confirmer, ouvrir un litige, payer et retirer sont
  autorisés par `client_account_id` / `provider_account_id`, jamais par un
  identifiant Telegram. Une mission payée sans compte rattaché est refusée
  (`mission_account_missing`). L'API traduit l'identité Telegram en compte à un
  seul endroit (`_telegram_account` dans `backend/app/main.py`). Les intentions
  de paiement nomment le client et le prestataire par leur compte, et chaque
  opération enregistre le compte qui l'a déclenchée (`actor_account_id`).
  Migration `b2c3d4e5f6a7`, qui s'arrête si une intention n'a pas de compte.
- Le passage complet des appels d'API à `account_id` et l'adaptation des
  parcours Mini App/Telegram restent à réaliser avant l'ouverture de WhatsApp.

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
| Libération (client confirme, auto 48 h, admin « payer le prestataire ») | escrow −total, wallet prestataire +net, platform +commission |
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
- libération auto 48 h : seulement depuis `awaiting_confirmation`, donc
  jamais une mission en litige. L'échéance (`release_after`) est fixée quand
  le prestataire déclare la mission terminée et ne change plus ensuite ; les
  missions terminées avant le passage à 48 h gardent leur échéance de 24 h
- litige sans décision après le délai de réponse de 48 h : alerte admin (tâche
  `litiges-en-retard`), puis une relance par jour ; aucun argent ne bouge
  sans décision humaine

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
`provider_is_client`, `quote_not_accepted`, `invalid_percentage`…) et l'état courant de la mission.

## Bot

- Chaque bouton d'argent appelle le backend et affiche ce qu'il répond ; en
  cas de refus, le motif traduit ; backend injoignable : message « réessaie
  dans un instant », rien n'est écrit. Le bot ne garde aucune copie des
  missions : écrans et listes admin les relisent dans le backend.
- Les soldes affichés (wallet client, wallet prestataire, écran de paiement)
  viennent uniquement du backend ; injoignable = « solde indisponible ».
- Les actions admin sur l'argent exigent `ADMIN_TELEGRAM_ID` configuré (avant,
  sans cette variable, tout le monde était admin).
- Supprimés : soldes, transactions, missions, devis et avis dans `db.py`, fonctions de paiement,
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
- Décision de litige en deux temps avec 3 jours pour contester, partage avec
  commission au prorata, accord amiable confirmé par les deux (prochaines
  étapes). Un litige en retard n'est jamais réglé automatiquement.

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
