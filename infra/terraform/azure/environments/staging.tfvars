# Staging Environment Configuration for QuantHireAI
# Apply with: terraform apply -var-file="environments/staging.tfvars"

project_name = "quanthire"
environment  = "staging"
location     = "qatarcentral"

tags = {
  Project     = "QuantHireAI"
  Environment = "Staging"
  ManagedBy   = "Terraform"
  Owner       = "pradeep.kumar@malomatia.qa"
  Purpose     = "Pre-production testing"
}

# Network Configuration
vnet_address_space = ["10.1.0.0/16"]
subnet_prefixes    = ["10.1.1.0/24", "10.1.2.0/24", "10.1.3.0/24", "10.1.4.0/24"]

# AKS Configuration (Smaller footprint)
kubernetes_version      = "1.28"
aks_node_count          = 2
aks_node_size           = "Standard_D2s_v3"  # 2 vCPU, 8 GB RAM
aks_enable_auto_scaling = true
aks_min_node_count      = 2
aks_max_node_count      = 5
enable_azure_ad_rbac    = true
enable_monitoring       = true

# PostgreSQL Configuration
postgres_version                 = "16"
postgres_sku                     = "GP_Standard_D2s_v3"  # 2 vCPU, 8 GB RAM
postgres_storage_mb              = 65536  # 64 GB
postgres_backup_retention_days   = 7
postgres_geo_redundant_backup    = false
postgres_admin_username          = "quanthire_admin"
postgres_enable_high_availability = false

# Redis Configuration
redis_capacity = 1     # 6 GB cache (Premium P1)
redis_family   = "P"
redis_sku      = "Premium"

# Storage Configuration
storage_account_tier             = "Standard"
storage_replication_type         = "LRS"  # Local redundancy
storage_enable_versioning        = true
storage_enable_soft_delete       = true
storage_soft_delete_retention_days = 14
storage_enable_lifecycle         = true

# Key Vault Configuration
keyvault_soft_delete_retention_days  = 7
keyvault_network_acls_default_action = "Allow"  # More permissive for testing
keyvault_allowed_ip_ranges           = []

# Monitoring Configuration
log_analytics_retention_days = 30

# Container Registry
acr_sku           = "Standard"
acr_admin_enabled = false

# Scale Targets
target_concurrent_recruiters    = 50
target_daily_candidate_uploads  = 1000
target_concurrent_candidates    = 500
target_expected_embeddings      = 50000
target_monthly_growth_pct       = 15












