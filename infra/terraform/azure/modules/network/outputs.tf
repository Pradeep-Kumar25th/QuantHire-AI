output "vnet_id" {
  description = "Virtual network ID"
  value       = azurerm_virtual_network.main.id
}

output "vnet_name" {
  description = "Virtual network name"
  value       = azurerm_virtual_network.main.name
}

output "aks_subnet_id" {
  description = "AKS subnet ID"
  value       = azurerm_subnet.aks.id
}

output "postgres_subnet_id" {
  description = "PostgreSQL subnet ID"
  value       = azurerm_subnet.postgres.id
}

output "redis_subnet_id" {
  description = "Redis subnet ID"
  value       = azurerm_subnet.redis.id
}

output "private_endpoints_subnet_id" {
  description = "Private endpoints subnet ID"
  value       = azurerm_subnet.private_endpoints.id
}

output "postgres_private_dns_zone_id" {
  description = "PostgreSQL private DNS zone ID"
  value       = azurerm_private_dns_zone.postgres.id
}


