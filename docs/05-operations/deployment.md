# 🚀 Deployment Guide

This guide describes the current deployment standard for Azure Naming. Infrastructure is provisioned from `environs-iac`, and application code is published from this repository. Containers are used here for local development only through the VS Code dev container workflow.

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

### Local container usage

The repository does include a VS Code dev container, but that is intended only to standardize local Azure Functions development. It is not the production deployment artifact for the service.

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
