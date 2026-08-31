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

variable "account_tier" {
  type = string
}

variable "account_replication_type" {
  type = string
}

variable "enable_versioning" {
  type = bool
}

variable "enable_soft_delete" {
  type = bool
}

variable "soft_delete_retention_days" {
  type = number
}

variable "enable_lifecycle_management" {
  type = bool
}

variable "tags" {
  type = map(string)
}


