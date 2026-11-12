# Supervision : sondes externes, alertes et budget. Tout part par e-mail
# (et l'application mobile Google Cloud si Ben l'installe).
#
# - Sondes HTTPS chaque minute, depuis plusieurs continents, par le domaine
#   public (donc à travers Cloudflare) : Mini App, backend, bot.
# - Échec d'une tâche planifiée ou de son déclenchement.
# - Disque de la base au-delà de 80 %.
# - Budget mensuel : 50 %, 90 %, 100 %.

data "google_project" "projet" {
  project_id = var.projet
}

resource "google_monitoring_notification_channel" "email" {
  display_name = "Alertes Nexis (${var.prefixe})"
  type         = "email"
  labels = {
    email_address = var.email_alertes
  }
}

locals {
  sondes = {
    miniapp = "/health/ready"
    backend = "/sante/backend"
    bot     = "/sante/bot"
  }
  canaux = [google_monitoring_notification_channel.email.id]
}

resource "google_monitoring_uptime_check_config" "sonde" {
  for_each     = var.services_deployes ? local.sondes : {}
  display_name = "${var.prefixe} ${each.key}"
  timeout      = "10s"
  period       = "60s"

  http_check {
    path         = each.value
    port         = 443
    use_ssl      = true
    validate_ssl = true
    accepted_response_status_codes {
      status_class = "STATUS_CLASS_2XX"
    }
  }

  monitored_resource {
    type = "uptime_url"
    labels = {
      project_id = var.projet
      host       = var.domaine
    }
  }
}

resource "google_monitoring_alert_policy" "sonde" {
  for_each     = google_monitoring_uptime_check_config.sonde
  display_name = "${var.prefixe} : ${each.key} injoignable"
  combiner     = "OR"

  conditions {
    display_name = "Sonde ${each.key} en échec"
    condition_threshold {
      filter          = "metric.type=\"monitoring.googleapis.com/uptime_check/check_passed\" AND metric.label.check_id=\"${each.value.uptime_check_id}\" AND resource.type=\"uptime_url\""
      comparison      = "COMPARISON_GT"
      threshold_value = 1
      duration        = "120s"
      aggregations {
        alignment_period     = "1200s"
        per_series_aligner   = "ALIGN_NEXT_OLDER"
        cross_series_reducer = "REDUCE_COUNT_FALSE"
        group_by_fields      = ["resource.label.*"]
      }
    }
  }

  notification_channels = local.canaux
}

resource "google_monitoring_alert_policy" "job_en_echec" {
  display_name = "${var.prefixe} : tâche ou migration en échec"
  combiner     = "OR"

  conditions {
    display_name = "Exécution de Job en échec"
    condition_threshold {
      filter          = "metric.type=\"run.googleapis.com/job/completed_execution_count\" AND resource.type=\"cloud_run_job\" AND metric.label.result=\"failed\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "0s"
      aggregations {
        alignment_period     = "300s"
        per_series_aligner   = "ALIGN_DELTA"
        cross_series_reducer = "REDUCE_SUM"
        group_by_fields      = ["resource.label.job_name"]
      }
    }
  }

  notification_channels = local.canaux
}

resource "google_monitoring_alert_policy" "declenchement_en_echec" {
  display_name = "${var.prefixe} : Cloud Scheduler n'a pas pu lancer une tâche"
  combiner     = "OR"

  conditions {
    display_name = "Erreur de Cloud Scheduler"
    condition_matched_log {
      filter = "resource.type=\"cloud_scheduler_job\" AND severity>=ERROR"
    }
  }

  alert_strategy {
    notification_rate_limit {
      period = "300s"
    }
    auto_close = "1800s"
  }

  notification_channels = local.canaux
}

resource "google_monitoring_alert_policy" "disque_base" {
  display_name = "${var.prefixe} : disque de la base au-delà de 80 %"
  combiner     = "OR"

  conditions {
    display_name = "Disque Cloud SQL > 80 %"
    condition_threshold {
      filter          = "metric.type=\"cloudsql.googleapis.com/database/disk/utilization\" AND resource.type=\"cloudsql_database\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0.8
      duration        = "300s"
      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_MEAN"
      }
    }
  }

  notification_channels = local.canaux
}

resource "google_billing_budget" "mensuel" {
  billing_account = var.compte_facturation
  display_name    = "Nexis ${var.prefixe}"

  budget_filter {
    projects = ["projects/${data.google_project.projet.number}"]
  }

  amount {
    specified_amount {
      currency_code = "USD"
      units         = tostring(var.budget_mensuel_usd)
    }
  }

  threshold_rules {
    threshold_percent = 0.5
  }
  threshold_rules {
    threshold_percent = 0.9
  }
  threshold_rules {
    threshold_percent = 1.0
  }

  all_updates_rule {
    monitoring_notification_channels = local.canaux
    disable_default_iam_recipients   = false
  }
}
