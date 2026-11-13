output "registre" {
  description = "Adresse du registre d'images (région-docker.pkg.dev/projet/dépôt)."
  value       = "${var.region}-docker.pkg.dev/${google_artifact_registry_repository.images.project}/${google_artifact_registry_repository.images.repository_id}"
}

output "services" {
  description = "Rôle -> nom du service Cloud Run (vide avant le premier déploiement)."
  value = local.deploye ? {
    backend = module.backend[0].nom
    miniapp = module.miniapp[0].nom
    bot     = module.bot[0].nom
  } : {}
}

output "job_taches" {
  value = local.deploye ? google_cloud_run_v2_job.job["taches"].name : null
}

output "deploye" {
  value = local.deploye
}
