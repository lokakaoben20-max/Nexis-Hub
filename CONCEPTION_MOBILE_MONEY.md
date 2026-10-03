# Conception : paiements et retraits Mobile Money réels

Rédigée le 2026-10-03 à la demande de Ben, complétée le même jour avec ses
décisions (section « Décisions de Ben »). Agrégateur retenu : FlexPaie
(FlexPay). Le cœur reste indépendant de l'agrégateur : seul un module
d'adaptation lui est propre.
S'appuie sur le registre d'argent (`CONCEPTION_ARGENT.md`), qui reste la
seule source de vérité.

## Principe

L'argent n'existe dans Nexis Hub que lorsque **l'agrégateur l'a confirmé**,
directement au backend. Ni le bot, ni le client, ni un écran ne peuvent
déclarer un paiement réussi. Un paiement ou un retrait se déroule en deux
temps : une demande (en attente), puis une confirmation de l'agrégateur, qui
seule déplace l'argent dans le registre.

Aujourd'hui, `fund_mission(method="mobile_money")` enregistre un paiement
simulé dès le clic. En réel, cette voie n'est plus ouverte au bot : seul le
traitement d'une confirmation de l'agrégateur peut l'appeler.

## Encaissement (le client paie une mission)

1. Le client choisit Mobile Money. Le bot propose son numéro vérifié (ou en
   demande un) et l'opérateur, déduit du préfixe et confirmé par le client.
2. Le backend crée une **intention de paiement** (`payment_intents`) : mission,
   compte payeur, montant et devise recalculés depuis le devis accepté,
   numéro, opérateur, statut `created`. **Une seule intention ouverte par
   mission** : un second clic renvoie la même, il n'en crée pas une autre.
3. Le backend demande à l'agrégateur d'envoyer la demande de paiement sur le
   téléphone du client (USSD ou notification de l'opérateur). Statut
   `pending`, avec la référence de l'agrégateur.
4. Le client valide avec son code secret sur son téléphone. Le bot affiche
   « en attente de confirmation de votre opérateur ».
5. L'agrégateur prévient le backend (webhook). Le backend vérifie la
   signature, refuse un message trop ancien ou déjà traité, puis
   **reconsulte le statut auprès de l'agrégateur** avant de croire le message.
6. Si le paiement est réussi et que montant et devise sont exactement ceux de
   l'intention : dans **une seule transaction**, l'intention passe à
   `succeeded` et le registre enregistre le paiement de la mission
   (external → escrow), avec la référence de l'agrégateur. Puis client et
   prestataire sont prévenus.
7. Échec, refus ou annulation par le client : intention `failed`, rien ne
   bouge dans le registre, le client peut réessayer (nouvelle intention).

Filets de sécurité :

- **Webhook perdu** : une tâche périodique interroge l'agrégateur pour chaque
  intention `pending` depuis plus de quelques minutes.
- **Expiration** : sans confirmation après le délai de l'opérateur, l'intention
  passe à `expired` ; la mission reste payable.
- **Montant ou devise différents** : aucun paiement de mission ; l'intention
  passe à `mismatch` et l'admin est alerté.
- **Paiement confirmé en retard, ou deux fois** (intention expirée puis
  payée, ou deux intentions réussies) : la mission n'est jamais payée deux
  fois (contrainte du registre). L'argent réellement reçu en trop est crédité
  sur le wallet du client (opération tracée external → wallet) et l'admin est
  alerté. Aucun argent reçu n'est perdu ni ignoré.
- **Doublon de confirmation** : la référence de l'agrégateur est unique ; un
  webhook rejoué ne fait rien.

## Retrait (le prestataire récupère son argent)

1. Le prestataire (vérifié, non suspendu) demande un retrait depuis son
   wallet vers son numéro Mobile Money vérifié.
2. Dans une seule transaction, le backend vérifie le solde et bloque le
   montant : wallet → compte `payout_pending` du retrait. Le wallet affiché
   baisse immédiatement ; deux demandes simultanées ne peuvent pas dépasser le
   solde (verrou du compte, comme pour le paiement par wallet).
3. Le backend demande le versement à l'agrégateur (statut `processing`).
4. Confirmation de l'agrégateur (webhook vérifié et statut reconsulté) :
   `payout_pending` → external, retrait `succeeded`.
5. Échec définitif : `payout_pending` → wallet, retrait `failed`, le
   prestataire est prévenu. L'argent revient, toujours.

**Validation (décision de Ben)** : au lancement, chaque retrait attend la
validation de l'admin dans le bot avant d'être envoyé à l'agrégateur (statut
`awaiting_approval`, montant déjà bloqué). Plus tard, sous un plafond réglé
dans le backend, les retraits partent automatiquement. Cette règle vit dans
notre backend : l'agrégateur ne fait qu'exécuter un versement déjà autorisé.
Un refus de l'admin rend le montant au wallet.

