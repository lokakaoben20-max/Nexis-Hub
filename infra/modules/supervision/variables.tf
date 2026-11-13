variable "projet" {
  type = string
}

variable "prefixe" {
  type = string
}

variable "domaine" {
  type = string
}

variable "services_deployes" {
  description = "Vrai une fois les services créés : les sondes n'ont de sens qu'après."
  type        = bool
}

variable "email_alertes" {
  type = string
}

variable "compte_facturation" {
  description = "Identifiant du compte de facturation (XXXXXX-XXXXXX-XXXXXX)."
  type        = string
}

variable "budget_mensuel_usd" {
  type = number
}
