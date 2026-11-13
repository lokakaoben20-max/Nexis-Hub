variable "prefixe" {
  type = string
}

variable "region" {
  type = string
}

variable "domaine" {
  type = string
}

variable "services" {
  description = "Rôle -> nom du service Cloud Run ; doit contenir backend, bot et miniapp."
  type        = map(string)
  validation {
    condition     = alltrue([for role in ["backend", "bot", "miniapp"] : contains(keys(var.services), role)])
    error_message = "Les services backend, bot et miniapp sont attendus."
  }
}

variable "plages_cloudflare" {
  description = "Contenu de infra/cloudflare_ips.json."
  type = object({
    ipv4 = list(string)
    ipv6 = list(string)
  })
}
