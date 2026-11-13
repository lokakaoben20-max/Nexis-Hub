variable "projet" {
  type = string
}

variable "prefixe" {
  type = string
}

variable "region" {
  description = "Région du Job `taches`."
  type        = string
}

variable "region_planificateur" {
  description = "Région de Cloud Scheduler (la même si Cloud Scheduler y est disponible)."
  type        = string
}

variable "job" {
  description = "Nom du Cloud Run Job des tâches."
  type        = string
}

variable "compte_planificateur" {
  type = string
}

variable "calendrier" {
  description = "Nom de la tâche -> expression cron UTC (contenu de infra/calendrier.json)."
  type        = map(string)
}
