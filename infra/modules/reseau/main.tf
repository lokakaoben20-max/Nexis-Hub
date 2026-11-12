# Réseau privé de l'environnement.
#
# - Un VPC sans sous-réseaux automatiques et un sous-réseau dans la région.
#   Les services Cloud Run y sortent directement (sortie VPC directe, sans
#   connecteur).
# - Accès privé aux services Google (Cloud SQL, Memorystore) par appairage :
#   la base et Redis n'ont aucune adresse publique.
# - Cloud NAT avec une adresse IP réservée : tout appel sortant (agrégateur
#   Mobile Money, Telegram, Meta) part de cette adresse fixe, que l'agrégateur
#   peut mettre sur sa liste autorisée.

resource "google_compute_network" "vpc" {
  name                    = "${var.prefixe}-vpc"
  auto_create_subnetworks = false
  routing_mode            = "REGIONAL"
}

resource "google_compute_subnetwork" "services" {
  name                     = "${var.prefixe}-services"
  region                   = var.region
  network                  = google_compute_network.vpc.id
  ip_cidr_range            = var.plage_services
  private_ip_google_access = true

  log_config {
    aggregation_interval = "INTERVAL_5_MIN"
    flow_sampling        = 0.5
    metadata             = "INCLUDE_ALL_METADATA"
  }
}

# Plage réservée aux services gérés par Google (Cloud SQL, Memorystore).
resource "google_compute_global_address" "services_google" {
  name          = "${var.prefixe}-services-google"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.vpc.id
}

resource "google_service_networking_connection" "services_google" {
  network                 = google_compute_network.vpc.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.services_google.name]
}

resource "google_compute_address" "sortie" {
  name         = "${var.prefixe}-ip-sortie"
  region       = var.region
  address_type = "EXTERNAL"
  network_tier = "PREMIUM"
}

resource "google_compute_router" "sortie" {
  name    = "${var.prefixe}-routeur"
  region  = var.region
  network = google_compute_network.vpc.id
}

resource "google_compute_router_nat" "sortie" {
  name                               = "${var.prefixe}-nat"
  router                             = google_compute_router.sortie.name
  region                             = var.region
  nat_ip_allocate_option             = "MANUAL_ONLY"
  nat_ips                            = [google_compute_address.sortie.self_link]
  source_subnetwork_ip_ranges_to_nat = "LIST_OF_SUBNETWORKS"

  subnetwork {
    name                    = google_compute_subnetwork.services.id
    source_ip_ranges_to_nat = ["ALL_IP_RANGES"]
  }

  log_config {
    enable = true
    filter = "ERRORS_ONLY"
  }
}
