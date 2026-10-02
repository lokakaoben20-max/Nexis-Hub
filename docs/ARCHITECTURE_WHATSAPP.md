# Architecture du canal WhatsApp client — Nexis Hub

2 octobre 2026. Validé par Ben (toutes les questions ouvertes tranchées le
même jour, voir la dernière section). Version de travail éditable :
https://claude.ai/code/artifact/289f536c-f696-490f-a85a-b41a86f6a2c7

## Objet et décisions déjà prises

Nexis Hub ouvre un canal WhatsApp réservé aux clients, parce que Telegram est peu utilisé à Kinshasa. Ce document décrit l'architecture cible de ce canal. Aucune ligne de code WhatsApp n'est écrite avant que les étapes qui le précèdent (chantier argent, compte Nexis) soient terminées.

Décisions prises par Ben le 2 octobre 2026 :

1. **Clients** : ils choisissent WhatsApp ou Telegram.
2. **Prestataires** : ils passent obligatoirement par le bot Telegram, la Mini App ou, plus tard, l'application Nexis. Aucun parcours prestataire n'existe sur WhatsApp.
3. **Un seul compte client** : un même client peut relier Telegram et WhatsApp à un seul compte et un seul wallet. La liaison est vérifiée par le numéro de téléphone.
4. **Refus explicite** : une personne qui demande à s'inscrire comme prestataire sur WhatsApp reçoit un refus clair et un lien vers Telegram ou la Mini App.

## État actuel vérifié dans le dépôt

Aucun code WhatsApp n'existe, et le backend est entièrement construit autour de l'identifiant Telegram. Vérifié sur `feature/v5-migration`, commit `d3f3b1b`.

| Constat | Preuve |
| --- | --- |
| Le plan prévoit un canal WhatsApp en 4 lignes, conditionné à un backend indépendant du canal | `V5_MIGRATION_PLAN.md:503-509` (avant cette mise à jour) |
| Le client est identifié par son `telegram_id`, clé primaire de la table, et son wallet y est accroché | `backend/app/models.py:11-17` |
| Le prestataire aussi, avec son propre wallet | `backend/app/models.py:24-43` |
| Missions, devis, avis et demandes de service référencent client et prestataire par `telegram_id` | `backend/app/models.py:55-127` |
| Toutes les routes du backend prennent un `telegram_id` dans l'URL | `backend/app/main.py:276-745` |
| Les notifications du backend ne partent que par l'API Telegram | `backend/app/notify.py:14`, appelé depuis `backend/app/tasks.py:53-149` |
| La Mini App authentifie par la signature Telegram (`initData`) | `mini_app/app.py:119` |
| Le paiement mobile money est simulé | `telegram_bot/payment.py:142` (`operator="mobile_money_simulation"`) |
| Le mot « WhatsApp » n'apparaît que pour demander le numéro de téléphone à l'inscription Telegram | `translations/fr.json:155`, `telegram_bot/keyboards.py:184` |

En plus, `db.py` (SQLite) porte encore une partie de la vérité métier, et le chantier « backend seule source de vérité de l'argent » est en cours (branche `feature/argent-backend`). Le canal WhatsApp ne peut pas s'appuyer sur `db.py` : il ne parle qu'au backend.

## Principes non négociables

Le canal WhatsApp est un affichage et une prise de commande, jamais un endroit où l'argent se décide.

