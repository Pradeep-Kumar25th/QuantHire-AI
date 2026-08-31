output "storage_account_id" {
  value = azurerm_storage_account.main.id
}

output "storage_account_name" {
  value = azurerm_storage_account.main.name
}

output "primary_blob_endpoint" {
  value = azurerm_storage_account.main.primary_blob_endpoint
}

output "primary_connection_string" {
  value     = azurerm_storage_account.main.primary_connection_string
  sensitive = true
}

output "container_names" {
  value = [
    azurerm_storage_container.uploads.name,
    azurerm_storage_container.resumes.name,
    azurerm_storage_container.assessments.name,
    azurerm_storage_container.backups.name,
  ]
}












