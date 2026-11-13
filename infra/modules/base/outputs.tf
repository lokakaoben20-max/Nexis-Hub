output "instance" {
  value = google_sql_database_instance.postgres.name
}

output "ip_privee" {
  description = "Adresse privée de Postgres, pour composer DATABASE_URL."
  value       = google_sql_database_instance.postgres.private_ip_address
}

output "base" {
  value = google_sql_database.nexis.name
}
