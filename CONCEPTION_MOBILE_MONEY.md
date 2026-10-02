# Conception : paiements et retraits Mobile Money réels

Rédigée le 2026-10-03, à la demande de Ben, pendant que les agrégateurs
(FlexPaie, MaxiCash, SerdiPay, KibaWallet) répondent. Indépendante de
l'agrégateur choisi : seul un module d'adaptation lui sera propre.
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

Un retrait ne puise que dans le wallet : l'argent d'une mission en escrow ou
en litige n'y est jamais. Le compte `payout_pending` et un nouveau compte
`fees` (frais d'agrégateur) s'ajoutent aux comptes du registre.

## Frais d'agrégateur

Les frais facturés par l'agrégateur sont enregistrés comme une opération à
part (platform → fees pour ce que la plateforme paie, ou wallet → fees pour
ce que le prestataire paie au retrait), au montant indiqué par l'agrégateur.
Le registre reste exact au centime face aux relevés.

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

## Décisions à prendre par Ben

1. **Agrégateur** : après comparaison des réponses (frais, versements
   sortants, délais, qualité de l'API).
2. **Frais d'encaissement** : absorbés par la plateforme sur sa commission
   (le client paie le prix du devis, comme aujourd'hui), ou ajoutés au prix
   payé par le client.
3. **Frais de retrait** : payés par le prestataire (déduits du retrait) ou par
   la plateforme ; montant minimum de retrait.
4. **Validation des retraits** : automatique, ou validée par l'admin au-dessus
   d'un montant (recommandé au lancement).
5. **Wallet client** : un client peut-il retirer vers son Mobile Money l'argent
   d'un remboursement, ou ce solde sert-il seulement à payer d'autres
   missions ?

## Livraison

Un seul chantier, sur une branche dédiée, livré complet une fois
l'agrégateur choisi et son bac à sable ouvert : tables et migration
(intentions, retraits, comptes `payout_pending` et `fees`), module
d'adaptation, webhook et interrogation de secours, parcours bot et admin,
rapprochement, puis essais dans le bac à sable. Tests obligatoires :
signature falsifiée, webhook rejoué, montant différent, confirmation en
retard, double confirmation, agrégateur injoignable, retrait concurrent,
échec de versement et retour de l'argent.
