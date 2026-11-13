# Ce qui fait tourner le code : registre d'images, trois services Cloud Run
# (backend, bot, miniapp) et trois Cloud Run Jobs (migration, taches,
# reglage-webhook). Une seule image pour tout ; le rôle est le premier
# argument (docker/lancer.sh).
#
# Terraform crée les services et les Jobs avec `image_initiale` ; ensuite la
# CI publie chaque nouvelle version (nouvelle révision), d'où `ignore_changes`
# sur l'image. Tant que `image_initiale` est vide, seuls le registre d'images
# et ses droits existent : la première image doit y être publiée avant
# (infra/README.md, « Premier déploiement »).
#
# Exposition : aucun service n'est joignable directement depuis Internet
# (`INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER`). Le public passe par le
# répartiteur de charge (module entree), qui n'accepte que Cloudflare et ne
# route vers le backend que /api/app/* et /api/payments/webhook/*. Le bot et la
# Mini App appellent les routes /api/bot/* du backend par le réseau privé
# (sortie VPC), avec la clé de service du canal Telegram.

locals {
  deploye  = var.image_initiale != null
  url_site = "https://${var.domaine}"

  # Processus qui touchent à l'argent (backend, tâches) : nexis_config refuse
  # de démarrer hors développement s'il manque un de ces réglages.
  # Les admins ne sont pas un réglage : ils sont enregistrés en base
  # (python -m backend.app.admins), plusieurs personnes possibles.
  env_argent = merge(var.reglages_argent, {
    APP_ENV = var.app_env
  })

  secret = var.secrets

  # Le bot lit REDIS_URL, de la forme
  # rediss://:<AUTH>@<hôte>:6378/0?ssl_ca_certs=/secrets/redis/ca.pem
  url_backend = one(module.backend[*].uri)

  # Le bot et le Job qui enregistre son webhook vérifient la même configuration
  # (nexis_config, rôle « bot ») : mêmes variables.
  env_bot = {
    APP_ENV          = var.app_env
    BACKEND_BASE_URL = local.url_backend
    MINI_APP_URL     = local.url_site
    WEBHOOK_URL      = local.url_site
    BOT_RUN_MODE     = "webhook"
  }
  secrets_bot = {
    BOT_TOKEN                = local.secret["BOT_TOKEN"]
    BACKEND_API_KEY_TELEGRAM = local.secret["BACKEND_API_KEY_TELEGRAM"]
    WEBHOOK_SECRET_TOKEN     = local.secret["WEBHOOK_SECRET_TOKEN"]
    REDIS_URL                = local.secret["REDIS_URL"]
  }

  redis_ca = {
    "redis-ca" = { secret = local.secret["REDIS_CA"], dossier = "/secrets/redis", fichier = "ca.pem" }
  }
}

resource "google_artifact_registry_repository" "images" {
  #checkov:skip=CKV_GCP_84:Chiffrement par les clés gérées par Google. Les clés propres (CSEK) ajoutent une gestion de clés sans gain pour un dépôt privé.
  repository_id = var.prefixe
  location      = var.region
  format        = "DOCKER"
  description   = "Images de Nexis Hub : une étiquette par commit, jamais réécrite."
  labels        = var.etiquettes

  docker_config {
    immutable_tags = true
  }
}

resource "google_artifact_registry_repository_iam_member" "deploiement" {
  repository = google_artifact_registry_repository.images.name
  location   = var.region
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${var.compte_deploiement}"
}

# --- Services ------------------------------------------------------------------

module "backend" {
  source = "../service_run"
  count  = local.deploye ? 1 : 0

  nom            = "${var.prefixe}-backend"
  role           = "backend"
  region         = var.region
  image          = var.image_initiale
  compte         = var.comptes["backend"]
  reseau_id      = var.reseau_id
  sous_reseau_id = var.sous_reseau_id
  env            = merge(local.env_argent, { NEXIS_BOT_USERNAME = var.nom_bot_telegram })
  env_secrets = {
    DATABASE_URL             = local.secret["DATABASE_URL"]
    BACKEND_API_KEY_TELEGRAM = local.secret["BACKEND_API_KEY_TELEGRAM"]
    APP_CODE_HMAC_KEY        = local.secret["APP_CODE_HMAC_KEY"]
    BOT_TOKEN                = local.secret["BOT_TOKEN"]
  }
  instances_min          = var.instances_min_backend
  instances_max          = var.instances_max
  protection_suppression = var.protection_suppression
  etiquettes             = var.etiquettes
}

