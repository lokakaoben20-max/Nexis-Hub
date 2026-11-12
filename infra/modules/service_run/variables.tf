variable "nom" {
  type = string
}

variable "role" {
  description = "Rôle passé à docker/lancer.sh (backend, bot, miniapp)."
  type        = string
}

variable "region" {
  type = string
}

variable "image" {
  type = string
}

variable "compte" {
  type = string
}

variable "reseau_id" {
  type = string
}

variable "sous_reseau_id" {
  type = string
}

variable "env" {
  type = map(string)
}

variable "env_secrets" {
  description = "Variable d'environnement -> identifiant du secret (dernière version)."
  type        = map(string)
}

variable "fichiers_secrets" {
  description = "Secrets montés comme fichiers : nom du volume -> { secret, dossier, fichier }."
  type = map(object({
    secret  = string
    dossier = string
    fichier = string
  }))
  default = {}
}

variable "instances_min" {
  type = number
}

variable "instances_max" {
  type = number
}

variable "cpu" {
  type    = string
  default = "1"
}

variable "memoire" {
  type    = string
  default = "512Mi"
}

variable "protection_suppression" {
  type = bool
}

variable "etiquettes" {
  type    = map(string)
  default = {}
}
