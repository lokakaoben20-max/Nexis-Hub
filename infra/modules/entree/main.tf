# Entrée publique : répartiteur de charge HTTPS de Google devant les trois
# services, derrière Cloudflare.
#
# - Certificat géré par Google, validé par un enregistrement DNS (fonctionne
#   même derrière le proxy Cloudflare). Rien de secret dans Terraform.
# - Cloud Armor : seules les adresses de Cloudflare passent (infra/cloudflare_ips.json),
#   tout le reste reçoit 403. Personne ne contourne donc le pare-feu de Cloudflare.
# - Routes : /api/app/* et /api/payments/webhook/* vers le backend, /webhook
#   vers le bot, tout le reste vers la Mini App. Les routes /api/bot/* du
#   backend ne sont PAS publiées ici (elles restent sur le réseau privé).
# - /sante/backend et /sante/bot : `/health/ready` de chaque service, pour les
#   sondes de la supervision.

locals {
  # Cloud Armor : 10 plages au plus par règle.
  plages = concat(var.plages_cloudflare.ipv4, var.plages_cloudflare.ipv6)
  groupes_plages = [
    for i in range(0, length(local.plages), 10) : slice(local.plages, i, min(i + 10, length(local.plages)))
  ]
}

resource "google_compute_global_address" "entree" {
  name = "${var.prefixe}-entree"
}

resource "google_certificate_manager_dns_authorization" "domaine" {
  name   = "${var.prefixe}-domaine"
  domain = var.domaine
}

resource "google_certificate_manager_certificate" "domaine" {
  name = "${var.prefixe}-domaine"
  managed {
    domains            = [var.domaine]
    dns_authorizations = [google_certificate_manager_dns_authorization.domaine.id]
  }
}

resource "google_certificate_manager_certificate_map" "entree" {
  name = "${var.prefixe}-entree"
}

resource "google_certificate_manager_certificate_map_entry" "domaine" {
  name         = "${var.prefixe}-domaine"
  map          = google_certificate_manager_certificate_map.entree.name
  hostname     = var.domaine
  certificates = [google_certificate_manager_certificate.domaine.id]
}

resource "google_compute_security_policy" "cloudflare" {
  name        = "${var.prefixe}-cloudflare-seulement"
  description = "Seul Cloudflare peut joindre le répartiteur."
  type        = "CLOUD_ARMOR"

  dynamic "rule" {
    for_each = local.groupes_plages
    content {
      action      = "allow"
      priority    = 1000 + rule.key
      description = "Plages Cloudflare (${rule.key + 1}/${length(local.groupes_plages)})"
      match {
        versioned_expr = "SRC_IPS_V1"
        config {
          src_ip_ranges = rule.value
        }
      }
    }
  }

  # Règle WAF préconfigurée contre les tentatives d'exécution de code à
  # distance type Log4j : elle passe avant les règles d'autorisation.
  rule {
    action      = "deny(403)"
    priority    = 900
    description = "WAF : tentatives Log4j (CVE-2021-44228)"
    match {
      expr {
        expression = "evaluatePreconfiguredExpr('cve-canary')"
      }
    }
  }

  rule {
    action      = "deny(403)"
    priority    = 2147483647
    description = "Tout le reste"
    match {
      versioned_expr = "SRC_IPS_V1"
      config {
        src_ip_ranges = ["*"]
      }
    }
  }
}

resource "google_compute_region_network_endpoint_group" "service" {
  for_each              = var.services
  name                  = "${var.prefixe}-${each.key}"
  region                = var.region
  network_endpoint_type = "SERVERLESS"
  cloud_run {
    service = each.value
  }
}

resource "google_compute_backend_service" "service" {
  for_each              = var.services
  name                  = "${var.prefixe}-${each.key}"
  protocol              = "HTTPS"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  security_policy       = google_compute_security_policy.cloudflare.id

  backend {
    group = google_compute_region_network_endpoint_group.service[each.key].id
  }

  log_config {
    enable      = true
    sample_rate = 1
  }
}

resource "google_compute_url_map" "entree" {
  name            = "${var.prefixe}-entree"
  default_service = google_compute_backend_service.service["miniapp"].id

  host_rule {
    hosts        = [var.domaine]
    path_matcher = "nexis"
  }

  path_matcher {
    name            = "nexis"
    default_service = google_compute_backend_service.service["miniapp"].id

    path_rule {
      paths   = ["/api/app/*", "/api/payments/webhook/*"]
      service = google_compute_backend_service.service["backend"].id
    }

    path_rule {
      paths   = ["/webhook"]
      service = google_compute_backend_service.service["bot"].id
    }

    path_rule {
      paths   = ["/sante/backend"]
      service = google_compute_backend_service.service["backend"].id
      route_action {
        url_rewrite {
          path_prefix_rewrite = "/health/ready"
        }
      }
    }

    path_rule {
      paths   = ["/sante/bot"]
      service = google_compute_backend_service.service["bot"].id
      route_action {
        url_rewrite {
          path_prefix_rewrite = "/health/ready"
        }
      }
    }
  }
}

resource "google_compute_ssl_policy" "moderne" {
  name            = "${var.prefixe}-tls"
  profile         = "MODERN"
  min_tls_version = "TLS_1_2"
}

resource "google_compute_target_https_proxy" "entree" {
  name            = "${var.prefixe}-entree"
  url_map         = google_compute_url_map.entree.id
  certificate_map = "//certificatemanager.googleapis.com/${google_certificate_manager_certificate_map.entree.id}"
  ssl_policy      = google_compute_ssl_policy.moderne.id
}

resource "google_compute_global_forwarding_rule" "https" {
  name                  = "${var.prefixe}-https"
  target                = google_compute_target_https_proxy.entree.id
  ip_address            = google_compute_global_address.entree.address
  port_range            = "443"
  ip_protocol           = "TCP"
  load_balancing_scheme = "EXTERNAL_MANAGED"
}
