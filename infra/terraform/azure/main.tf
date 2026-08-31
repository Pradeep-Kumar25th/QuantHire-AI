terraform {
  required_version = ">= 1.6.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.80"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.24"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.12"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  # Remote state backend (uncomment for production)
  # backend "azurerm" {
  #   resource_group_name  = "quanthire-terraform-rg"
  #   storage_account_name = "quanthireterraform"
  #   container_name       = "tfstate"
  #   key                  = "production.terraform.tfstate"
  # }
}

provider "azurerm" {
  features {
    key_vault {
      purge_soft_delete_on_destroy    = false
      recover_soft_deleted_key_vaults = true
    }
    resource_group {
      prevent_deletion_if_contains_resources = true
    }
  }
}

# Data sources
data "azurerm_client_config" "current" {}

# Resource Group
resource "azurerm_resource_group" "main" {
  name     = "${var.project_name}-${var.environment}-rg"
  location = var.location
  tags     = merge(var.tags, { Component = "ResourceGroup" })
}

# Network Module
module "network" {
  source = "./modules/network"

  project_name        = var.project_name
  environment         = var.environment
  location            = var.location
  resource_group_name = azurerm_resource_group.main.name
  vnet_address_space  = var.vnet_address_space
  subnet_prefixes     = var.subnet_prefixes
  tags                = var.tags
}

# AKS Module
module "aks" {
  source = "./modules/aks"

  project_name               = var.project_name
  environment                = var.environment
  location                   = var.location
  resource_group_name        = azurerm_resource_group.main.name
  vnet_subnet_id             = module.network.aks_subnet_id
  kubernetes_version         = var.kubernetes_version
  node_count                 = var.aks_node_count
  node_size                  = var.aks_node_size
  enable_auto_scaling        = var.aks_enable_auto_scaling
  min_node_count             = var.aks_min_node_count
  max_node_count             = var.aks_max_node_count
  enable_azure_ad_rbac       = var.enable_azure_ad_rbac
  enable_monitoring          = var.enable_monitoring
  tags                       = var.tags

  depends_on = [module.network]
}

# PostgreSQL Module
module "postgres" {
  source = "./modules/postgres"

  project_name              = var.project_name
  environment               = var.environment
  location                  = var.location
  resource_group_name       = azurerm_resource_group.main.name
  delegated_subnet_id       = module.network.postgres_subnet_id
  private_dns_zone_id       = module.network.postgres_private_dns_zone_id
  postgres_version          = var.postgres_version
  postgres_sku              = var.postgres_sku
  storage_mb                = var.postgres_storage_mb
  backup_retention_days     = var.postgres_backup_retention_days
  geo_redundant_backup      = var.postgres_geo_redundant_backup
  admin_username            = var.postgres_admin_username
  admin_password            = var.postgres_admin_password
  enable_high_availability  = var.postgres_enable_high_availability
  tags                      = var.tags

  depends_on = [module.network]
}

# Redis Module
module "redis" {
  source = "./modules/redis"

  project_name        = var.project_name
  environment         = var.environment
  location            = var.location
  resource_group_name = azurerm_resource_group.main.name
  subnet_id           = module.network.redis_subnet_id
  redis_capacity      = var.redis_capacity
  redis_family        = var.redis_family
  redis_sku           = var.redis_sku
  enable_non_ssl_port = false
  tags                = var.tags

  depends_on = [module.network]
}

# Storage Module
module "storage" {
  source = "./modules/storage"

  project_name                  = var.project_name
  environment                   = var.environment
  location                      = var.location
  resource_group_name           = azurerm_resource_group.main.name
  account_tier                  = var.storage_account_tier
  account_replication_type      = var.storage_replication_type
  enable_versioning             = var.storage_enable_versioning
  enable_soft_delete            = var.storage_enable_soft_delete
  soft_delete_retention_days    = var.storage_soft_delete_retention_days
  enable_lifecycle_management   = var.storage_enable_lifecycle
  tags                          = var.tags
}

# Key Vault Module
module "keyvault" {
  source = "./modules/keyvault"

  project_name               = var.project_name
  environment                = var.environment
  location                   = var.location
  resource_group_name        = azurerm_resource_group.main.name
  tenant_id                  = data.azurerm_client_config.current.tenant_id
  aks_principal_id           = module.aks.kubelet_identity_object_id
  enable_rbac_authorization  = true
  enable_soft_delete         = true
  soft_delete_retention_days = var.keyvault_soft_delete_retention_days
  enable_purge_protection    = var.environment == "production" ? true : false
  network_acls_default_action = var.keyvault_network_acls_default_action
  allowed_ip_ranges          = var.keyvault_allowed_ip_ranges
  tags                       = var.tags

  depends_on = [module.aks]
}

# Monitoring Module (Application Insights + Log Analytics)
module "monitoring" {
  source = "./modules/monitoring"

  project_name        = var.project_name
  environment         = var.environment
  location            = var.location
  resource_group_name = azurerm_resource_group.main.name
  aks_cluster_id      = module.aks.cluster_id
  retention_days      = var.log_analytics_retention_days
  tags                = var.tags

  depends_on = [module.aks]
}

# Container Registry Module
module "acr" {
  source = "./modules/acr"

  project_name        = var.project_name
  environment         = var.environment
  location            = var.location
  resource_group_name = azurerm_resource_group.main.name
  sku                 = var.acr_sku
  admin_enabled       = var.acr_admin_enabled
  aks_principal_id    = module.aks.kubelet_identity_object_id
  tags                = var.tags

  depends_on = [module.aks]
}

# Create secrets in Key Vault
resource "azurerm_key_vault_secret" "postgres_connection_string" {
  name         = "postgres-connection-string"
  value        = module.postgres.connection_string
  key_vault_id = module.keyvault.key_vault_id

  depends_on = [module.keyvault]
}

resource "azurerm_key_vault_secret" "redis_connection_string" {
  name         = "redis-connection-string"
  value        = module.redis.primary_connection_string
  key_vault_id = module.keyvault.key_vault_id

  depends_on = [module.keyvault]
}

resource "azurerm_key_vault_secret" "storage_connection_string" {
  name         = "storage-connection-string"
  value        = module.storage.primary_connection_string
  key_vault_id = module.keyvault.key_vault_id

  depends_on = [module.keyvault]
}

# Random string for generating secrets
resource "random_password" "jwt_secret" {
  length  = 32
  special = true
}

resource "azurerm_key_vault_secret" "jwt_secret" {
  name         = "jwt-secret"
  value        = random_password.jwt_secret.result
  key_vault_id = module.keyvault.key_vault_id

  depends_on = [module.keyvault]
}

resource "random_password" "nextauth_secret" {
  length  = 32
  special = true
}

resource "azurerm_key_vault_secret" "nextauth_secret" {
  name         = "nextauth-secret"
  value        = random_password.nextauth_secret.result
  key_vault_id = module.keyvault.key_vault_id

  depends_on = [module.keyvault]
}


