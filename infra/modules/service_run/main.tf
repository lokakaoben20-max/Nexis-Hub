# Un service Cloud Run de Nexis Hub (backend, bot ou miniapp), toujours
# construit de la même façon : voir le module `services` pour l'exposition.

resource "google_cloud_run_v2_service" "service" {
  name                 = var.nom
  location             = var.region
  ingress              = "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"
  deletion_protection  = var.protection_suppression
  invoker_iam_disabled = true # accès limité par l'entrée : répartiteur + Cloud Armor (module entree)
  labels               = var.etiquettes

  template {
    service_account                  = var.compte
    execution_environment            = "EXECUTION_ENVIRONMENT_GEN2"
    timeout                          = "60s"
    max_instance_request_concurrency = 40

    scaling {
      min_instance_count = var.instances_min
      max_instance_count = var.instances_max
    }

    vpc_access {
      network_interfaces {
        network    = var.reseau_id
        subnetwork = var.sous_reseau_id
      }
      # Tout sort par le VPC, donc par l'IP fixe du NAT ; les appels vers le
      # backend restent internes.
      egress = "ALL_TRAFFIC"
    }

    containers {
      image = var.image
      args  = [var.role]

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = var.cpu
          memory = var.memoire
        }
        cpu_idle          = true
        startup_cpu_boost = true
      }

      dynamic "env" {
        for_each = var.env
        content {
          name  = env.key
          value = env.value
        }
      }

      dynamic "env" {
        for_each = var.env_secrets
        content {
          name = env.key
          value_source {
            secret_key_ref {
              secret  = env.value
              version = "latest"
            }
          }
        }
      }

      dynamic "volume_mounts" {
        for_each = var.fichiers_secrets
        content {
          name       = volume_mounts.key
          mount_path = volume_mounts.value.dossier
        }
      }

      startup_probe {
        http_get {
          path = "/health/live"
        }
        period_seconds    = 2
        failure_threshold = 30
      }

      liveness_probe {
        http_get {
          path = "/health/live"
        }
        period_seconds    = 15
        failure_threshold = 3
      }
    }

    dynamic "volumes" {
      for_each = var.fichiers_secrets
      content {
        name = volumes.key
        secret {
          secret = volumes.value.secret
          items {
            version = "latest"
            path    = volumes.value.fichier
          }
        }
      }
    }
  }

  lifecycle {
    # La CI publie chaque nouvelle image (nouvelle révision).
    ignore_changes = [
      template[0].containers[0].image,
      client,
      client_version,
    ]
  }
}
