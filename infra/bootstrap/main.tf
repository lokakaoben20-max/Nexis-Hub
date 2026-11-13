# Amorçage, appliqué UNE FOIS par Ben à la main (infra/README.md) avant tout
# le reste. État local, qui ne contient aucun secret :
#
# - les buckets d'état Terraform (versionnés, accès limité) ;
# - le pool Workload Identity Federation pour GitHub : la CI s'identifie par
#   un jeton de quelques minutes, sans clé Google à stocker ;
# - le registre d'images (créé ici pour que la CI puisse publier avant les
#   services).
#
# Le projet Google Cloud lui-même est créé à la main (console), pour que la
# facturation et l'organisation restent sous contrôle de Ben.

terraform {
  required_version = ">= 1.9"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 8.10"
    }
  }
}

variable "projet" {
  type = string
}

variable "region" {
  type = string
}

data "google_project" "projet" {
  project_id = var.projet
}

resource "google_storage_bucket" "etat" {
  #checkov:skip=CKV_GCP_62:Journaux d'accès du bucket d'état non activés : à décider (suivi dans infra/README.md, « Limites connues »).
  for_each                    = toset(["test", "prod"])
  name                        = "nexis-tfstate-${each.key}"
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false

  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition {
      num_newer_versions = 30
      with_state         = "ARCHIVED"
    }
    action {
      type = "Delete"
    }
  }
}

resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "github"
  display_name              = "GitHub Actions (Nexis Hub)"
  disabled                  = false
}

resource "google_iam_workload_identity_pool_provider" "github" {
  #checkov:skip=CKV_GCP_125:La confiance est limitée au seul dépôt (attribute_condition). L'environnement GitHub est vérifié au niveau des droits (attribute.depot_env dans modules/identites), pas ici.
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "depot"
  display_name                       = "Dépôt lokakaoben20-max/Nexis-Hub"

  attribute_mapping = {
    "google.subject"      = "assertion.sub"
    "attribute.depot"     = "assertion.repository"
    "attribute.depot_env" = "assertion.environment"
    "attribute.ref"       = "assertion.ref"
  }

  # Seul ce dépôt peut emprunter une identité ici.
  attribute_condition = "assertion.repository == 'lokakaoben20-max/Nexis-Hub'"

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

output "pool_identite_github" {
  description = "À reporter dans environnements/*/main.tf (pool_identite_github)."
  value       = "projects/${data.google_project.projet.number}/locations/global/workloadIdentityPools/${google_iam_workload_identity_pool.github.workload_identity_pool_id}"
}

output "fournisseur_identite_github" {
  description = "Pour l'action google-github-actions/auth (workload_identity_provider)."
  value       = "${google_iam_workload_identity_pool.github.name}/providers/${google_iam_workload_identity_pool_provider.github.workload_identity_pool_provider_id}"
}
