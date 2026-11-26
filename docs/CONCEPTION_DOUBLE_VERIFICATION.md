# Conception : double vérification du compte

**Statut : proposition approuvée dans son principe par Ben (2026-11-26,
11 h 15). Rien n'est codé côté serveur.** Les choix encore ouverts sont listés
en section 11. Deux points sont **à voir avec le juriste** avant tout code :
la récupération d'un prestataire par sa vidéo d'identité, et le délai de
7 jours pour un client.

Ce document complète `backend/app/app_auth.py` (codes de connexion) et
`backend/app/app_sessions.py` (téléphones, sessions, délai de 72 h). Il ne
change aucune règle d'argent : le registre (`ledger.py`) reste la seule
source.

## 1. Le risque visé

Aujourd'hui, une connexion sur un nouveau téléphone demande seulement le
code de connexion (6 chiffres, envoyé par Telegram, plus tard WhatsApp, lié à
la clé du téléphone qui l'a demandé). Ensuite, ce téléphone crée **son propre**
code NexisHub (`docs/APPS_NATIVES.md`, « Code NexisHub, Face ID et
empreinte ») : ce code protège le téléphone, pas le compte.

Le vol visé est celui du **numéro** : quelqu'un fait refaire la carte SIM à
son nom, ou prend le compte Telegram ou WhatsApp lié au numéro. Il reçoit
alors le code de connexion. Ce qui le freine aujourd'hui :

- le délai de 72 h avant toute sortie d'argent depuis un nouveau téléphone
  (`NEW_DEVICE_MONEY_DELAY`) ;
- l'alerte « Nouvel appareil » envoyée aux autres canaux, avec « Ce n'est pas
  moi » (`report_not_me`).

C'est solide pour l'argent, mais le voleur voit quand même le compte (missions,
adresses, historique) et peut attendre que le titulaire ne regarde pas son
téléphone. La double vérification ferme cette porte : **un code de connexion
seul ne suffit plus à ouvrir le compte sur un nouveau téléphone.**

## 2. Ce que ce n'est pas

- **Pas à chaque ouverture de l'app** : le code NexisHub ou Face ID s'en
  charge déjà, sur le téléphone.
- **Pas de SMS comme deuxième facteur** : c'est déjà le canal du premier, et
  c'est celui qu'on vole.
- **Pas d'e-mail comme deuxième facteur** : une boîte e-mail se récupère le
  plus souvent avec le même numéro de téléphone. Une adresse e-mail vérifiée
  sert seulement à recevoir les alertes (voir
  `docs/CONCEPTION_INFOS_FACULTATIVES.md`).
- **Pas d'app d'authentification (Google Authenticator) au départ** : peu
  connue des utilisateurs visés. Elle pourra venir plus tard, en option.

## 3. Quand elle est demandée

Pour un compte où la double vérification est active, le deuxième facteur est
demandé, **en plus** du code de connexion, pour :

| Action | Pourquoi |
| --- | --- |
| Se connecter sur un nouveau téléphone (`sign_in` sur un compte existant, clé d'appareil inconnue) | Le cas du vol de numéro. |
| Relier un nouveau compte Telegram ou WhatsApp au compte NexisHub | Même vol, par un autre canal. |
| Changer le numéro vérifié du compte (quand cette fonction existera) | Le numéro est la clé de tout le reste. |
| Désactiver la double vérification | Sinon un voleur la désactiverait d'abord. |
| Créer un nouveau code de secours | Idem. |

Elle n'est **pas** demandée pour un téléphone déjà connecté (ses sessions se
renouvellent comme aujourd'hui), ni pour la création d'un compte neuf.

## 4. Pour qui

- **Prestataires : obligatoire** dès que le compte est vérifié
  (`provider_profiles.verified_at` posé). Le prestataire la met en place au
  premier lancement qui suit sa vérification. Tant qu'il ne l'a pas fait, il
  ne peut pas se rendre disponible (même garde que `PROVIDER_VERIFIED_STATUSES`,
  appliquée par `profils.py`), pour qu'il ne puisse pas recevoir d'argent sans
  elle.
- **Clients : facultative**, proposée après le premier paiement réussi (le
  moment où le compte commence à valoir quelque chose). « Plus tard » est
  possible ; la proposition revient au plus une fois par mois.

## 5. Les deux façons de prouver que c'est bien la personne

### 5.1 L'accord d'un téléphone déjà connecté (façon principale)

1. Le nouveau téléphone donne le bon code de connexion. Au lieu de créer
   l'appareil et la session, le serveur crée une **connexion en attente**
   (`pending_sign_ins`, section 7), liée à la clé du nouveau téléphone. Le code
   de connexion est consommé dans la même transaction.
2. Les téléphones déjà connectés du compte reçoivent la demande : à
   l'ouverture de l'app, et par notification quand l'envoi de notifications
   de l'app existera. Le message dit le modèle du téléphone, l'heure et la
   ville approximative quand elle est connue : « Quelqu'un se connecte sur un
   Tecno Spark 10. C'est vous ? »
3. **Oui** : il faut d'abord Face ID, l'empreinte ou le code NexisHub sur
   l'ancien téléphone. La réponse est une demande signée par la clé de
   l'ancien téléphone (`verify_signed_request`, nonce et horodatage
   compris). Le serveur crée alors l'appareil et la session du nouveau
   téléphone, comme `sign_in` aujourd'hui, en une seule transaction.
4. **Non** : la connexion en attente est refusée, le nouveau téléphone ne
   pourra pas réessayer avec cette clé, et la personne voit « Ce n'est pas
   vous ? Protégez votre compte » (changer de code de secours, prévenir
   NexisHub).
5. Sans réponse en **5 minutes**, la demande expire. Le nouveau téléphone
   peut passer au code de secours.

**Règle : refuser peut se faire depuis n'importe quel canal du compte
(app, Telegram, WhatsApp, e-mail). Accepter, seulement depuis un téléphone
déjà connecté par l'app.** Un compte Telegram peut avoir été pris avec le
numéro : il ne doit jamais pouvoir dire oui.

Plus tard, pour que le serveur sache que Face ID ou l'empreinte a vraiment
été faite, l'app créera une deuxième clé, qui ne signe qu'après Face ID ou
l'empreinte (iOS : `SecAccessControl` avec `.biometryCurrentSet` ;
Android : clé du Keystore avec `setUserAuthenticationRequired`). C'est le
point « relier la clé du téléphone à Face ID » de `docs/APPS_NATIVES.md`.
Sans Face ID ni empreinte, l'accord reste signé par la clé du téléphone après
le code NexisHub vérifié sur le téléphone : c'est moins fort, et c'est dit
dans l'écran des réglages.

