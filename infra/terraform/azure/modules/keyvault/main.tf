data "azurerm_client_config" "current" {}

resource "azurerm_key_vault" "main" {
  name                        = "${var.project_name}-${var.environment}-kv"
  location                    = var.location
  resource_group_name         = var.resource_group_name
  tenant_id                   = var.tenant_id
  sku_name                    = "premium"
  soft_delete_retention_days  = var.soft_delete_retention_days
  purge_protection_enabled    = var.enable_purge_protection
  enable_rbac_authorization   = var.enable_rbac_authorization
  enabled_for_deployment      = true
  enabled_for_disk_encryption = true
  enabled_for_template_deployment = true

  network_acls {
    default_action = var.network_acls_default_action
    bypass         = "AzureServices"
    ip_rules       = var.allowed_ip_ranges
  }

  tags = merge(var.tags, { Component = "KeyVault" })
}

# Role assignment for AKS managed identity
resource "azurerm_role_assignment" "aks_keyvault_secrets_user" {
  scope                = azurerm_key_vault.main.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = var.aks_principal_id
}

# Role assignment for current deployment identity
resource "azurerm_role_assignment" "deployment_keyvault_admin" {
  scope                = azurerm_key_vault.main.id
  role_definition_name = "Key Vault Administrator"
  principal_id         = data.azurerm_client_config.current.object_id
}