module "miniapp" {
  source = "../service_run"
  count  = local.deploye ? 1 : 0

  nom            = "${var.prefixe}-miniapp"
  role           = "miniapp"
  region         = var.region
  image          = var.image_initiale
  compte         = var.comptes["miniapp"]
  reseau_id      = var.reseau_id
  sous_reseau_id = var.sous_reseau_id
  env = {
    APP_ENV          = var.app_env
    BACKEND_BASE_URL = local.url_backend
  }
  env_secrets = {
    BOT_TOKEN                = local.secret["BOT_TOKEN"]
    BACKEND_API_KEY_TELEGRAM = local.secret["BACKEND_API_KEY_TELEGRAM"]
  }
  instances_min          = var.instances_min_autres
  instances_max          = var.instances_max
  protection_suppression = var.protection_suppression
  etiquettes             = var.etiquettes
}

module "bot" {
  source = "../service_run"
  count  = local.deploye ? 1 : 0

  nom                    = "${var.prefixe}-bot"
  role                   = "bot"
  region                 = var.region
  image                  = var.image_initiale
  compte                 = var.comptes["bot"]
  reseau_id              = var.reseau_id
  sous_reseau_id         = var.sous_reseau_id
  env                    = local.env_bot
  env_secrets            = local.secrets_bot
  fichiers_secrets       = local.redis_ca
  instances_min          = var.instances_min_autres
  instances_max          = var.instances_max
  protection_suppression = var.protection_suppression
  etiquettes             = var.etiquettes
}

# --- Jobs ------------------------------------------------------------------------

locals {
  jobs = {
    # `alembic upgrade head`, lancé par la CI avant chaque nouvelle révision.
    migration = {
      compte      = var.comptes["migration"]
      args        = ["migration"]
      env         = { APP_ENV = var.app_env }
      env_secrets = { DATABASE_URL = local.secret["DATABASE_URL_MIGRATION"] }
      fichiers    = {}
      timeout     = "600s"
      essais      = 0
    }
    # Une tâche du calendrier ; Cloud Scheduler donne son nom en argument
    # (module planification). Sans argument, le Job affiche le calendrier.
    taches = {
      compte = var.comptes["taches"]
      args   = ["calendrier"]
      env    = local.env_argent
      env_secrets = {
        DATABASE_URL = local.secret["DATABASE_URL"]
        BOT_TOKEN    = local.secret["BOT_TOKEN"]
      }
      fichiers = {}
      timeout  = "540s"
      # Les tâches sont idempotentes et protégées par un verrou Postgres.
      essais = 1
    }
    # Enregistre le webhook Telegram, lancé par la CI après le déploiement du bot.
    reglage-webhook = {
      compte      = var.comptes["bot"]
      args        = ["webhook-setup"]
      env         = local.env_bot
      env_secrets = local.secrets_bot
      fichiers    = local.redis_ca
      timeout     = "120s"
      essais      = 0
    }
  }
}

resource "google_cloud_run_v2_job" "job" {
  for_each = { for nom, job in local.jobs : nom => job if local.deploye }

  name                = "${var.prefixe}-${each.key}"
  location            = var.region
  deletion_protection = var.protection_suppression
  labels              = var.etiquettes

  template {
    task_count = 1

    template {
      service_account       = each.value.compte
      execution_environment = "EXECUTION_ENVIRONMENT_GEN2"
      timeout               = each.value.timeout
      max_retries           = each.value.essais

      vpc_access {
        network_interfaces {
          network    = var.reseau_id
          subnetwork = var.sous_reseau_id
        }
        egress = "ALL_TRAFFIC"
      }

      containers {
        image = var.image_initiale
        args  = each.value.args

        resources {
          limits = {
            cpu    = "1"
            memory = "512Mi"
          }
        }

        dynamic "env" {
          for_each = each.value.env
          content {
            name  = env.key
            value = env.value
          }
        }

        dynamic "env" {
          for_each = each.value.env_secrets
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
          for_each = each.value.fichiers
          content {
            name       = volume_mounts.key
            mount_path = volume_mounts.value.dossier
          }
        }
      }

      dynamic "volumes" {
        for_each = each.value.fichiers
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
  }

  lifecycle {
    ignore_changes = [
      template[0].template[0].containers[0].image,
      client,
      client_version,
    ]
  }
}
