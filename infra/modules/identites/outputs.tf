output "comptes" {
  description = "Rôle -> adresse du compte de service (backend, bot, miniapp, taches, migration)."
  value       = { for role, compte in google_service_account.execution : role => compte.email }
}

output "planificateur" {
  value = google_service_account.planificateur.email
}

output "deploiement" {
  value = google_service_account.deploiement.email
}

output "acces_secrets" {
  description = "Secret -> adresses des comptes qui peuvent le lire (entrée du module secrets)."
  value = {
    for secret, roles in local.lectures_secrets :
    secret => [for role in roles : google_service_account.execution[role].email]
  }
}