### 5.2 Le code de secours du compte

- **8 chiffres**, choisis par la personne à l'activation (tapés deux fois),
  pour ne pas le confondre avec le code NexisHub du téléphone (6 chiffres).
  Mêmes refus que le code du téléphone (chiffres répétés, suites, moitiés
  pareilles), et il doit être différent du code NexisHub de ce téléphone
  (vérifié sur le téléphone, jamais envoyé).
- Gardé par le serveur **haché avec une clé serveur à part**
  (`SECOND_FACTOR_HASH_KEY`, HMAC-SHA256 comme `app_auth`), jamais en clair,
  jamais dans un journal.
- **5 essais** par période de 24 h et par compte, comptés en base, sous
  verrou (deux essais simultanés ne dépassent pas la limite). Au 5e essai
  faux : plus aucun essai pendant 24 h, et alerte sur tous les canaux.
- Il sert quand aucun téléphone connecté ne peut répondre (perdu, volé,
  éteint). Chaque usage est suivi d'une alerte sur tous les canaux.

## 6. Si la personne a tout perdu

Ancien téléphone et code de secours perdus : une **récupération** se demande
depuis le nouveau téléphone, après le bon code de connexion.

- **Prestataire** : il refait la vidéo guidée du visage (l'étape de « Devenir
  prestataire »). Une personne de l'équipe la compare au dossier d'identité
  (`docs/CONCEPTION_IDENTITE_PRESTATAIRE.md`) et accepte ou refuse, avec une
  raison. Jamais d'IA pour cette décision (AGENTS.md). **À voir avec le
  juriste** : réutiliser la vidéo du dossier pour ce but.
