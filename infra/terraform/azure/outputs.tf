output "resource_group_name" {
  description = "Resource group name"
  value       = azurerm_resource_group.main.name
}

output "location" {
  description = "Azure region"
  value       = azurerm_resource_group.main.location
}

# Network outputs
output "vnet_id" {
  description = "Virtual network ID"
  value       = module.network.vnet_id
}

output "vnet_name" {
  description = "Virtual network name"
  value       = module.network.vnet_name
}

# AKS outputs
output "aks_cluster_name" {
  description = "AKS cluster name"
  value       = module.aks.cluster_name
}

output "aks_cluster_id" {
  description = "AKS cluster ID"
  value       = module.aks.cluster_id
}

output "aks_kubeconfig_command" {
  description = "Command to get kubeconfig"
  value       = "az aks get-credentials --resource-group ${azurerm_resource_group.main.name} --name ${module.aks.cluster_name}"
}

output "aks_cluster_fqdn" {
  description = "AKS cluster FQDN"
  value       = module.aks.cluster_fqdn
}

# PostgreSQL outputs
output "postgres_fqdn" {
  description = "PostgreSQL server FQDN"
  value       = module.postgres.server_fqdn
}

output "postgres_server_name" {
  description = "PostgreSQL server name"
  value       = module.postgres.server_name
}

output "postgres_admin_username" {
  description = "PostgreSQL admin username"
  value       = module.postgres.admin_username
  sensitive   = true
}

output "postgres_database_name" {
  description = "PostgreSQL database name"
  value       = module.postgres.database_name
}

# Redis outputs
output "redis_hostname" {
  description = "Redis cache hostname"
  value       = module.redis.hostname
}

output "redis_ssl_port" {
  description = "Redis SSL port"
  value       = module.redis.ssl_port
}

output "redis_name" {
  description = "Redis cache name"
  value       = module.redis.name
}

# Storage outputs
output "storage_account_name" {
  description = "Storage account name"
  value       = module.storage.storage_account_name
}

output "storage_primary_blob_endpoint" {
  description = "Primary blob endpoint"
  value       = module.storage.primary_blob_endpoint
}

output "storage_container_names" {
  description = "Storage container names"
  value       = module.storage.container_names
}

# Key Vault outputs
output "keyvault_id" {
  description = "Key Vault ID"
  value       = module.keyvault.key_vault_id
}

output "keyvault_uri" {
  description = "Key Vault URI"
  value       = module.keyvault.key_vault_uri
}

output "keyvault_name" {
  description = "Key Vault name"
  value       = module.keyvault.key_vault_name
}

# Monitoring outputs
output "log_analytics_workspace_id" {
  description = "Log Analytics workspace ID"
  value       = module.monitoring.workspace_id
}

output "application_insights_instrumentation_key" {
  description = "Application Insights instrumentation key"
  value       = module.monitoring.instrumentation_key
  sensitive   = true
}

output "application_insights_connection_string" {
  description = "Application Insights connection string"
  value       = module.monitoring.connection_string
  sensitive   = true
}

# Container Registry outputs
output "acr_login_server" {
  description = "Container registry login server"
  value       = module.acr.login_server
}

output "acr_name" {
  description = "Container registry name"
  value       = module.acr.name
}

# Connection strings (stored in Key Vault)
output "connection_strings_info" {
  description = "Information about connection strings stored in Key Vault"
  value = {
    postgres_secret_name = "postgres-connection-string"
    redis_secret_name    = "redis-connection-string"
    storage_secret_name  = "storage-connection-string"
    jwt_secret_name      = "jwt-secret"
    nextauth_secret_name = "nextauth-secret"
    keyvault_uri         = module.keyvault.key_vault_uri
  }
}

# Quick start information
output "quick_start" {
  description = "Quick start commands"
  value = <<-EOT
    # 1. Get AKS credentials
    ${output.aks_kubeconfig_command.value}
    
    # 2. Verify cluster access
    kubectl cluster-info
    
    # 3. Install external-secrets operator
    helm repo add external-secrets https://charts.external-secrets.io
    helm install external-secrets external-secrets/external-secrets -n external-secrets --create-namespace
    
    # 4. Deploy application
    cd ../../../infra/kubernetes/helm
    helm install quanthire ./quanthire -f values-${var.environment}.yaml
    
    # 5. Get Key Vault secrets
    az keyvault secret list --vault-name ${module.keyvault.key_vault_name}
    
    # 6. Connect to PostgreSQL
    psql "host=${module.postgres.server_fqdn} port=5432 dbname=${module.postgres.database_name} user=${module.postgres.admin_username} sslmode=require"
    
    # 7. Container registry login
    az acr login --name ${module.acr.name}
  EOT
}

# Cost estimation
output "estimated_monthly_cost_usd" {
  description = "Estimated monthly cost in USD (approximate)"
  value = {
    aks     = "500-800"
    postgres = "300-500"
    redis   = "150-250"
    storage = "50-100"
    keyvault = "5-10"
    monitoring = "50-100"
    acr     = "20-40"
    total   = "1075-1800"
    note    = "Costs vary based on usage and region. Enable detailed billing in Azure Cost Management."
  }
}


