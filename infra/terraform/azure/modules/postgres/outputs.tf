output "server_id" {
  value = azurerm_postgresql_flexible_server.main.id
}

output "server_name" {
  value = azurerm_postgresql_flexible_server.main.name
}

output "server_fqdn" {
  value = azurerm_postgresql_flexible_server.main.fqdn
}

output "admin_username" {
  value     = azurerm_postgresql_flexible_server.main.administrator_login
  sensitive = true
}

output "admin_password" {
  value     = var.admin_password != null ? var.admin_password : random_password.postgres_admin[0].result
  sensitive = true
}

output "database_name" {
  value = azurerm_postgresql_flexible_server_database.main.name
}

output "connection_string" {
  value     = "postgresql://${azurerm_postgresql_flexible_server.main.administrator_login}:${var.admin_password != null ? var.admin_password : random_password.postgres_admin[0].result}@${azurerm_postgresql_flexible_server.main.fqdn}:5432/${azurerm_postgresql_flexible_server_database.main.name}?sslmode=require"
  sensitive = true
}


