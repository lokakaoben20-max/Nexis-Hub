# Conception : informations facultatives du profil (e-mail et autres)

**Statut : proposition, demandée par Ben le 2026-11-26 (11 h 15). Rien n'est
codé.** La liste exacte des informations est à choisir par Ben (section 3).
Le principe de collecter le moins possible est **à confirmer avec le
juriste**.

## 1. Le principe

Aujourd'hui, un profil a seulement le prénom (client), le nom complet
(prestataire), la commune et le numéro vérifié du compte. Ben veut laisser
clients et prestataires **ajouter d'autres informations, s'ils le veulent**.

Règles pour chaque information :

- **Jamais obligatoire.** Rien dans NexisHub ne doit dépendre d'elle :
  commander, payer, recevoir une mission, se faire verser, tout marche sans
  elle.
- **Un usage écrit.** On ne demande que ce qui sert à quelque chose de précis,
  dit à l'écran à côté du champ (« Pour recevoir vos reçus par e-mail »).
- **Qui la voit, dit à l'écran.** « Visible par vous seulement », « Visible
  par NexisHub », ou « Visible par vos clients ». Les numéros et l'e-mail ne
  sont **jamais** montrés à l'autre partie d'une mission (choix de Ben : la
  messagerie dans l'app, numéros cachés).
- **Modifiable et effaçable** par la personne, à tout moment, depuis
  « Mes informations ». Effacer, c'est vraiment effacer (pas seulement
  masquer), sauf ce que la loi oblige à garder.
- **Une seule source** : le backend (`profils.py`), comme tout le profil.
  L'app, le bot et la Mini App lisent et écrivent par lui.

## 2. L'adresse e-mail

C'est l'information la plus utile, et elle demande le plus de soin.

- **À quoi elle sert** : recevoir les reçus de paiement et de versement, et
  les **alertes de sécurité** (nouveau téléphone, accord de connexion,
  récupération, code de secours utilisé). Depuis un e-mail d'alerte, on peut
  **refuser** (« Ce n'est pas moi »), jamais accepter
  (`docs/CONCEPTION_DOUBLE_VERIFICATION.md`, section 5.1).
- **À quoi elle ne sert pas** : se connecter, ou servir de deuxième facteur.
  Une boîte e-mail se récupère souvent avec le même numéro de téléphone.
- **Vérifiée avant usage** : un code de 6 chiffres envoyé à l'adresse,
  10 minutes, 5 essais (mêmes règles que les codes de connexion). Tant
  qu'elle n'est pas vérifiée, rien n'y est envoyé.
- **Une adresse vérifiée par compte**, et une même adresse vérifiée sur un
  seul compte (unicité en base, comme `phone_e164`).
- **Changer d'adresse** : l'ancienne adresse est prévenue. Sur un compte avec
  double vérification, il faut aussi le deuxième facteur.
- **À décider** : quel service d'envoi d'e-mails (Brevo, Amazon SES,
  Postmark…). Il faut un domaine à NexisHub (enregistrements SPF, DKIM et
  DMARC) pour que les messages n'arrivent pas en indésirables.

## 3. Les autres informations proposées (à choisir par Ben)

| Information | Pour qui | À quoi elle sert | Qui la voit |
| --- | --- | --- | --- |
| Adresse habituelle (quartier, avenue, numéro, repère) | Client | Remplir d'avance l'adresse d'une demande | La personne ; le prestataire **seulement** pour une mission acceptée |
| Deuxième numéro de contact | Client et prestataire | Joindre la personne si le premier ne répond pas (équipe NexisHub seulement) | NexisHub seulement |
| Photo de profil | Client et prestataire | Reconnaître la personne à l'arrivée | L'autre partie d'une mission acceptée |
| Langues parlées (français, lingala, swahili, kikongo, tshiluba, anglais) | Client et prestataire | Mettre en relation des gens qui se comprennent | L'autre partie d'une mission |
| Présentation courte (300 caractères) | Prestataire | Se présenter aux clients | Les clients |
| Années d'expérience | Prestataire | Aider le client à choisir | Les clients |
| Diplômes et certificats (photo) | Prestataire | Obtenir un badge après vérification par l'équipe | NexisHub ; le badge est visible par les clients |
| Horaires habituels | Prestataire | Ne pas recevoir de demandes hors de ses heures | NexisHub (tri des demandes) |

Pas proposé, parce que rien ne s'en servirait : date de naissance, genre,
profession d'un client, adresse du domicile d'un prestataire.

La photo de profil d'un prestataire n'est pas la vidéo d'identité : elle est
choisie par lui et visible par ses clients. La vidéo reste dans le dossier,
lue seulement par l'équipe (`docs/CONCEPTION_IDENTITE_PRESTATAIRE.md`). Pour
la photo de profil, la galerie reste permise : ce n'est pas une preuve
d'identité.

## 4. Données (proposition)

- `account_emails` : compte, adresse, vérifiée le, créée le ; unicité de
  l'adresse vérifiée.
- `email_challenges` : comme `login_challenges` (code haché avec une clé
  serveur, 10 minutes, 5 essais).
- Colonnes facultatives (toutes `nullable`, avec `server_default` quand il en
  faut un, voir le skill `migrations-alembic`) sur `client_profiles` et
  `provider_profiles`, ou une table `profile_details` par compte si Ben en
  retient beaucoup.
- Les photos (profil, diplômes) passent par `stored_files`, avec de nouveaux
  usages, comme les photos de service.

## 5. Dans les apps

« Mes informations » garde le prénom, le nom et la commune en haut. En
dessous, une section « Pour aller plus loin (facultatif) », où chaque ligne
dit à quoi elle sert et qui la voit. Rien n'est demandé à l'inscription : la
personne y vient quand elle veut. Une seule fois, après le premier paiement,
l'app propose d'ajouter un e-mail pour les reçus.

## 6. Décisions attendues de Ben

1. Les informations à garder dans la liste de la section 3.
2. Le service d'envoi d'e-mails, et le domaine de NexisHub.
3. Montrer ou non la photo de profil du client au prestataire (proposé : oui,
   seulement pour une mission acceptée).
