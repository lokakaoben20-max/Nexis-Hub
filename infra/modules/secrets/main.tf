# Secret Manager : déclarations seulement.
#
# Terraform crée chaque secret (vide) et dit qui peut le lire. Les VALEURS ne
# passent jamais par Terraform ni par Git : Ben les dépose avec une commande par
# secret (infra/README.md, « Déposer les secrets »). Seule exception : le
# certificat public de l'autorité de Redis, qui n'est pas un secret.
#
# Copies gardées dans la région de l'environnement seulement.

resource "google_secret_manager_secret" "secret" {
  for_each  = var.acces
  secret_id = each.key
  labels    = var.etiquettes

  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }
}

locals {
  lectures = merge([
    for secret, comptes in var.acces : {
      for compte in comptes : "${secret}/${compte}" => { secret = secret, compte = compte }
    }
  ]...)
}

resource "google_secret_manager_secret_iam_member" "lecture" {
  for_each  = local.lectures
  secret_id = google_secret_manager_secret.secret[each.value.secret].id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${each.value.compte}"
}

resource "google_secret_manager_secret_version" "redis_ca" {
  secret      = google_secret_manager_secret.secret["REDIS_CA"].id
  secret_data = var.certificat_ca_redis
}
