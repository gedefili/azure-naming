locals {
  name_prefix = "${var.project_name}-${var.environment}"
  default_tags = merge(var.tags, {
    project     = var.project_name
    environment = var.environment
    managed_by  = "terraform"
  })
}

# ---------------------------------------------------------------------------
# Resource Group
# ---------------------------------------------------------------------------
resource "azurerm_resource_group" "main" {
  name     = "${local.name_prefix}-rg"
  location = var.location
  tags     = local.default_tags
}

# ---------------------------------------------------------------------------
# Storage Account + Tables
# ---------------------------------------------------------------------------
resource "azurerm_storage_account" "main" {
  name                          = var.storage_account_name
  resource_group_name           = azurerm_resource_group.main.name
  location                      = azurerm_resource_group.main.location
  account_tier                  = "Standard"
  account_replication_type      = "LRS"
  min_tls_version               = "TLS1_2"
  public_network_access_enabled = false

  network_rules {
    default_action = "Deny"
    bypass         = ["AzureServices"]
  }

  tags = local.default_tags
}

resource "azurerm_storage_table" "claimed_names" {
  name                 = "ClaimedNames"
  storage_account_name = azurerm_storage_account.main.name
}

resource "azurerm_storage_table" "audit_logs" {
  name                 = "AuditLogs"
  storage_account_name = azurerm_storage_account.main.name
}

resource "azurerm_storage_table" "slug_mappings" {
  name                 = "SlugMappings"
  storage_account_name = azurerm_storage_account.main.name
}

# ---------------------------------------------------------------------------
# Log Analytics + Application Insights
# ---------------------------------------------------------------------------
resource "azurerm_log_analytics_workspace" "main" {
  name                = "${local.name_prefix}-law"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = "PerGB2018"
  retention_in_days   = 30
  tags                = local.default_tags
}

resource "azurerm_application_insights" "main" {
  name                = "${local.name_prefix}-appinsights"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  workspace_id        = azurerm_log_analytics_workspace.main.id
  application_type    = "web"
  tags                = local.default_tags
}

# ---------------------------------------------------------------------------
# Function App (Consumption Plan, Linux, Python)
# ---------------------------------------------------------------------------
resource "azurerm_service_plan" "main" {
  name                = "${local.name_prefix}-plan"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  os_type             = "Linux"
  sku_name            = "Y1" # Consumption plan
  tags                = local.default_tags
}

resource "azurerm_linux_function_app" "main" {
  name                       = "${local.name_prefix}-fn"
  resource_group_name        = azurerm_resource_group.main.name
  location                   = azurerm_resource_group.main.location
  service_plan_id            = azurerm_service_plan.main.id
  storage_account_name       = azurerm_storage_account.main.name
  storage_uses_managed_identity = true
  https_only                 = true

  tags = local.default_tags

  site_config {
    application_stack {
      python_version = var.python_version
    }

    ftps_state = "Disabled"
  }

  app_settings = {
    "FUNCTIONS_WORKER_RUNTIME"       = "python"
    "APPINSIGHTS_INSTRUMENTATIONKEY" = azurerm_application_insights.main.instrumentation_key
    "APPLICATIONINSIGHTS_CONNECTION_STRING" = azurerm_application_insights.main.connection_string
    "AZURE_CLIENT_ID"                = azuread_application.main.client_id
    "AZURE_TENANT_ID"                = data.azuread_client_config.current.tenant_id
  }

  identity {
    type = "SystemAssigned"
  }
}

# Grant the Function App's managed identity access to the storage account
resource "azurerm_role_assignment" "func_storage_blob" {
  scope                = azurerm_storage_account.main.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_linux_function_app.main.identity[0].principal_id
}

resource "azurerm_role_assignment" "func_storage_table" {
  scope                = azurerm_storage_account.main.id
  role_definition_name = "Storage Table Data Contributor"
  principal_id         = azurerm_linux_function_app.main.identity[0].principal_id
}
