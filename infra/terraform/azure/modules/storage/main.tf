resource "azurerm_storage_account" "main" {
  name                     = "${var.project_name}${var.environment}storage"
  resource_group_name      = var.resource_group_name
  location                 = var.location
  account_tier             = var.account_tier
  account_replication_type = var.account_replication_type
  account_kind             = "StorageV2"
  min_tls_version          = "TLS1_3"
  enable_https_traffic_only = true

  blob_properties {
    versioning_enabled = var.enable_versioning
    
    dynamic "delete_retention_policy" {
      for_each = var.enable_soft_delete ? [1] : []
      content {
        days = var.soft_delete_retention_days
      }
    }

    dynamic "container_delete_retention_policy" {
      for_each = var.enable_soft_delete ? [1] : []
      content {
        days = var.soft_delete_retention_days
      }
    }
  }

  network_rules {
    default_action = "Deny"
    bypass         = ["AzureServices"]
  }

  tags = merge(var.tags, { Component = "Storage" })
}

# Containers
resource "azurerm_storage_container" "uploads" {
  name                  = "uploads"
  storage_account_name  = azurerm_storage_account.main.name
  container_access_type = "private"
}

resource "azurerm_storage_container" "resumes" {
  name                  = "resumes"
  storage_account_name  = azurerm_storage_account.main.name
  container_access_type = "private"
}

resource "azurerm_storage_container" "assessments" {
  name                  = "assessments"
  storage_account_name  = azurerm_storage_account.main.name
  container_access_type = "private"
}

resource "azurerm_storage_container" "backups" {
  name                  = "backups"
  storage_account_name  = azurerm_storage_account.main.name
  container_access_type = "private"
}

# Lifecycle management
resource "azurerm_storage_management_policy" "main" {
  count = var.enable_lifecycle_management ? 1 : 0

  storage_account_id = azurerm_storage_account.main.id

  rule {
    name    = "delete-old-uploads"
    enabled = true

    filters {
      prefix_match = ["uploads/"]
      blob_types   = ["blockBlob"]
    }

    actions {
      base_blob {
        delete_after_days_since_modification_greater_than = 90
      }
    }
  }

  rule {
    name    = "archive-old-resumes"
    enabled = true

    filters {
      prefix_match = ["resumes/"]
      blob_types   = ["blockBlob"]
    }

    actions {
      base_blob {
        tier_to_cool_after_days_since_modification_greater_than    = 30
        tier_to_archive_after_days_since_modification_greater_than = 365
        delete_after_days_since_modification_greater_than          = 730
      }
    }
  }
}


