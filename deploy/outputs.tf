# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------

output "resource_group_name" {
  description = "Name of the resource group."
  value       = azurerm_resource_group.main.name
}

output "function_app_name" {
  description = "Name of the deployed Function App."
  value       = azurerm_linux_function_app.main.name
}

output "function_app_default_hostname" {
  description = "Default hostname of the Function App."
  value       = azurerm_linux_function_app.main.default_hostname
}

output "storage_account_name" {
  description = "Name of the Storage Account."
  value       = azurerm_storage_account.main.name
}

output "application_insights_name" {
  description = "Name of the Application Insights resource."
  value       = azurerm_application_insights.main.name
}

output "application_insights_instrumentation_key" {
  description = "Instrumentation key for Application Insights."
  value       = azurerm_application_insights.main.instrumentation_key
  sensitive   = true
}

output "entra_app_client_id" {
  description = "Client (Application) ID of the Entra App Registration."
  value       = azuread_application.main.client_id
}

output "entra_tenant_id" {
  description = "Entra ID Tenant ID."
  value       = data.azuread_client_config.current.tenant_id
}
