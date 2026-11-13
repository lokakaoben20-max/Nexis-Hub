variable "projet" {
  type = string
}

variable "prefixe" {
  description = "Préfixe des comptes (6 à 18 caractères : le nom complet ne doit pas dépasser 30)."
  type        = string
  validation {
    condition     = length(var.prefixe) <= 16
    error_message = "Préfixe trop long pour les noms de comptes de service (30 caractères au plus)."
  }
}

variable "pool_identite_github" {
  description = "Nom complet du pool Workload Identity créé par infra/bootstrap (projects/<numéro>/locations/global/workloadIdentityPools/github)."
  type        = string
}

variable "depot_github" {
  description = "Dépôt autorisé à déployer, sous la forme propriétaire/nom."
  type        = string
}

variable "environnement_github" {
  description = "Environnement GitHub (Settings > Environments) dont les travaux peuvent déployer ici."
  type        = string
}