- **Client** : un **délai de 7 jours**, avec des messages sur tous les canaux
  du compte au début, au 3e jour et au 6e jour. Le vrai titulaire, s'il voit
  passer la demande, l'annule d'un appui (« Ce n'est pas moi »).
- Dans les deux cas : aucune sortie d'argent pendant la récupération ; une
  fois acceptée, le nouveau téléphone est relié avec le délai de 72 h
  habituel ; l'ancien code de secours ne vaut plus, la personne en choisit un
  nouveau.

## 7. Données (proposition)

| Table | Contenu | Règles |
| --- | --- | --- |
| `second_factor_settings` | compte, active depuis, obligatoire (prestataire), empreinte du code de secours, version de la clé de hachage, essais et date de blocage | Une ligne au plus par compte. Désactivation = colonne remplie, jamais une ligne effacée. |
| `pending_sign_ins` | identifiant public aléatoire, compte, empreinte de la clé du nouveau téléphone, modèle et plateforme, créée, expire (5 min), décision (`approved`, `denied`, `expired`), téléphone qui a décidé, moyen (`device`, `recovery_code`, `recovery`) | Une seule décision ; elle ne change plus. Un refus interdit cette clé pour ce compte. |
| `account_recoveries` | compte, type (`provider_video`, `client_delay`), clé du nouveau téléphone, demandée, fin du délai, décision, personne de l'équipe, raison | Une seule récupération ouverte par compte. |

Chaque étape écrit dans `auth_events` (déjà en ajout seul) : demande,
accord, refus, expiration, code de secours juste ou faux, blocage,
récupération demandée, annulée, acceptée.

## 8. Ce qui change dans le code existant

- `app_sessions.sign_in` : si le compte existe, que la clé est nouvelle et
  que la double vérification est active, il ne crée ni appareil ni session.
  Il rend `second_factor_required` avec l'identifiant de la connexion en
  attente. Le code de connexion est consommé dans la même transaction, pour
  qu'il ne puisse pas resservir.
- Nouvelles routes de l'API de l'app (`/api/app/v1`) :
  - le nouveau téléphone demande l'état de sa connexion en attente (signé par
    sa clé) ;
  - il donne le code de secours (signé par sa clé) ;
  - un téléphone connecté liste les demandes et dit oui ou non
    (`verify_signed_request`) ;
  - réglages : activer, désactiver, changer le code de secours ;
  - récupération : demander, annuler.
- Bot Telegram : la liaison d'un nouveau compte Telegram passe par la même
  règle ; le message d'alerte porte un bouton « Ce n'est pas moi » (refus
  seulement).
- Désactiver la double vérification (clients seulement) demande le deuxième
  facteur, puis prend effet **après 7 jours**, avec alertes et annulation
  possible.

## 9. Pannes et cas limites

| Cas | Ce qui se passe |
| --- | --- |
| Serveur injoignable pendant l'accord | Rien n'est créé. Le nouveau téléphone redemande l'état ; l'ancien redit oui. L'accord est idempotent (même demande, même résultat). |
| Deux téléphones répondent en même temps, l'un oui et l'autre non | La première décision écrite gagne (verrou sur la ligne). Le refus est toujours pris si les deux arrivent dans la même seconde. |
| Accord après l'expiration | Refusé : « Demande expirée ». |
| Le nouveau téléphone change de clé (app réinstallée) | La connexion en attente ne vaut plus : il faut un nouveau code de connexion. |
| Clé de hachage du code de secours absente du serveur | Toute activation et tout usage sont refusés (en cas de doute, on refuse), comme `app_auth`. |
| Un prestataire n'a plus aucun téléphone et ne répond plus | Il reste hors ligne ; l'argent déjà gagné reste dans le registre, rien n'est perdu. |

## 10. Tests attendus (avant toute fusion)

- Un code de connexion juste, seul, ne crée ni appareil ni session sur un
  compte protégé.
- Oui depuis un téléphone connecté : appareil et session créés une seule
  fois, même si l'accord est rejoué (nonce, idempotence).
- Non, puis oui : le non reste. Oui après 5 minutes : refusé.
- Accord signé par un téléphone coupé, ou d'un autre compte : refusé.
- Code de secours : 5 essais faux, blocage 24 h, sous demandes simultanées.
- Le code de secours n'apparaît dans aucune réponse, aucun journal, aucun
  `auth_events`.
- Récupération client : annulée par « Ce n'est pas moi » ; acceptée seulement
  après 7 jours ; aucune sortie d'argent pendant le délai.
- Prestataire vérifié sans double vérification : ne peut pas se rendre
  disponible.
- Les mêmes tests sur Postgres et sur SQLite, comme toute la suite.

Revue par l'agent `security-reviewer` avant chaque commit côté serveur.

## 11. Décisions attendues de Ben

1. **Délai de 72 h après un accord donné par un téléphone connecté** : le
   garder tel quel (proposé), ou le réduire à 24 h quand un ancien téléphone a
   dit oui.
2. **Récupération d'un prestataire par vidéo** : d'accord sur le principe,
   sous réserve du juriste ?
3. **Délai de récupération d'un client** : 7 jours (proposé), ou un autre.
4. **Envoi des notifications de l'app** (Firebase Cloud Messaging pour
   Android, APNs pour iPhone, compte Apple Developer requis) : nécessaire pour
   que l'ancien téléphone soit prévenu sans ouvrir l'app.

## 12. Découpage

1. Ce document, validé par Ben (et le juriste pour la section 6).
2. Serveur : tables, migration Alembic, règles, routes, tests, revue de
   sécurité.
3. Apps iOS et Android : activation, code de secours, écran « C'est vous ? »,
   attente sur le nouveau téléphone, récupération.
4. Bot Telegram : liaison d'un nouveau compte et bouton « Ce n'est pas moi ».

Chaque étape est complète en elle-même ; aucune n'est fusionnée sans CI
verte.