1. **Le backend est la seule source de vérité.** Identité, missions, devis, paiements, wallets, libérations, litiges et remboursements sont décidés par le backend, en une transaction. Le service WhatsApp n'a pas de base métier à lui.
2. **Le service WhatsApp n'importe jamais `db.py`.** Il ne parle au backend que par son API authentifiée.
3. **Backend injoignable, aucune action d'argent.** Le client reçoit un message d'indisponibilité et réessaie. Aucune file locale ne rejoue une action d'argent à sa place.
4. **Chaque action est idempotente.** Un message WhatsApp peut arriver deux fois (Meta réessaie ses webhooks). Chaque appel au backend porte une clé d'idempotence dérivée de l'identifiant du message WhatsApp.
5. **Les règles métier sont écrites une seule fois.** Commissions, statuts, délais et droits sont dans le backend. Telegram et WhatsApp appellent les mêmes endpoints et obtiennent les mêmes résultats au centime.
6. **Tout webhook entrant est authentifié.** Signature `X-Hub-Signature-256` vérifiée en temps constant, sinon rejet, comme le webhook Telegram aujourd'hui (`telegram_bot/webhook_server.py`).
7. **Les textes passent par les fichiers de traduction** (fr, ln, en), jamais écrits en dur.

## Architecture cible

Un compte Nexis unique porte l'argent, et chaque canal n'est qu'une porte d'entrée rattachée à ce compte.

```mermaid
flowchart LR
    CW[Client WhatsApp] --> META[Meta Cloud API] --> SW["Service WhatsApp<br/>whatsapp_bot/, clients seuls"]
    CT[Client Telegram] --> TG[API Telegram]
    PR["Prestataire<br/>Telegram ou Mini App"] --> TG
    TG --> BT["Bot Telegram<br/>et Mini App"]
    SW --> BE["Backend V5<br/>comptes et identités<br/>grand livre et wallets<br/>file de notifications<br/>actions prestataire refusées via WhatsApp<br/><b>seule source de vérité</b>"]
    BT --> BE
```

Le service WhatsApp et le bot Telegram ne décident rien : ils transmettent au backend, qui tient les comptes, l'argent et les règles. Les notifications repartent du backend par le même chemin, sur le canal de chaque personne.

### Identité : compte Nexis et identités de canal

| Table | Rôle | Champs clés | Contraintes |
| --- | --- | --- | --- |
| `accounts` | La personne. Clients et prestataires. | `account_id`, `roles` (client, provider, ou les deux), `phone_e164`, `language`, `created_at` | `phone_e164` unique pour les comptes vérifiés |
| `channel_identities` | Une porte d'entrée vers un compte | `account_id`, `channel` (telegram, whatsapp, miniapp, app), `external_id` (id Telegram ou `wa_id`), `verified_at` | Unique sur (`channel`, `external_id`) ; un seul canal de chaque type par compte |
| Wallet et grand livre | Définis par le chantier argent | Rattachés à `account_id`, jamais à un canal | Voir le chantier argent |

Missions, devis, transactions, avis et litiges référencent `account_id` au lieu de `telegram_id`. Le prestataire utilise le même modèle. C'est ce qui permettra plus tard l'application Nexis sans nouvelle migration.

**Règle de rôle dans le backend :** un compte `provider` ne peut avoir que des identités `telegram`, `miniapp` ou `app` pour ses actions de prestataire. Le backend refuse toute action prestataire venant d'une identité `whatsapp`. La règle n'est pas confiée au service WhatsApp.

**Compte avec deux rôles :** un prestataire peut aussi commander comme client, avec le même compte et le même wallet. Sur Telegram et la Mini App, il passe d'un mode à l'autre. Le backend refuse tout devis d'un prestataire sur une mission dont il est le client.

### Routage des notifications

Le backend écrit chaque notification dans une table `notifications` dans la même transaction que l'événement métier (paiement reçu, mission libérée, litige ouvert). Une tâche Celery envoie ensuite chaque ligne sur le canal préféré du destinataire et enregistre le résultat.

- Une notification n'est jamais perdue : si l'envoi échoue, la ligne reste à renvoyer, avec un nombre d'essais et une erreur enregistrée.
- Une notification n'est jamais envoyée deux fois : chaque ligne a un état (`pending`, `sent`, `failed`) et un identifiant de message du fournisseur.
- L'envoi direct actuel (`backend/app/notify.py:14`) est remplacé par cette table pour les deux canaux.

### Composants

