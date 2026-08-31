resource "azurerm_kubernetes_cluster" "main" {
  name                = "${var.project_name}-${var.environment}-aks"
  location            = var.location
  resource_group_name = var.resource_group_name
  dns_prefix          = "${var.project_name}-${var.environment}"
  kubernetes_version  = var.kubernetes_version
  
  automatic_channel_upgrade = "stable"
  node_resource_group       = "${var.resource_group_name}-nodes"
  
  default_node_pool {
    name                = "system"
    node_count          = var.node_count
    vm_size             = var.node_size
    vnet_subnet_id      = var.vnet_subnet_id
    enable_auto_scaling = var.enable_auto_scaling
    min_count           = var.enable_auto_scaling ? var.min_node_count : null
    max_count           = var.enable_auto_scaling ? var.max_node_count : null
    os_disk_size_gb     = 100
    type                = "VirtualMachineScaleSets"
    
    upgrade_settings {
      max_surge = "33%"
    }
    
    tags = merge(var.tags, { NodePool = "System" })
  }

  identity {
    type = "SystemAssigned"
  }

  network_profile {
    network_plugin    = "azure"
    network_policy    = "azure"
    load_balancer_sku = "standard"
    service_cidr      = "10.1.0.0/16"
    dns_service_ip    = "10.1.0.10"
  }

  dynamic "azure_active_directory_role_based_access_control" {
    for_each = var.enable_azure_ad_rbac ? [1] : []
    content {
      managed                = true
      azure_rbac_enabled     = true
    }
  }

  dynamic "oms_agent" {
    for_each = var.enable_monitoring ? [1] : []
    content {
      log_analytics_workspace_id = var.log_analytics_workspace_id
    }
  }

  key_vault_secrets_provider {
    secret_rotation_enabled  = true
    secret_rotation_interval = "2m"
  }

  tags = merge(var.tags, { Component = "AKS" })
}

# User node pool for application workloads
resource "azurerm_kubernetes_cluster_node_pool" "user" {
  name                  = "user"
  kubernetes_cluster_id = azurerm_kubernetes_cluster.main.id
  vm_size               = var.node_size
  node_count            = var.node_count
  enable_auto_scaling   = var.enable_auto_scaling
  min_count             = var.enable_auto_scaling ? var.min_node_count : null
  max_count             = var.enable_auto_scaling ? var.max_node_count : null
  vnet_subnet_id        = var.vnet_subnet_id
  
  node_labels = {
    "workload" = "application"
  }

  node_taints = []

  upgrade_settings {
    max_surge = "33%"
  }

  tags = merge(var.tags, { NodePool = "User" })
}


