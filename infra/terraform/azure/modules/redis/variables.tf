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

variable "subnet_id" {
  type = string
}

variable "redis_capacity" {
  type = number
}

variable "redis_family" {
  type = string
}

variable "redis_sku" {
  type = string
}

variable "enable_non_ssl_port" {
  type = bool
}

variable "tags" {
  type = map(string)
}


