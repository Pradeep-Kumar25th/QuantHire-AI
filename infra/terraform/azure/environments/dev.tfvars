# Development Environment Configuration for QuantHireAI
# Apply with: terraform apply -var-file="environments/dev.tfvars"

project_name = "quanthire"
environment  = "dev"
location     = "eastus"  # Use cheaper region for dev

tags = {
  Project     = "QuantHireAI"
  Environment = "Development"
  ManagedBy   = "Terraform"
  Owner       = "pradeep.kumar@malomatia.qa"
  AutoShutdown = "true"  # Can be shut down at night
}

# Network Configuration
vnet_address_space = ["10.2.0.0/16"]
subnet_prefixes    = ["10.2.1.0/24", "10.2.2.0/24", "10.2.3.0/24", "10.2.4.0/24"]

# AKS Configuration (Minimal)
kubernetes_version      = "1.28"
aks_node_count          = 2
aks_node_size           = "Standard_D2s_v3"
aks_enable_auto_scaling = false
aks_min_node_count      = 1
aks_max_node_count      = 3
enable_azure_ad_rbac    = false  # Simpler auth for dev
enable_monitoring       = false  # Cost savings

# PostgreSQL Configuration
postgres_version                 = "16"
postgres_sku                     = "B_Standard_B2s"  # Burstable, cost-effective
postgres_storage_mb              = 32768  # 32 GB
postgres_backup_retention_days   = 7
postgres_geo_redundant_backup    = false
postgres_admin_username          = "quanthire_admin"
postgres_enable_high_availability = false

# Redis Configuration
redis_capacity = 1
redis_family   = "C"   # Basic tier for dev
redis_sku      = "Basic"

# Storage Configuration
storage_account_tier             = "Standard"
storage_replication_type         = "LRS"
storage_enable_versioning        = false
storage_enable_soft_delete       = false
storage_soft_delete_retention_days = 7
storage_enable_lifecycle         = false

# Key Vault Configuration
keyvault_soft_delete_retention_days  = 7
keyvault_network_acls_default_action = "Allow"
keyvault_allowed_ip_ranges           = []

# Monitoring Configuration
log_analytics_retention_days = 7

# Container Registry
acr_sku           = "Basic"
acr_admin_enabled = true  # Easier for dev

# Scale Targets
target_concurrent_recruiters    = 10
target_daily_candidate_uploads  = 100
target_concurrent_candidates    = 50
target_expected_embeddings      = 10000
target_monthly_growth_pct       = 0












