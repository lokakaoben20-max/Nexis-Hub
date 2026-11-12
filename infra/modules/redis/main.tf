# Redis de l'environnement : étapes de conversation du bot (FSM) et registre
# des updates Telegram déjà traitées. Jamais d'argent : perdre Redis interrompt
# des conversations, pas un paiement.
#
# - Adresse privée seule (accès privé aux services), mot de passe (AUTH) et
#   chiffrement TLS obligatoires.
# - Niveau Standard (réplique + bascule automatique) en production, Basic en test.
#
# Le mot de passe AUTH est généré par Google. Terraform le lit, il est donc
# dans l'état Terraform (bucket chiffré, accès limité : voir infra/README.md).
# Il n'est jamais écrit dans Git ni dans une sortie.

resource "google_redis_instance" "redis" {
  name                    = "${var.prefixe}-redis"
  region                  = var.region
  tier                    = var.haute_disponibilite ? "STANDARD_HA" : "BASIC"
  memory_size_gb          = var.memoire_go
  redis_version           = "REDIS_7_2"
  authorized_network      = var.reseau_id
  connect_mode            = "PRIVATE_SERVICE_ACCESS"
  auth_enabled            = true
  transit_encryption_mode = "SERVER_AUTHENTICATION"
  labels                  = var.etiquettes

  maintenance_policy {
    weekly_maintenance_window {
      day = "SUNDAY"
      start_time {
        hours   = 2
        minutes = 0
      }
    }
  }
}
