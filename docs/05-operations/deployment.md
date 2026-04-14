# 🚀 Deployment Guide

This guide describes the current deployment standard for Azure Naming. Infrastructure is provisioned from `environs-iac`, and application code is published from this repository. The repository also publishes its VS Code dev container image to Azure Container Registry for reusable development environments.

---

## ☁️ Prerequisites

* Access to the `environs-iac` repository
* Azure CLI installed and logged in
* Python 3.11 environment
* Access to Azure subscription and Entra ID
* Azure DevOps project access with permission to queue pipelines and manage pipeline variables

---

## 🧱 Standard Deployment Flow

Azure Naming is currently deployed by publishing application source to a provisioned Azure Function App. That remains the intended Azure deployment model.

### 1. Provision infrastructure from `environs-iac`

Use the Terraform stack at:

* `sanmar/applications/internal/azure-naming/service`

That stack provisions:

* the resource group
* the storage account and Azure Tables
* Log Analytics and Application Insights
* the Linux Function App and plan
* the Entra API application registration, service principal, and secret

The stack also sets the Function App application settings needed by the service, including `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AzureWebJobsStorage`, and deployment build settings.

### 2. Capture deployment outputs

The key outputs from Terraform are:

* `function_app_name`
* `function_app_default_hostname`
* `entra_app_client_id`
* `entra_tenant_id`
* `entra_app_client_secret` when needed for client flows

### 3. Configure the Azure DevOps pipeline

This repository publishes the Python application code through [azure-pipelines.yml](../../azure-pipelines.yml).

Create an Azure DevOps variable group named `azure-naming-shared` and set these non-secret values:

* `functionAppName = wus2-prd-fn-aznaming`
* `functionAppResourceGroup = wus2-prd-rg-aznaming`
* `functionAppSubscriptionId = cfe7cbd7-1b9d-4f5c-9459-57d72559d3f5`
* `acrSubscriptionId = a889bd72-26dd-49eb-8b8b-e874846ad155`
* `acrResourceGroup = wus2-prd-rg-iac-registry`
* `acrName = wus2prdcrsanmariac`
* `acrImageRepository = iac/naming/azure`

Set these secret variables either in the same variable group or directly on the pipeline:

* `azureServicePrincipalId`
* `azureServicePrincipalSecret`
* `azureTenantId`
* `acrServicePrincipalId` if ACR publishing uses a different principal
* `acrServicePrincipalSecret` if ACR publishing uses a different principal
* `acrTenantId` if ACR publishing uses a different tenant

The principal behind the deploy credentials must also be assigned the Azure Naming API's `admin` app role. The deployment stage requests a bearer token for the configured `AZURE_CLIENT_ID` and calls `POST /api/slug_sync` after every successful publish.

### 4. Publish the application code

The application code is deployed from this repository when the Azure DevOps `azure-naming` pipeline runs on pushes to `main`.

The pipeline:

* checks out the code
* installs dependencies
* runs tests
* logs into Azure with the configured service principal
* packages the repository for zip deployment
* publishes the package to the provisioned Function App
* resolves the Function App hostname and `AZURE_CLIENT_ID` from Azure
* requests an Entra bearer token for `api://<AZURE_CLIENT_ID>/.default`
* retries `POST /api/slug_sync` until the initial slug import succeeds or the deployment fails

### 5. Publish the dev container image

The same Azure DevOps pipeline publishes the dev container image.

Target registry settings:

* subscription: `a889bd72-26dd-49eb-8b8b-e874846ad155`
* resource group: `wus2-prd-rg-iac-registry`
* registry: `wus2prdcrsanmariac`
* repository path: `iac/naming/azure:<version>`

The pipeline behavior is:

* pushes to `main` publish `wus2prdcrsanmariac.azurecr.io/iac/naming/azure:latest`
* git tags like `v1.2.3` publish `wus2prdcrsanmariac.azurecr.io/iac/naming/azure:1.2.3`
* manual runs can override the image tag with the `devcontainerVersion` pipeline parameter

The pipeline uses Azure Container Registry build tasks, so the build agent only needs Azure login permissions and does not need a local Docker daemon.

Notes:

* the ACR credentials can reuse the main deploy principal if it has rights in both subscriptions
* otherwise configure separate `acrServicePrincipalId`, `acrServicePrincipalSecret`, and `acrTenantId` secrets
* the service principal must be able to select subscription `a889bd72-26dd-49eb-8b8b-e874846ad155`
* the service principal must have enough access to read `wus2prdcrsanmariac` and run `az acr build` against it
* a registry-scoped or resource-group-scoped role assignment is sufficient for the image publish stage; it does not need Function App deployment permissions

### Local container usage

The repository does include a VS Code dev container to standardize local Azure Functions development. The published ACR image is the same development environment packaged for reuse, but it is still not the production deployment artifact for the service.

For local setup and debugging in the dev container, see [../04-development/local-testing.md](../04-development/local-testing.md).

---

## 🔐 Entra ID Configuration

The Entra API registration is created during the Terraform apply in `environs-iac`. After provisioning, the remaining manual step is to assign users or groups to the generated `reader`, `contributor`, and `admin` app roles.

For testing-client setup and token acquisition, see [docs/02-getting-started/app-registration.md](../02-getting-started/app-registration.md).

---

## 🔁 Slug Sync Timer

The `slug_sync_timer` function runs weekly at **Sunday 4:00 AM UTC** to refresh the slug mappings from GitHub.

---

## 💻 Local Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
func start
```

Use tools like Postman or curl to hit endpoints using a valid Bearer token.

---

## 🧪 Post-Provision Verification

* Ensure the Function App exists and is reachable at the Terraform output hostname
* Ensure role-based access works with real Entra users or groups
* Confirm the Azure DevOps deploy stage's post-deploy slug sync step succeeds
* Use `POST /api/slug_sync` manually only for recovery or ad hoc refreshes
* Verify name claims and audits persist in the provisioned storage tables
