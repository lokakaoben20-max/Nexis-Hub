output "ids" {
  description = "Nom du secret -> identifiant (pour les variables des services Cloud Run)."
  value       = { for nom, secret in google_secret_manager_secret.secret : nom => secret.secret_id }
}
