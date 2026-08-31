resource "random_password" "postgres_admin" {
  count   = var.admin_password == null ? 1 : 0
  length  = 32
  special = true
}

resource "azurerm_postgresql_flexible_server" "main" {
  name                   = "${var.project_name}-${var.environment}-postgres"
  location               = var.location
  resource_group_name    = var.resource_group_name
  version                = var.postgres_version
  delegated_subnet_id    = var.delegated_subnet_id
  private_dns_zone_id    = var.private_dns_zone_id
  administrator_login    = var.admin_username
  administrator_password = var.admin_password != null ? var.admin_password : random_password.postgres_admin[0].result
  zone                   = "1"
  storage_mb             = var.storage_mb
  sku_name               = var.postgres_sku
  backup_retention_days  = var.backup_retention_days
  geo_redundant_backup_enabled = var.geo_redundant_backup

  dynamic "high_availability" {
    for_each = var.enable_high_availability ? [1] : []
    content {
      mode                      = "ZoneRedundant"
      standby_availability_zone = "2"
    }
  }

  maintenance_window {
    day_of_week  = 0
    start_hour   = 2
    start_minute = 0
  }

  tags = merge(var.tags, { Component = "PostgreSQL" })

  depends_on = [var.private_dns_zone_id]
}

# Create database
resource "azurerm_postgresql_flexible_server_database" "main" {
  name      = "${var.project_name}_db"
  server_id = azurerm_postgresql_flexible_server.main.id
  collation = "en_US.utf8"
  charset   = "utf8"
}

# Enable pgvector extension
resource "azurerm_postgresql_flexible_server_configuration" "pgvector" {
  name      = "azure.extensions"
  server_id = azurerm_postgresql_flexible_server.main.id
  value     = "PGVECTOR,UUID-OSSP,CITEXT"
}

# Performance and security configurations
resource "azurerm_postgresql_flexible_server_configuration" "ssl_enforcement" {
  name      = "ssl_min_protocol_version"
  server_id = azurerm_postgresql_flexible_server.main.id
  value     = "TLSv1.3"
}

resource "azurerm_postgresql_flexible_server_configuration" "connection_throttle" {
  name      = "connection_throttle.enable"
  server_id = azurerm_postgresql_flexible_server.main.id
  value     = "on"
}

resource "azurerm_postgresql_flexible_server_configuration" "log_checkpoints" {
  name      = "log_checkpoints"
  server_id = azurerm_postgresql_flexible_server.main.id
  value     = "on"
}

resource "azurerm_postgresql_flexible_server_configuration" "log_connections" {
  name      = "log_connections"
  server_id = azurerm_postgresql_flexible_server.main.id
  value     = "on"
}

resource "azurerm_postgresql_flexible_server_configuration" "log_disconnections" {
  name      = "log_disconnections"
  server_id = azurerm_postgresql_flexible_server.main.id
  value     = "on"
}


