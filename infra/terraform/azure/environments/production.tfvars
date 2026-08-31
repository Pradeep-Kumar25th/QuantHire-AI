# Production Environment Configuration for QuantHireAI
# Apply with: terraform apply -var-file="environments/production.tfvars"

project_name = "quanthire"
environment  = "production"
location     = "qatarcentral"  # Qatar data residency requirement

tags = {
  Project     = "QuantHireAI"
  Environment = "Production"
  ManagedBy   = "Terraform"
  Owner       = "pradeep.kumar@malomatia.qa"
  Contact     = "pradeep.kumar@malomatia.qa"
  DataClass   = "Confidential"
  Compliance  = "GDPR"
}

# Network Configuration
vnet_address_space = ["10.0.0.0/16"]
subnet_prefixes    = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24", "10.0.4.0/24"]

# AKS Configuration (Sized for 200 concurrent recruiters, 5000 daily uploads)
kubernetes_version      = "1.28"
aks_node_count          = 5
aks_node_size           = "Standard_D4s_v3"  # 4 vCPU, 16 GB RAM
aks_enable_auto_scaling = true
aks_min_node_count      = 3
aks_max_node_count      = 15  # Handles 15% monthly growth
enable_azure_ad_rbac    = true
enable_monitoring       = true

# PostgreSQL Configuration (Sized for 200K embeddings + growth)
postgres_version                 = "16"
postgres_sku                     = "GP_Standard_D4s_v3"  # 4 vCPU, 16 GB RAM
postgres_storage_mb              = 262144  # 256 GB
postgres_backup_retention_days   = 30
postgres_geo_redundant_backup    = true
postgres_admin_username          = "quanthire_admin"
postgres_enable_high_availability = true  # Zone-redundant HA

# Redis Configuration
redis_capacity = 2     # 6 GB cache
redis_family   = "P"   # Premium tier (persistence + VNet)
redis_sku      = "Premium"

# Storage Configuration
storage_account_tier             = "Standard"
storage_replication_type         = "GRS"  # Geo-redundant
storage_enable_versioning        = true
storage_enable_soft_delete       = true
storage_soft_delete_retention_days = 30
storage_enable_lifecycle         = true

# Key Vault Configuration
keyvault_soft_delete_retention_days  = 90
keyvault_network_acls_default_action = "Deny"
keyvault_allowed_ip_ranges           = []  # Configure with office/VPN IPs

# Monitoring Configuration
log_analytics_retention_days = 90  # Compliance requirement

# Container Registry
acr_sku           = "Premium"  # Geo-replication + enhanced security
acr_admin_enabled = false      # Use managed identity

# Scale Targets (for documentation)
target_concurrent_recruiters    = 200
target_daily_candidate_uploads  = 5000
target_concurrent_candidates    = 2000
target_expected_embeddings      = 200000
target_monthly_growth_pct       = 15












