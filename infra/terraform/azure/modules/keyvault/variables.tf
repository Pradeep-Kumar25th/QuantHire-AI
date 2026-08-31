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

variable "tenant_id" {
  type = string
}

variable "aks_principal_id" {
  type = string
}

variable "enable_rbac_authorization" {
  type = bool
}

variable "enable_soft_delete" {
  type = bool
}

variable "soft_delete_retention_days" {
  type = number
}

variable "enable_purge_protection" {
  type = bool
}

variable "network_acls_default_action" {
  type = string
}

variable "allowed_ip_ranges" {
  type = list(string)
}

variable "tags" {
  type = map(string)
}












