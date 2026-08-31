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

variable "vnet_subnet_id" {
  type = string
}

variable "kubernetes_version" {
  type = string
}

variable "node_count" {
  type = number
}

variable "node_size" {
  type = string
}

variable "enable_auto_scaling" {
  type = bool
}

variable "min_node_count" {
  type = number
}

variable "max_node_count" {
  type = number
}

variable "enable_azure_ad_rbac" {
  type = bool
}

variable "enable_monitoring" {
  type = bool
}

variable "log_analytics_workspace_id" {
  type    = string
  default = null
}

variable "tags" {
  type = map(string)
}


