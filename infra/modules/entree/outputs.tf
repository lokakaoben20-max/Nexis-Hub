output "ip" {
  description = "Adresse du répartiteur : enregistrement A du domaine chez Cloudflare (proxy activé)."
  value       = google_compute_global_address.entree.address
}

output "dns_validation_certificat" {
  description = "Enregistrement CNAME à créer chez Cloudflare (sans proxy) pour valider le certificat."
  value = {
    nom    = google_certificate_manager_dns_authorization.domaine.dns_resource_record[0].name
    type   = google_certificate_manager_dns_authorization.domaine.dns_resource_record[0].type
    valeur = google_certificate_manager_dns_authorization.domaine.dns_resource_record[0].data
  }
}
