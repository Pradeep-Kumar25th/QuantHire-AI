variable "project_name" {
  type = string
}

variable "environment" {
  type = string
}

variable "location" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "delegated_subnet_id" {
  type = string
}

variable "private_dns_zone_id" {
  type = string
}

variable "postgres_version" {
  type = string
}

variable "postgres_sku" {
  type = string
}

variable "storage_mb" {
  type = number
}

variable "backup_retention_days" {
  type = number
}

variable "geo_redundant_backup" {
  type = bool
}

variable "admin_username" {
  type = string
}

variable "admin_password" {
  type      = string
  sensitive = true
  default   = null
}

variable "enable_high_availability" {
  type = bool
}

variable "tags" {
  type = map(string)
}


