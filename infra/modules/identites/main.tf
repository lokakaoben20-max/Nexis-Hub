# Comptes de service : un par rôle, chacun avec le strict nécessaire.
#
# - backend, bot, miniapp : les trois services Cloud Run ;
# - taches : les tâches planifiées (Cloud Run Job) ;
# - migration : `alembic upgrade head`, seul à pouvoir changer le schéma ;
# - planificateur : Cloud Scheduler, qui lance les tâches ;
# - deploiement : la CI GitHub, qui publie les images et les nouvelles
#   révisions. Elle s'identifie par Workload Identity Federation (jeton de
#   quelques minutes) : aucune clé Google n'existe, donc aucune ne peut fuir.
#   Seul un travail GitHub du dépôt Nexis Hub lancé dans l'environnement GitHub
#   `environnement_github` peut l'utiliser.
#
# Les accès aux secrets, à la base et aux tâches sont donnés là où ces
# ressources sont créées (modules secrets, services, planification).

locals {
  roles_execution = ["backend", "bot", "miniapp", "taches", "migration"]
}

resource "google_service_account" "execution" {
  for_each     = toset(local.roles_execution)
  account_id   = "${var.prefixe}-${each.key}"
  display_name = "Nexis ${each.key} (${var.prefixe})"
}

resource "google_service_account" "planificateur" {
  account_id   = "${var.prefixe}-planificateur"
  display_name = "Nexis Cloud Scheduler (${var.prefixe})"
}

resource "google_service_account" "deploiement" {
  account_id   = "${var.prefixe}-deploiement"
  display_name = "Nexis déploiement par la CI (${var.prefixe})"
}

# Journaux et métriques, pour chaque compte qui fait tourner du code.
resource "google_project_iam_member" "journaux" {
  for_each = google_service_account.execution
  project  = var.projet
  role     = "roles/logging.logWriter"
  member   = "serviceAccount:${each.value.email}"
}

resource "google_project_iam_member" "metriques" {
  for_each = google_service_account.execution
  project  = var.projet
  role     = "roles/monitoring.metricWriter"
  member   = "serviceAccount:${each.value.email}"
}

# La CI publie de nouvelles révisions des services et lance les Jobs
# (migration, réglage du webhook) ; elle ne crée ni ne supprime rien d'autre.
resource "google_project_iam_member" "deploiement_run" {
  project = var.projet
  role    = "roles/run.developer"
  member  = "serviceAccount:${google_service_account.deploiement.email}"
}

# Pour publier une révision qui tourne sous un compte, il faut pouvoir agir en
# son nom : seulement ces comptes-là.
resource "google_service_account_iam_member" "deploiement_agit_comme" {
  for_each           = google_service_account.execution
  service_account_id = each.value.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.deploiement.email}"
}

resource "google_service_account_iam_member" "deploiement_github" {
  service_account_id = google_service_account.deploiement.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${var.pool_identite_github}/attribute.depot_env/${var.depot_github}@${var.environnement_github}"
}

# Qui peut lire quel secret (moindre privilège). Le module secrets applique ces
# droits ; les valeurs, elles, sont déposées à la main.
locals {
  lectures_secrets = {
    DATABASE_URL             = ["backend", "taches"]
    DATABASE_URL_MIGRATION   = ["migration"]
    BOT_TOKEN                = ["backend", "miniapp", "bot", "taches"]
    BACKEND_API_KEY_TELEGRAM = ["backend", "miniapp", "bot"]
    APP_CODE_HMAC_KEY        = ["backend"]
    WEBHOOK_SECRET_TOKEN     = ["bot"]
    REDIS_URL                = ["bot"]
    REDIS_CA                 = ["bot"]
  }
}
