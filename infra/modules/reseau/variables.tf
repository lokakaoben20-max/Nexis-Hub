variable "prefixe" {
  description = "Préfixe des noms de ressources (nexis-test, nexis-prod)."
  type        = string
}

variable "region" {
  description = "Région Google Cloud de l'environnement."
  type        = string
}

variable "plage_services" {
  description = "Plage d'adresses du sous-réseau des services Cloud Run (/24 au moins)."
  type        = string
  default     = "10.10.0.0/24"
}
