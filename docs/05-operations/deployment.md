# 🚀 Deployment Guide

This guide describes the current deployment standard for Azure Naming. Infrastructure is provisioned from `environs-iac`, and application code is published from this repository. The repository also publishes its VS Code dev container image to Azure Container Registry for reusable development environments.

---

## ☁️ Prerequisites

* Access to the `environs-iac` repository
* Azure CLI installed and logged in
* Python 3.11 environment
* Access to Azure subscription and Entra ID
* GitHub repository secrets or OIDC configuration for the deploy workflow

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

### 3. Configure the application publish path

This repository publishes the Python application code through [deploy.yml](../../.github/workflows/deploy.yml).

The workflow currently expects:

* `AZURE_CREDENTIALS` for `azure/login`
* `AZURE_FUNCTIONAPP_NAME` matching the Terraform output `function_app_name`

### 4. Publish the application code

The application code is deployed from this repository when the deploy workflow runs on pushes to `main`.

The workflow:

* checks out the code
* installs dependencies
* runs tests
* logs into Azure
* publishes the repository root to the provisioned Function App

### 5. Publish the dev container image

The repository now publishes the dev container image with [devcontainer-publish.yml](../../.github/workflows/devcontainer-publish.yml).

Target registry settings:

* subscription: `a889bd72-26dd-49eb-8b8b-e874846ad155`
* resource group: `wus2-prd-rg-iac-registry`
* registry: `wus2prdcrsanmariac`
* repository path: `iac/naming/azure:<version>`

The workflow behavior is:

* pushes to `main` publish `wus2prdcrsanmariac.azurecr.io/iac/naming/azure:latest`
* git tags like `v1.2.3` publish `wus2prdcrsanmariac.azurecr.io/iac/naming/azure:1.2.3`
* manual runs can publish any explicit `version` value

The workflow uses Azure Container Registry build tasks, so GitHub Actions only needs Azure login permissions and does not need a local Docker daemon.

Use a dedicated GitHub Actions secret named `AZURE_ACR_CREDENTIALS` for this workflow. Do not reuse `AZURE_CREDENTIALS`, because that secret is also used by the Function App deployment workflow and may point at a different subscription.

Verified secret payload shape for `AZURE_ACR_CREDENTIALS`:

```json
{
	"clientId": "<service-principal-app-id>",
	"clientSecret": "<service-principal-password>",
	"subscriptionId": "a889bd72-26dd-49eb-8b8b-e874846ad155",
	"tenantId": "<entra-tenant-id>"
}
```

Notes:

* all values are strings
* the service principal must be able to select subscription `a889bd72-26dd-49eb-8b8b-e874846ad155`
* the service principal must have enough access to read `wus2prdcrsanmariac` and run `az acr build` against it
* a registry-scoped or resource-group-scoped role assignment is sufficient for this workflow; it does not need Function App deployment permissions

Verification reference:

* successful manual publish of `wus2prdcrsanmariac.azurecr.io/iac/naming/azure:0.1.0`: `https://github.com/gedefili/azure-naming/actions/runs/24159607753`

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
* Test slug updates manually with `POST /api/slug_sync`
* Verify name claims and audits persist in the provisioned storage tables