- **Service WhatsApp** (`whatsapp_bot/`, processus séparé) : reçoit les webhooks de Meta, vérifie la signature, déduplique, garde l'état de conversation et appelle le backend.
- **Backend V5** : seule source de vérité. Nouveaux endpoints indexés par `account_id`, authentifiés par clé de service par canal.
- **Expéditeur de notifications** (Celery) : lit `notifications` et envoie par Telegram ou WhatsApp.
- **Bot Telegram et Mini App** : inchangés dans leur rôle, mais appellent les endpoints par `account_id`.

L'état de conversation WhatsApp (étape en cours d'un client) vit dans Redis, déjà en place. Il ne contient aucune donnée d'argent : perdu, le client recommence l'étape.

## Parcours client sur WhatsApp et contraintes de l'API

Le client WhatsApp fait les mêmes choses que le client Telegram, mais avec des boutons et des listes plus pauvres et une règle stricte sur les messages envoyés sans qu'il ait écrit.

### Contraintes de l'API WhatsApp

| Contrainte | Effet sur Nexis |
| --- | --- |
| 3 boutons de réponse maximum, 20 caractères par bouton | Chaque choix oui/non ou à 3 options tient en boutons ; les libellés lingala doivent être courts et relus |
| Listes de 10 lignes maximum | Services et communes de Kinshasa doivent être présentés par groupes (par exemple district, puis commune) |
| Fenêtre de 24 h après le dernier message du client | Dans la fenêtre : message libre gratuit. Hors fenêtre : uniquement un modèle validé par Meta |
| Modèles « utilité » (suivi de transaction) | Gratuits dans la fenêtre de 24 h, facturés par message en dehors |
| Modèles « marketing » | Toujours facturés, consentement requis. Nexis n'en utilise pas dans ce chantier |
| Pas de Mini App | Aucun écran riche ; tout passe par messages, boutons, listes, localisation et photos |

