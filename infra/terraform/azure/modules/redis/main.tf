resource "azurerm_redis_cache" "main" {
  name                = "${var.project_name}-${var.environment}-redis"
  location            = var.location
  resource_group_name = var.resource_group_name
  capacity            = var.redis_capacity
  family              = var.redis_family
  sku_name            = var.redis_sku
  enable_non_ssl_port = var.enable_non_ssl_port
  minimum_tls_version = "1.3"
  subnet_id           = var.subnet_id
  
  redis_configuration {
    enable_authentication = true
    maxmemory_policy      = "allkeys-lru"
    maxmemory_reserved    = 50
    maxfragmentationmemory_reserved = 50
  }

  patch_schedule {
    day_of_week    = "Sunday"
    start_hour_utc = 2
  }

  tags = merge(var.tags, { Component = "Redis" })
}


