resource "azurerm_container_registry" "main" {
  name                = "${var.project_name}${var.environment}acr"
  resource_group_name = var.resource_group_name
  location            = var.location
  sku                 = var.sku
  admin_enabled       = var.admin_enabled

  dynamic "georeplications" {
    for_each = var.sku == "Premium" && var.environment == "production" ? [1] : []
    content {
      location                = "eastus"
      zone_redundancy_enabled = true
      tags                    = var.tags
    }
  }

  network_rule_set {
    default_action = "Deny"
  }

  tags = merge(var.tags, { Component = "ContainerRegistry" })
}

# Role assignment for AKS to pull images
resource "azurerm_role_assignment" "aks_acr_pull" {
  scope                = azurerm_container_registry.main.id
  role_definition_name = "AcrPull"
  principal_id         = var.aks_principal_id
}












