# Environnement de test : mêmes modules que la production, tailles réduites,
# sans haute disponibilité, paiement simulé. Rien n'est créé tant que Ben ne
# lance pas `apply` (lot 5, avec son accord).

terraform {
  backend "gcs" {
    bucket = "nexis-tfstate-test"
    prefix = "infra/test"
  }
}

provider "google" {
  project = var.projet
  region  = var.region
}

variable "projet" {
  description = "Projet Google Cloud de test (sans organisation jusqu'à l'achat du domaine payant)."
  type        = string
}

variable "region" {
  description = "africa-south1 (Johannesburg) ou europe-west4, selon la mesure depuis Kinshasa."
  type        = string
}

variable "domaine" {
  description = "Domaine de test (nexishub.dpdns.org aujourd'hui)."
  type        = string
}

variable "image_initiale" {
  type    = string
  default = null
}

variable "email_alertes" {
  type = string
}

variable "compte_facturation" {
  type = string
}

variable "pool_identite_github" {
  type = string
}

variable "admin_telegram_id" {
  description = "Identifiant Telegram numérique de l'administrateur (test)."
  type        = string
}

variable "plages_cloudflare" {
  type = object({ ipv4 = list(string), ipv6 = list(string) })
}

locals {
  prefixe    = "nexis-test"
  etiquettes = { environnement = "test", projet = "nexis-hub" }
  calendrier = jsondecode(file("${path.module}/../../calendrier.json"))
}

module "reseau" {
  source  = "../../modules/reseau"
  prefixe = local.prefixe
  region  = var.region
}

module "base" {
  source                 = "../../modules/base"
  prefixe                = local.prefixe
  region                 = var.region
  reseau_id              = module.reseau.reseau_id
  tier                   = "db-custom-1-3840"
  haute_disponibilite    = false
  disque_go              = 10
  jours_pitr             = 7
  protection_suppression = true
  etiquettes             = local.etiquettes
}

module "redis" {
  source              = "../../modules/redis"
  prefixe             = local.prefixe
  region              = var.region
  reseau_id           = module.reseau.reseau_id
  haute_disponibilite = false
  memoire_go          = 1
  etiquettes          = local.etiquettes
}

module "identites" {
  source               = "../../modules/identites"
  projet               = var.projet
  prefixe              = local.prefixe
  pool_identite_github = var.pool_identite_github
  depot_github         = "lokakaoben20-max/Nexis-Hub"
  environnement_github = "test"
}

module "secrets" {
  source              = "../../modules/secrets"
  region              = var.region
  certificat_ca_redis = module.redis.certificat_ca
  acces               = module.identites.acces_secrets
  etiquettes          = local.etiquettes
}

module "services" {
  source = "../../modules/services"

  prefixe            = local.prefixe
  region             = var.region
  domaine            = var.domaine
  image_initiale     = var.image_initiale
  comptes            = module.identites.comptes
  compte_deploiement = module.identites.deploiement
  secrets            = module.secrets.ids
  reseau_id          = module.reseau.reseau_id
  sous_reseau_id     = module.reseau.sous_reseau_id

  app_env           = "test"
  admin_telegram_id = var.admin_telegram_id
  nom_bot_telegram  = "@NexisHubTestBot"

  reglages_argent = {
    PAYMENT_GATEWAY       = "simulation"
    COLLECTION_FEE_RATE   = "0.025"
    PAYOUT_FEE_RATE       = "0.02"
    PAYOUT_FEE_FIXED_USD  = "1"
    PAYOUT_FEE_FIXED_CDF  = "2500"
    PAYOUT_MINIMUM_USD    = "5"
    PAYOUT_MINIMUM_CDF    = "12500"
    PAYOUT_AUTO_LIMIT_USD = "100"
    PAYOUT_AUTO_LIMIT_CDF = "250000"
  }

  instances_min_backend  = 0
  instances_min_autres   = 0
  instances_max          = 2
  protection_suppression = true
  etiquettes             = local.etiquettes
}

module "entree" {
  source            = "../../modules/entree"
  prefixe           = local.prefixe
  region            = var.region
  domaine           = var.domaine
  services          = module.services.services
  plages_cloudflare = var.plages_cloudflare
}

module "planification" {
  source               = "../../modules/planification"
  projet               = var.projet
  prefixe              = local.prefixe
  region               = var.region
  region_planificateur = var.region
  job                  = module.services.job_taches
  compte_planificateur = module.identites.planificateur
  calendrier           = local.calendrier
}

module "supervision" {
  source             = "../../modules/supervision"
  projet             = var.projet
  prefixe            = local.prefixe
  domaine            = var.domaine
  services_deployes  = module.services.deploye
  email_alertes      = var.email_alertes
  compte_facturation = var.compte_facturation
  budget_mensuel_usd = 100
}

output "ip_entree" {
  value = module.entree.ip
}

output "validation_certificat" {
  value = module.entree.dns_validation_certificat
}

output "ip_sortie_agregateur" {
  description = "IP fixe des appels sortants : à déclarer chez l'agrégateur (bac à sable)."
  value       = module.reseau.ip_sortie
}

output "registre_images" {
  value = module.services.registre
}
