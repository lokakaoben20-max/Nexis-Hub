# Postgres de l'environnement : la seule donnée irremplaçable (registre de
# l'argent compris).
#
# - Adresse privée seule, connexions chiffrées obligatoires.
# - Sauvegardes quotidiennes + journaux de transactions : restauration à la
#   minute près (PITR) sur `jours_pitr` jours.
# - Haute disponibilité régionale en production (bascule automatique sur une
#   autre zone), une seule zone en test.
# - Protection contre la suppression, côté Terraform et côté Google.
#
# Les utilisateurs de la base (appli et migration) ne sont PAS créés ici : leur
# mot de passe finirait dans l'état Terraform. Ils sont créés une fois à la main
# (infra/README.md, « Comptes de la base »), et leurs URL déposées dans
# Secret Manager.

resource "google_sql_database_instance" "postgres" {
  #checkov:skip=CKV_GCP_6:ssl_mode = ENCRYPTED_ONLY impose le chiffrement de toute connexion (remplace l'ancien réglage require_ssl).
  #checkov:skip=CKV_GCP_79:PostgreSQL 16 est pris en charge. La montée en version 17 est une décision séparée (compatibilité de l'application, test préalable).
  name                = "${var.prefixe}-postgres"
  region              = var.region
  database_version    = "POSTGRES_16"
  deletion_protection = var.protection_suppression

  settings {
    edition                     = "ENTERPRISE"
    tier                        = var.tier
    availability_type           = var.haute_disponibilite ? "REGIONAL" : "ZONAL"
    disk_type                   = "PD_SSD"
    disk_size                   = var.disque_go
    disk_autoresize             = true
    deletion_protection_enabled = var.protection_suppression

    ip_configuration {
      ipv4_enabled                                  = false
      private_network                               = var.reseau_id
      ssl_mode                                      = "ENCRYPTED_ONLY"
      enable_private_path_for_google_cloud_services = false
    }

    backup_configuration {
      enabled                        = true
      start_time                     = var.heure_sauvegarde_utc
      location                       = var.region
      point_in_time_recovery_enabled = true
      transaction_log_retention_days = var.jours_pitr

      backup_retention_settings {
        retained_backups = var.sauvegardes_conservees
        retention_unit   = "COUNT"
      }
    }

    maintenance_window {
      # Dimanche, 2 h UTC (3 h à Kinshasa) : le moment le plus calme.
      day          = 7
      hour         = 2
      update_track = "stable"
    }

    insights_config {
      query_insights_enabled  = true
      record_application_tags = false
      record_client_address   = false
    }

    # Journalisation recommandée (règles CIS Cloud SQL Postgres).
    database_flags {
      name  = "log_checkpoints"
      value = "on"
    }
    database_flags {
      name  = "log_connections"
      value = "on"
    }
    database_flags {
      name  = "log_disconnections"
      value = "on"
    }
    database_flags {
      name  = "log_lock_waits"
      value = "on"
    }
    database_flags {
      name  = "log_hostname"
      value = "on"
    }
    database_flags {
      # Les DDL seulement : les requêtes de paiement ne sont pas journalisées
      # en clair (données personnelles et montants).
      name  = "log_statement"
      value = "ddl"
    }
    database_flags {
      # Durée des requêtes, sans leur texte.
      name  = "log_duration"
      value = "on"
    }
    database_flags {
      name  = "log_min_messages"
      value = "error"
    }
    database_flags {
      name  = "log_min_error_statement"
      value = "error"
    }
    database_flags {
      name  = "log_temp_files"
      value = "0"
    }
    database_flags {
      name  = "log_min_duration_statement"
      value = "-1"
    }
    database_flags {
      name  = "cloudsql.enable_pgaudit"
      value = "on"
    }

    user_labels = var.etiquettes
  }
}

resource "google_sql_database" "nexis" {
  name     = "nexis"
  instance = google_sql_database_instance.postgres.name
}