Source : [tarification Meta](https://developers.facebook.com/docs/whatsapp/pricing) (facturation par message depuis le 1er juillet 2025) et [boutons de réponse](https://developers.facebook.com/docs/whatsapp/cloud-api/messages/interactive-reply-buttons-messages).

### Parcours

La saisie se fait en conversation pas à pas (décision de Ben) : listes, texte, localisation. Pas de formulaires WhatsApp Flows.

| Parcours | Sur WhatsApp | Notification hors fenêtre (modèle utilité à faire valider) |
| --- | --- | --- |
| Inscription | Choix de la langue (3 boutons), nom ; le numéro est le `wa_id`, déjà vérifié par WhatsApp | Aucune |
| Créer une mission | Service (liste), commune (liste en deux niveaux), description (texte), localisation (partage de position WhatsApp) | Aucune |
| Recevoir et choisir un devis | Devis affiché avec boutons Accepter / Refuser | « Nouveau devis pour votre mission » |
| Payer | Lien ou demande de paiement mobile money émise par le backend ; confirmation par le backend uniquement | « Paiement reçu » |
| Suivre la mission | Messages d'état (démarrée, terminée) | « Mission démarrée », « Mission terminée, confirmez » |
| Confirmer la fin et noter | Boutons Confirmer / Signaler un problème, puis note | « Paiement libéré » |
| Ouvrir un litige | Motif en liste, puis texte libre | « Litige ouvert », « Litige résolu » |
| Voir missions et solde | Commandes par menu (liste) | Aucune |

Le paiement réel est un prérequis commun : aujourd'hui il est simulé (`telegram_bot/payment.py:142`). Le canal WhatsApp n'ouvre pas à de vrais clients tant que le paiement mobile money réel (Phase 6) n'est pas en place, exactement comme Telegram.

## Liaison Telegram et WhatsApp, refus prestataire

Deux canaux ne sont reliés à un même compte que si la personne prouve qu'elle contrôle les deux. Le numéro seul ne suffit jamais.

### Ce que vaut un numéro

| Source du numéro | Prouvé ? | Pourquoi |
| --- | --- | --- |
| `wa_id` WhatsApp | Oui | WhatsApp a vérifié le numéro par SMS |
| Bouton « Partager mon numéro » Telegram, si le contact envoyé est celui de l'expéditeur | Oui | Telegram a vérifié le numéro du compte |
| Numéro tapé à la main sur Telegram (permis aujourd'hui, `translations/fr.json:155`) | Non | N'importe qui peut taper le numéro d'un autre |

`accounts.phone_e164` n'est unique que pour les numéros prouvés. Un numéro tapé par un compte existant reste enregistré, marqué non vérifié. Pour les nouveaux comptes Telegram, le bouton « Partager mon numéro » devient obligatoire (décision de Ben).

### Règles de liaison

1. **Numéro WhatsApp inconnu** : le backend crée un compte client et une identité `whatsapp` vérifiée.
2. **Numéro WhatsApp déjà porté par un compte client Telegram** : pas de liaison automatique. Le client choisit « Lier mon compte Telegram ». Le backend envoie un code à 6 chiffres sur Telegram ; le client le tape sur WhatsApp. La liaison ajoute l'identité `whatsapp` au compte existant. Le wallet ne bouge pas, il appartient déjà au compte.
3. **Code** : stocké sous forme de hachage, valable 10 minutes, usage unique, 5 essais au plus puis blocage d'une heure. Jamais écrit dans les journaux.
4. **Le numéro Telegram était tapé, donc non prouvé** : le titulaire WhatsApp, lui, est prouvé. La liaison passe quand même par le code Telegram. Sans code, le backend crée un compte WhatsApp séparé et signale le conflit à l'admin, sans toucher à aucun wallet.
5. **Deux comptes portant chacun un solde** : jamais fusionnés automatiquement. Une fusion d'argent est une opération admin explicite, tracée dans le grand livre, hors de ce chantier.
6. **Chaque liaison et déliaison** est inscrite dans un journal d'audit (qui, quand, quel canal, résultat).
7. **Changement de numéro WhatsApp** : nouveau `wa_id`, donc nouvelle identité. Le rattachement au compte existant passe par le code Telegram, ou par l'admin après vérification si le client n'a pas Telegram.

### Refus prestataire

- Le menu WhatsApp ne propose aucune option prestataire.
- Si la personne demande à devenir prestataire, le bot répond par un message fixe (fr, ln, en) avec le lien du bot Telegram et de la Mini App.
- Le backend refuse de lui-même toute création ou action prestataire venant d'une identité `whatsapp`. Le service WhatsApp ne peut donc pas contourner la règle, même par erreur.
- Si le numéro WhatsApp appartient déjà à un compte prestataire, le bot lui indique d'utiliser Telegram ou la Mini App pour ses actions de prestataire. Il peut en revanche y commander comme client.

## Fournisseur de l'API et prérequis Meta

Décision : l'API WhatsApp Cloud de Meta en direct, sans intermédiaire.

| Option | Pour | Contre |
| --- | --- | --- |
| **Cloud API Meta en direct (retenu)** | Pas de marge d'intermédiaire, pas de dépendance de plus, documentation officielle, nouveautés Meta disponibles dès leur sortie | Tout l'onboarding Meta à faire soi-même |
| Twilio | Onboarding guidé, bibliothèque Python, support | Marge par message en plus du prix Meta, un fournisseur de plus entre Nexis et ses clients |
| 360dialog | Abonnement fixe, prix Meta repassés | Abonnement mensuel, un fournisseur de plus |

Le code appelle une API HTTPS et reçoit des webhooks dans tous les cas. Isoler l'envoi et la réception derrière une seule interface dans `whatsapp_bot/` permet de changer de fournisseur sans toucher au reste.

### Prérequis à obtenir par Ben, avant le code de production

- [ ] Compte Meta Business (portefeuille d'entreprise) **vérifié**, avec les documents de l'entreprise Nexis Hub.
- [ ] Un numéro de téléphone dédié, non utilisé dans l'application WhatsApp.
- [ ] Nom d'affichage « Nexis Hub » approuvé par Meta.
- [ ] Modèles utilité approuvés, en français, lingala et anglais (liste dans les parcours).
- [ ] **Hébergement public HTTPS stable** pour le webhook. Le PC avec ngrok ne convient pas : Meta exige une URL fixe, et un webhook éteint fait perdre des messages clients. C'est déjà un bloquant de lancement identifié pour Telegram.
- [ ] Moyen de paiement enregistré chez Meta pour les modèles facturés.

Le développement et les tests peuvent commencer avec le numéro de test fourni par Meta, sans attendre la vérification.

## Découpage en étapes

Le canal WhatsApp vient après le chantier argent, et le compte Nexis doit être conçu avec lui pour ne pas migrer l'argent deux fois. Chaque étape est une session à part, relue (`security-reviewer`, `backend-parity-auditor`), testée, puis poussée sur une branche dédiée. Rien n'arrive sur `feature/v5-migration` dans un état intermédiaire.

| Étape | Contenu | Dépend de | Livré quand |
| --- | --- | --- | --- |
| 0. Accord avec le chantier argent | Le grand livre et les wallets sont rattachés à `account_id` dès leur conception | Chantier argent (`feature/argent-backend`) | Le document du chantier argent l'indique, validé par Ben |
| 1. Compte Nexis | Tables `accounts` et `channel_identities`, migration Alembic, reprise de chaque `telegram_id` existant, missions et transactions basculées sur `account_id`, bot Telegram et Mini App adaptés | Étape 0 | Audit : mêmes missions, mêmes montants au centime avant et après, sur les vraies bases |
| 2. Notifications fiables | Table `notifications` écrite dans la transaction métier, expéditeur Celery, Telegram migré dessus | Étape 1 | Plus aucun envoi direct ; tests d'échec réseau et de double envoi |
| 3. Rôles dans le backend | Refus des actions prestataire depuis WhatsApp, refus du devis sur sa propre mission, clé de service par canal | Étape 1 | Tests de refus pour chaque endpoint prestataire |
| 4. Service WhatsApp, socle | `whatsapp_bot/` : webhook, signature, déduplication, état Redis, inscription, menu, refus prestataire | Étapes 2 et 3 | Fonctionne sur le numéro de test Meta |
| 5. Parcours client | Mission, devis, paiement, suivi, notation, litige | Étape 4 et chantier argent terminé | Mêmes résultats que Telegram sur les mêmes scénarios |
| 6. Liaison des comptes | Code à usage unique, règles de conflit, journal d'audit | Étape 5 | Tests d'attaque (code faux, expiré, réutilisé, numéro tapé) |
| 7. Modèles et envoi WhatsApp | Modèles utilité validés par Meta, choix message libre ou modèle selon la fenêtre de 24 h | Étapes 2 et 5, modèles approuvés | Chaque notification arrive, dans ou hors fenêtre |
| 8. Mise en service | Hébergement HTTPS, compte Meta vérifié, paiement réel (Phase 6), essai réel avec quelques clients | Tout ce qui précède | Ben valide l'ouverture |

Les étapes 1 à 3 améliorent aussi Telegram (notifications fiables, rôles contrôlés par le backend). Elles ont de la valeur même avant l'arrivée de WhatsApp.

## Risques et parades

Le risque principal est la migration de l'identité (étape 1), parce qu'elle touche toutes les tables d'argent.

| Risque | Gravité | Parade |
| --- | --- | --- |
| Migration `telegram_id` vers `account_id` qui perd ou déplace un solde | Critique | Migration en une transaction, comptes vérifiés avant et après (nombre de lignes, somme des soldes au centime), répétée sur une copie des vraies bases avant la prod, sauvegarde avant |
| Deux wallets pour une même personne | Élevée | Numéro prouvé unique, liaison par code, aucune fusion automatique |
| Prise de contrôle d'un compte par liaison frauduleuse | Élevée | Code envoyé sur l'autre canal, haché, 10 minutes, 5 essais, journal d'audit |
| Prestataire qui se paie lui-même via sa propre mission | Élevée | Le backend refuse tout devis d'un prestataire sur une mission dont il est le client |
| Message WhatsApp reçu deux fois, donc action répétée | Élevée | Déduplication par identifiant de message et clé d'idempotence transmise au backend |
| Webhook falsifié | Élevée | Signature Meta vérifiée en temps constant, rejet sinon |
| Notification de paiement ou de litige jamais reçue | Moyenne | Table `notifications` avec nouvel essai ; modèle utilité hors fenêtre de 24 h |
| Modèle refusé par Meta | Moyenne | Textes purement transactionnels, soumis tôt, dans les trois langues |
| Compte Meta Business non vérifié ou numéro bloqué | Moyenne | Démarches lancées dès la validation de ce document ; développement sur le numéro de test |
| Coût des modèles hors fenêtre | Faible | Seulement des modèles utilité, uniquement pour les événements d'argent et de mission ; coût suivi par mois |
| Textes lingala trop longs pour les boutons (20 caractères) | Faible | Relecture native des libellés courts avant l'étape 5 |

## Plan de tests

Chaque étape a ses tests dans la suite existante (`pytest -q`), et l'étape 1 a en plus un audit sur les vraies bases.

| Domaine | Tests |
| --- | --- |
| Migration d'identité | Chaque `telegram_id` donne un compte et une identité ; aucune mission ni transaction orpheline ; somme des soldes identique au centime ; migration rejouée deux fois sans effet ; retour arrière testé |
| Parité Telegram / WhatsApp | Mêmes scénarios (mission, devis, paiement, libération, litige, remboursement) passés par les deux canaux : mêmes statuts et mêmes montants |
| Idempotence | Le même webhook reçu 2 fois et 10 fois en parallèle ne produit qu'une action |
| Backend coupé | Aucune action d'argent, message d'indisponibilité au client, rien rejoué plus tard à sa place |
| Sécurité webhook | Signature absente, fausse ou d'un autre corps : rejet |
| Rôles | Toute action prestataire depuis une identité `whatsapp` : refusée par le backend ; devis sur sa propre mission : refusé |
| Liaison | Bon code ; code faux, expiré, réutilisé ; 6e essai bloqué ; numéro tapé non prouvé ; deux comptes avec solde non fusionnés |
| Notifications | Envoi réussi, échec puis nouvel essai, jamais deux envois ; message libre dans la fenêtre, modèle hors fenêtre |
| Textes | Parité des clés fr / ln / en (`i18n-reviewer`) ; libellés de boutons de 20 caractères au plus |
| Bout en bout | Sur le numéro de test Meta, puis un essai réel avec quelques clients avant l'ouverture |

## Décisions de Ben sur les questions ouvertes

Toutes les questions ont été tranchées par Ben le 2 octobre 2026.

| Question | Décision |
| --- | --- |
| Prestataire qui commande aussi | Oui. Un compte, deux rôles, un wallet. Sur Telegram et la Mini App, il passe du mode prestataire au mode client. Sur WhatsApp, mode client seulement. Jamais de devis sur sa propre mission |
| Compte Nexis dans le chantier argent | Oui. `account_id` est intégré au chantier argent avant la fin de son code |
| Fournisseur | Cloud API Meta en direct |
| Numéro sur Telegram | Le bouton « Partager mon numéro » est obligatoire pour les nouveaux comptes ; le numéro tapé n'est plus accepté |
| Saisie de la mission sur WhatsApp | Conversation pas à pas : listes, texte, localisation. Pas de formulaires WhatsApp Flows |
