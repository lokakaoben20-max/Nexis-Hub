variable "prefixe" {
  type = string
}

variable "region" {
  type = string
}

variable "reseau_id" {
  type = string
}

variable "haute_disponibilite" {
  type = bool
}

variable "memoire_go" {
  type    = number
  default = 1
}

variable "etiquettes" {
  type    = map(string)
  default = {}
}
