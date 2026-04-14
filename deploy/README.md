# Azure Naming Service — Infrastructure as Code

Terraform configuration that provisions all Azure resources required by the Naming Service.

## Resources Created

| Resource | Purpose |
|----------|---------|
| Resource Group | Container for all resources |
| Storage Account (Standard LRS) | Function App backing store + Table Storage |
| Storage Tables | `ClaimedNames`, `AuditLogs`, `SlugMappings` |
| App Service Plan (Consumption/Y1) | Serverless hosting for the Function App |
| Linux Function App (Python 3.11) | Hosts the API |
| Log Analytics Workspace | Backing store for Application Insights |
| Application Insights | Monitoring and alerting |
| Entra ID App Registration | OAuth 2.0 auth with 3 app roles (reader, contributor, admin) |
| Entra Service Principal | Enterprise app for role assignment |
| Entra App Password | Client secret for token validation |

## Prerequisites

- [Terraform >= 1.5](https://developer.hashicorp.com/terraform/install)
- Azure CLI authenticated (`az login`)
- Permissions to create resources and Entra ID app registrations

## Quick Start

```bash
cd deploy

# Copy and edit variables
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your values (especially storage_account_name)

# Initialize
terraform init

# Preview changes
terraform plan

# Apply
terraform apply
```

## Deploy Application Code

After `terraform apply`, deploy the Function App code using the existing GitHub Actions workflow or manually:

```bash
cd ..
func azure functionapp publish $(terraform -chdir=deploy output -raw function_app_name)
```

## Remote State (Recommended for Teams)

Uncomment and configure the backend block in `providers.tf` to store state in Azure Blob Storage:

```hcl
backend "azurerm" {
  resource_group_name  = "terraform-state-rg"
  storage_account_name = "tfstateXXXXX"
  container_name       = "tfstate"
  key                  = "naming-service.tfstate"
}
```

## Sensitive Outputs

```bash
# View the Entra client secret
terraform output -raw entra_app_client_secret

# View the App Insights instrumentation key
terraform output -raw application_insights_instrumentation_key
```

## File Layout

| File | Contents |
|------|----------|
| `providers.tf` | Provider versions, backend configuration |
| `variables.tf` | Input variables with validation |
| `main.tf` | Resource Group, Storage, Function App, App Insights |
| `entra.tf` | Entra ID App Registration, roles, service principal |
| `outputs.tf` | Key resource identifiers and secrets |
| `terraform.tfvars.example` | Example variable values |
