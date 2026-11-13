# Infrastructure de Nexis Hub (Terraform)

Tout ce qui tourne en hébergé est décrit ici : réseau, base, Redis, services
Cloud Run, tâches planifiées, entrée publique, supervision. Plan de référence :
`hebergement/plan-deploiement-2026-11-07.md` (dossier du projet).

Rien dans ce dossier n'a été appliqué. L'application (`terraform apply`) est
une dépense : elle attend l'accord de Ben.

## Structure

- `bootstrap/` : état Terraform, identité GitHub sans clé, registre d'images.
  Appliqué une fois, à la main, avec l'état local (il ne contient aucun secret).
- `modules/` : un module par sujet, sans valeur propre à un environnement.
  - `reseau` : VPC, sous-réseau, IP de sortie fixe (Cloud NAT).
  - `base` : Cloud SQL Postgres 17, HA en prod, PITR, IP privée seule.
  - `redis` : Memorystore Redis 7, AUTH et TLS.
  - `secrets` : déclarations Secret Manager (les valeurs ne passent jamais par Terraform).
  - `identites` : un compte de service par rôle, droits minimaux, identité GitHub.
  - `services` : registre, services Cloud Run (backend, bot, miniapp), Jobs
    (migration, tâches, réglage du webhook).
  - `service_run` : un service Cloud Run, utilisé par `services`.
  - `planification` : Cloud Scheduler, une tâche par entrée de `calendrier.json`.
  - `entree` : répartiteur HTTPS, certificat, Cloud Armor (Cloudflare seulement).
  - `supervision` : sondes, alertes, budget.
- `environnements/test` et `environnements/prod` : les mêmes modules, avec des
  tailles et des réglages différents. La prod exige HA partout, un vrai
  agrégateur et l'approbation de Ben dans l'environnement GitHub `production`.
- `calendrier.json` : copie du calendrier de `backend/app/taches.py`, vérifiée
  par `tests/test_infra_calendrier.py`.
- `cloudflare_ips.json` : plages Cloudflare, à mettre à jour (voir plus bas).

## Règles

- Aucune valeur de secret dans Git. Les secrets sont déposés à la main dans
  Secret Manager (ci-dessous).
- Chaque changement d'infrastructure passe par une PR : la CI valide
  (`terraform fmt`, `validate`), Ben lit le `terraform plan` avant `apply`.
- Aucune ressource n'est créée sans l'accord de Ben, et aucun paiement n'est
  engagé par ce code.

## Procédure (à faire par Ben, dans l'ordre)

1. **Projet Google Cloud** : créer le projet `test` (sans organisation pour
   l'instant). Activer la facturation et les API : Cloud Run, Cloud SQL,
   Memorystore, Compute Engine, Secret Manager, Artifact Registry, Cloud
   Scheduler, Cloud Monitoring, Service Networking, Certificate Manager,
   IAM, IAM Credentials, Cloud Resource Manager.
2. **Amorçage** : `cd infra/bootstrap && terraform init && terraform apply`
   (variables `projet` et `region`). Reporter les sorties
   `pool_identite_github` dans `environnements/test/main.tf` et
   `fournisseur_identite_github` dans la configuration GitHub.
3. **Environnement GitHub** `test` (et `production` plus tard, avec
   approbation obligatoire de Ben) : variables de dépôt pour le fournisseur
   d'identité et le projet.
4. **Comptes de la base** (à la main, une fois, jamais dans Terraform) :
   `nexis_app` (pas de droits de schéma) et `nexis_migration` (propriétaire du
   schéma), mots de passe générés localement et déposés dans Secret Manager
   sous `DATABASE_URL` et `DATABASE_URL_MIGRATION`.
5. **Secrets** : une commande par secret, la valeur saisie sans être
   enregistrée dans l'historique du shell :
   `printf '%s' "$VALEUR" | gcloud secrets versions add NOM --data-file=-`.
   Les noms sont ceux de `module.identites` (`lectures_secrets`). Générés
   localement : `APP_CODE_HMAC_KEY`, `WEBHOOK_SECRET_TOKEN`,
   `BACKEND_API_KEY_TELEGRAM` (au moins 32 caractères). Fournis par ailleurs :
   `BOT_TOKEN` (le bot de test en test), `REDIS_URL` (URL `rediss://` avec le
   mot de passe AUTH), `REDIS_CA` (certificat public de Redis).
6. **Premier déploiement** : publier l'image dans le registre (`docker push`
   par la CI), puis renseigner `image_initiale` et appliquer. Les services ne
   sont créés qu'avec une image.
7. **Domaine** : créer chez Cloudflare l'enregistrement de validation du
   certificat (sortie `validation_certificat`, sans proxy), puis l'enregistrement
   `A` du domaine vers `ip_entree`, proxy activé.
8. **Agrégateur** : déclarer `ip_sortie_agregateur` comme adresse autorisée.
9. **Webhook Telegram** : lancer le Job `reglage-webhook` (la CI le fait après
   chaque déploiement du bot).

## Mettre à jour les plages Cloudflare

`cloudflare_ips.json` reprend https://www.cloudflare.com/ips-v4 et ips-v6.
À mettre à jour dès que Cloudflare publie un changement (la liste change
rarement). Un oubli bloque le trafic légitime, jamais l'argent.

## Limites connues (à traiter avant la production)

- `checkov` et `tflint` tournent dans la CI (versions et empreintes épinglées). Chaque règle `checkov` écartée est justifiée à côté de la ressource (`#checkov:skip=...`). Restent à décider : la montée en version de Postgres (17), les journaux d'accès du bucket d'état (CKV_GCP_62) et les clés propres pour le registre d'images (CSEK).
- Le premier `apply` n'a jamais été joué : la validation est statique seulement.
