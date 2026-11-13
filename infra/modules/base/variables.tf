variable "prefixe" {
  type = string
}

variable "region" {
  type = string
}

variable "reseau_id" {
  type = string
}

variable "tier" {
  description = "Taille de la machine Cloud SQL (ex. db-custom-1-3840 en test, db-custom-2-7680 en prod)."
  type        = string
}

variable "haute_disponibilite" {
  description = "Vrai : instance régionale avec bascule automatique (production)."
  type        = bool
}

variable "disque_go" {
  type    = number
  default = 20
}

variable "jours_pitr" {
  description = "Jours de restauration à la minute près."
  type        = number
  default     = 7
  validation {
    condition     = var.jours_pitr >= 1 && var.jours_pitr <= 7
    error_message = "Cloud SQL Enterprise garde de 1 à 7 jours de journaux."
  }
}

variable "sauvegardes_conservees" {
  description = "Nombre de sauvegardes quotidiennes gardées."
  type        = number
  default     = 30
}

variable "heure_sauvegarde_utc" {
  type    = string
  default = "01:00"
}

variable "protection_suppression" {
  type    = bool
  default = true
}

variable "etiquettes" {
  type    = map(string)
  default = {}
}
