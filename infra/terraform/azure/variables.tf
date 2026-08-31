variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
  default     = "quanthire"
}

variable "environment" {
  description = "Environment name (dev, staging, production)"
  type        = string
  validation {
    condition     = contains(["dev", "staging", "production"], var.environment)
    error_message = "Environment must be dev, staging, or production."
  }
}

variable "location" {
  description = "Azure region for resources"
  type        = string
  default     = "qatarcentral"
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default = {
    Project     = "QuantHireAI"
    ManagedBy   = "Terraform"
    Contact     = "pradeep.kumar@malomatia.qa"
  }
}

# Network variables
variable "vnet_address_space" {
  description = "Address space for the virtual network"
  type        = list(string)
  default     = ["10.0.0.0/16"]
}

variable "subnet_prefixes" {
  description = "Address prefixes for subnets"
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24", "10.0.4.0/24"]
}

# AKS variables
variable "kubernetes_version" {
  description = "Kubernetes version"
  type        = string
  default     = "1.28"
}

variable "aks_node_count" {
  description = "Initial number of nodes in the AKS cluster"
  type        = number
  default     = 3
}

variable "aks_node_size" {
  description = "VM size for AKS nodes"
  type        = string
  default     = "Standard_D4s_v3"
}

variable "aks_enable_auto_scaling" {
  description = "Enable auto-scaling for AKS node pool"
  type        = bool
  default     = true
}

variable "aks_min_node_count" {
  description = "Minimum number of nodes when auto-scaling is enabled"
  type        = number
  default     = 2
}

variable "aks_max_node_count" {
  description = "Maximum number of nodes when auto-scaling is enabled"
  type        = number
  default     = 10
}

variable "enable_azure_ad_rbac" {
  description = "Enable Azure AD RBAC for AKS"
  type        = bool
  default     = true
}

variable "enable_monitoring" {
  description = "Enable monitoring for AKS"
  type        = bool
  default     = true
}

# PostgreSQL variables
variable "postgres_version" {
  description = "PostgreSQL version"
  type        = string
  default     = "16"
}

variable "postgres_sku" {
  description = "PostgreSQL SKU"
  type        = string
  default     = "GP_Standard_D4s_v3"
}

variable "postgres_storage_mb" {
  description = "PostgreSQL storage in MB"
  type        = number
  default     = 131072 # 128 GB
}

variable "postgres_backup_retention_days" {
  description = "Backup retention in days"
  type        = number
  default     = 30
}

variable "postgres_geo_redundant_backup" {
  description = "Enable geo-redundant backup"
  type        = bool
  default     = true
}

variable "postgres_admin_username" {
  description = "PostgreSQL admin username"
  type        = string
  default     = "quanthire_admin"
  sensitive   = true
}

variable "postgres_admin_password" {
  description = "PostgreSQL admin password"
  type        = string
  sensitive   = true
  default     = null # Will be auto-generated if not provided
}

variable "postgres_enable_high_availability" {
  description = "Enable high availability for PostgreSQL"
  type        = bool
  default     = false # Set to true for production
}

# Redis variables
variable "redis_capacity" {
  description = "Redis cache capacity (1, 2, 3, 4, 5, 6 for Premium)"
  type        = number
  default     = 2
}

variable "redis_family" {
  description = "Redis SKU family (C for Basic/Standard, P for Premium)"
  type        = string
  default     = "P"
}

variable "redis_sku" {
  description = "Redis SKU (Basic, Standard, Premium)"
  type        = string
  default     = "Premium"
}

# Storage variables
variable "storage_account_tier" {
  description = "Storage account tier (Standard or Premium)"
  type        = string
  default     = "Standard"
}

variable "storage_replication_type" {
  description = "Storage replication type (LRS, GRS, RAGRS, ZRS, GZRS, RAGZRS)"
  type        = string
  default     = "GRS"
}

variable "storage_enable_versioning" {
  description = "Enable blob versioning"
  type        = bool
  default     = true
}

variable "storage_enable_soft_delete" {
  description = "Enable soft delete for blobs"
  type        = bool
  default     = true
}

variable "storage_soft_delete_retention_days" {
  description = "Soft delete retention in days"
  type        = number
  default     = 30
}

variable "storage_enable_lifecycle" {
  description = "Enable lifecycle management"
  type        = bool
  default     = true
}

# Key Vault variables
variable "keyvault_soft_delete_retention_days" {
  description = "Soft delete retention for Key Vault"
  type        = number
  default     = 90
}

variable "keyvault_network_acls_default_action" {
  description = "Default action for Key Vault network ACLs"
  type        = string
  default     = "Deny"
}

variable "keyvault_allowed_ip_ranges" {
  description = "Allowed IP ranges for Key Vault access"
  type        = list(string)
  default     = []
}

# Monitoring variables
variable "log_analytics_retention_days" {
  description = "Log Analytics retention in days"
  type        = number
  default     = 30
}

# Container Registry variables
variable "acr_sku" {
  description = "Container Registry SKU (Basic, Standard, Premium)"
  type        = string
  default     = "Premium"
}

variable "acr_admin_enabled" {
  description = "Enable admin user for ACR"
  type        = bool
  default     = false
}

# Scale targets (for documentation and resource sizing)
variable "target_concurrent_recruiters" {
  description = "Target concurrent recruiters"
  type        = number
  default     = 200
}

variable "target_daily_candidate_uploads" {
  description = "Target daily candidate uploads"
  type        = number
  default     = 5000
}

variable "target_concurrent_candidates" {
  description = "Target concurrent candidates"
  type        = number
  default     = 2000
}

variable "target_expected_embeddings" {
  description = "Target expected embeddings"
  type        = number
  default     = 200000
}

variable "target_monthly_growth_pct" {
  description = "Target monthly growth percentage"
  type        = number
  default     = 15
}


