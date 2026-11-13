output "reseau_id" {
  value = google_compute_network.vpc.id
}

output "sous_reseau_id" {
  value = google_compute_subnetwork.services.id
}

output "ip_sortie" {
  description = "Adresse IP fixe des appels sortants, à déclarer chez l'agrégateur."
  value       = google_compute_address.sortie.address
}
