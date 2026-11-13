variable "region" {
  type = string
}

variable "acces" {
  description = "Nom du secret -> adresses des comptes de service qui peuvent le lire. Doit contenir REDIS_CA."
  type        = map(list(string))
  validation {
    condition     = contains(keys(var.acces), "REDIS_CA")
    error_message = "Le secret REDIS_CA (certificat de Redis) doit être déclaré."
  }
}

variable "certificat_ca_redis" {
  description = "Certificat public de l'autorité de Redis (sortie du module redis)."
  type        = string
}

variable "etiquettes" {
  type    = map(string)
  default = {}
}
