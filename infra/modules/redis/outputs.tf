output "hote" {
  value = google_redis_instance.redis.host
}

output "port" {
  # 6378 avec TLS.
  value = google_redis_instance.redis.port
}

output "certificat_ca" {
  description = "Certificat (public) de l'autorité qui signe le certificat TLS de Redis."
  value       = google_redis_instance.redis.server_ca_certs[0].cert
}