**Argent d'un remboursement** : l'argent qu'un client a reçu par
remboursement (litige) reste utilisable pour payer d'autres missions, mais
n'est retirable vers le Mobile Money qu'après vérification de l'admin. Le
registre trace l'origine de chaque crédit, donc la part « remboursement »
d'un wallet est connue sans calcul approximatif.

Un retrait ne puise que dans le wallet : l'argent d'une mission en escrow ou
en litige n'y est jamais. Le compte `payout_pending` et un nouveau compte
`fees` (frais d'agrégateur) s'ajoutent aux comptes du registre.

## Frais d'agrégateur

Les frais facturés par l'agrégateur sont enregistrés comme une opération à
part, au montant indiqué par l'agrégateur, pour que le registre reste exact
au centime face aux relevés :

- **Encaissement** : à la charge de Nexis Hub (platform → fees), prélevés
  sur sa commission ; le client paie le prix du devis. Qui paie est un
  **réglage du backend** (payeur et taux attendu), pas une valeur codée en
  dur : Ben peut le changer plus tard sans toucher au registre. Le montant
  enregistré reste celui annoncé par l'agrégateur ; un écart avec le taux
  attendu est signalé au rapprochement.
- **Retrait** : à la charge du prestataire (wallet → fees), au prix coûtant
  de l'agrégateur, déduit du montant versé ; montant minimum de retrait. Les
  deux valeurs sont des réglages du backend, fixés avec les tarifs PayOut
  de FlexPaie.

## Rapprochement

Chaque jour, une tâche compare le relevé de l'agrégateur avec les intentions
et retraits du registre : montants, devises, statuts, références. Tout écart
produit un rapport pour l'admin. **Aucune correction d'argent automatique** :
une correction est une opération admin explicite, tracée dans le registre.

## Sécurité

- Clés de l'agrégateur uniquement dans les variables d'environnement du
  backend, jamais dans le bot ni dans le dépôt.
- Endpoint webhook public mais isolé du reste de l'API : signature vérifiée
  (comparaison à temps constant), horodatage récent, identifiant d'événement
  à usage unique, restriction d'IP si l'agrégateur la propose.
- Le webhook ne fait jamais foi seul : statut toujours reconsulté auprès de
  l'agrégateur.
- Numéros masqués dans les journaux ; aucune donnée de carte ne transite chez
  nous.
- En production, le paiement simulé est refusé par configuration.

## Module d'adaptation

Une interface, une implémentation par agrégateur :

- demander un encaissement, en lire le statut ;
- vérifier un webhook ;
- demander un versement, en lire le statut ;
- lire le relevé d'une journée.

Les tests utilisent une implémentation de test (dans `tests/` uniquement),
et le bac à sable de l'agrégateur sert aux essais de bout en bout.

## Ce que le bot et l'admin voient

- Client : choix de l'opérateur, écran « en attente de confirmation », puis
  « paiement confirmé » ou « paiement échoué, réessayer ».
- Prestataire : bouton « Retirer », montant, numéro vérifié, suivi du retrait.
- Admin : intentions en anomalie (montant différent, paiement en trop),
  retraits échoués, rapport de rapprochement du jour.

## Décisions de Ben (2026-10-03)

1. **Agrégateur : FlexPaie (FlexPay).**
2. **Frais d'encaissement** : à la charge de Nexis Hub, sur sa commission,
   « on verra ensuite » : réglage du backend, modifiable sans migration.
3. **Frais de retrait** : au prix coûtant, à la charge du prestataire, avec
   un minimum de retrait ; montants fixés avec les tarifs reçus.
4. **Retraits** : validés par l'admin au début, puis automatiques sous un
   plafond.
5. **Remboursement d'un client** : non retirable sans vérification de
   l'admin.

## Ce que FlexPaie a répondu, et ce qui manque

Répondu : 100 USD d'installation, 2,5 % par encaissement ; encaissements
(PayIn) et versements (PayOut) par API, webhooks, consultation du statut,
bac à sable. La documentation n'est fournie qu'après le KYC, qui demande une
société enregistrée en RDC.

À obtenir **par écrit** avant tout branchement réel :

- **signature des webhooks** (comment vérifier qu'une confirmation vient
  bien de FlexPaie) : bloquant, sans elle on ne peut pas croire un webhook ;
- frais des versements (PayOut) et leurs plafonds ;
- remboursement par API (sinon le remboursement reste un crédit wallet,
  comme aujourd'hui) ;
- confirmation que nous gardons nous-mêmes l'argent en séquestre (escrow
  dans notre registre), FlexPaie ne faisant qu'encaisser et verser.

**Rien n'est branché en réel avant que le KYC soit validé et que la
signature des webhooks soit confirmée par écrit.**

## Découpage du code

Un seul chantier, sur une branche dédiée, livré complet. Les étapes 1 à 4
ne dépendent pas de la documentation FlexPaie et peuvent commencer dès
maintenant ; l'étape 5 attend le KYC et la réponse sur la signature.

1. **Registre et tables** : intentions de paiement, retraits, comptes
   `payout_pending` et `fees`, origine des crédits (remboursement), réglages
   (payeur et taux des frais, frais et minimum de retrait, plafond
   d'automatisation). Migration Alembic avec retour arrière.
2. **Encaissement indépendant de l'agrégateur** : création d'intention (une
   seule ouverte par mission), traitement d'une confirmation, interrogation
   de secours, expiration, montant différent, paiement en retard ou en
   double. La voie « paiement simulé au clic » disparaît en production.
3. **Retraits** : demande et blocage, validation ou refus admin, versement,
   échec et retour au wallet, minimum, frais, plafond, argent de
   remboursement.
4. **Bot et admin** : choix de l'opérateur, écran d'attente, bouton
   « Retirer », écrans admin (retraits à valider, anomalies, rapprochement).
   Textes en fr, ln, en.
5. **Module FlexPaie** : appels PayIn et PayOut, vérification de signature,
   lecture du statut et du relevé ; essais de bout en bout dans le bac à
   sable FlexPaie.
6. **Rapprochement quotidien** et revue de sécurité dédiée (déjà prévue
   pour la phase 6), puis mise en ligne.

Tests obligatoires : signature falsifiée, webhook rejoué, montant ou devise
différents, confirmation en retard, double confirmation, agrégateur
injoignable, deux retraits simultanés, retrait refusé par l'admin, échec de
versement et retour de l'argent, minimum et plafond, argent de remboursement
non retirable sans validation, aucune écriture si une étape échoue.

## Risques

| Risque | Gravité | Parade |
| --- | --- | --- |
| Faux webhook qui « paie » une mission | Critique | Signature vérifiée, statut toujours reconsulté chez FlexPaie ; pas de branchement réel sans signature confirmée |
| Argent reçu mais mission non payée (webhook perdu) | Élevée | Interrogation de secours, rapprochement quotidien |
| Double versement d'un retrait | Critique | Montant bloqué avant l'envoi, référence unique, retour au wallet seulement sur échec définitif confirmé |
| Frais réels différents des frais attendus | Moyenne | Montant de l'agrégateur enregistré tel quel, écart signalé au rapprochement |
| Documentation FlexPaie différente de nos hypothèses | Moyenne | Tout ce qui est propre à FlexPaie est isolé dans son module (étape 5) |
