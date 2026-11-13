variable "prefixe" {
  type = string
}

variable "region" {
  type = string
}

variable "domaine" {
  description = "Domaine public de l'environnement (sans https://), servi par Cloudflare."
  type        = string
}

variable "image_initiale" {
  description = "Image des premiers services (registre/nom@sha256:...). Vide tant qu'aucune image n'est publiée."
  type        = string
  default     = null
}

variable "comptes" {
  description = "Rôle -> compte de service (sortie `comptes` du module identites)."
  type        = map(string)
}

variable "compte_deploiement" {
  type = string
}

variable "secrets" {
  description = "Nom du secret -> identifiant (sortie `ids` du module secrets)."
  type        = map(string)
}

variable "reseau_id" {
  type = string
}

variable "sous_reseau_id" {
  type = string
}

variable "app_env" {
  description = "APP_ENV des processus : test ou production."
  type        = string
  validation {
    condition     = contains(["test", "production"], var.app_env)
    error_message = "APP_ENV hébergé : test ou production."
  }
}

variable "nom_bot_telegram" {
  description = "Nom du bot Telegram de l'environnement (@...)."
  type        = string
}

variable "reglages_argent" {
  description = "PAYMENT_GATEWAY, frais et seuils (voir nexis_config.py). Aucune valeur par défaut : chaque environnement les écrit."
  type        = map(string)
  validation {
    condition = alltrue([
      for nom in [
        "PAYMENT_GATEWAY", "COLLECTION_FEE_RATE", "PAYOUT_FEE_RATE",
        "PAYOUT_FEE_FIXED_USD", "PAYOUT_FEE_FIXED_CDF",
        "PAYOUT_MINIMUM_USD", "PAYOUT_MINIMUM_CDF",
        "PAYOUT_AUTO_LIMIT_USD", "PAYOUT_AUTO_LIMIT_CDF",
      ] : contains(keys(var.reglages_argent), nom)
    ])
    error_message = "Il manque un réglage d'argent (voir nexis_config.py)."
  }
}

variable "instances_min_backend" {
  description = "Instances toujours prêtes du backend (2 en production : deux zones)."
  type        = number
}

variable "instances_min_autres" {
  type = number
}

variable "instances_max" {
  type = number
}

variable "protection_suppression" {
  type = bool
}

variable "etiquettes" {
  type    = map(string)
  default = {}
}
