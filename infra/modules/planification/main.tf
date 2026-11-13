# Tâches planifiées : Cloud Scheduler lance le Job `taches` à l'heure dite,
# avec le nom de la tâche en argument (`tache <nom>`).
#
# Le calendrier n'est écrit qu'à un endroit : `CALENDRIER` dans
# backend/app/taches.py. `infra/calendrier.json` en est la copie lue par
# Terraform, et un test (tests/test_infra_calendrier.py) échoue en CI dès que
# les deux diffèrent.
#
# Deux exécutions ne se chevauchent jamais : chaque tâche prend un verrou
# Postgres (taches.py). Un échec est retenté une fois par le Job, et visible
# dans la supervision.

resource "google_cloud_scheduler_job" "tache" {
  for_each = var.calendrier

  name        = "${var.prefixe}-${each.key}"
  region      = var.region_planificateur
  schedule    = each.value
  time_zone   = "Etc/UTC"
  description = "Tâche Nexis « ${each.key} » (backend/app/taches.py)"

  attempt_deadline = "180s"

  retry_config {
    retry_count = 0
  }

  http_target {
    http_method = "POST"
    uri         = "https://run.googleapis.com/v2/projects/${var.projet}/locations/${var.region}/jobs/${var.job}:run"
    body = base64encode(jsonencode({
      overrides = {
        containerOverrides = [{ args = ["tache", each.key] }]
      }
    }))
    headers = {
      "Content-Type" = "application/json"
    }

    oauth_token {
      service_account_email = var.compte_planificateur
      scope                 = "https://www.googleapis.com/auth/cloud-platform"
    }
  }
}

# Le planificateur peut lancer ce Job (et lui seul), avec ses propres arguments.
resource "google_cloud_run_v2_job_iam_member" "planificateur" {
  name     = var.job
  location = var.region
  role     = "roles/run.jobsExecutorWithOverrides"
  member   = "serviceAccount:${var.compte_planificateur}"
}
