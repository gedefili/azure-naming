# 🚀 Deployment Guide

This guide walks through the deployment of the Azure Naming Function to Azure using Function Apps, Table Storage, and Entra ID authentication.

---

## ☁️ Prerequisites

* Azure CLI installed and logged in
* Python 3.10+ environment
* `func` Azure Functions Core Tools installed
* Access to Azure subscription and Entra ID

---

## 🧱 Resources to Provision

### Azure Resources

* **Resource Group** (if not using existing):

  ```bash
  az group create -n naming-fn-rg -l westus2
  ```
* **Storage Account** (for Function and Tables):

  ```bash
  az storage account create -n namingstorage123 -g naming-fn-rg --sku Standard_LRS
  ```
* **Function App** (Python 3.10 + Linux):

  ```bash
  az functionapp create -n naming-fn-app -g naming-fn-rg \
    --storage-account namingstorage123 \
    --consumption-plan-location westus2 \
    --runtime python --runtime-version 3.10 --functions-version 4 \
    --os-type Linux
  ```

### Azure Tables

Use Azure Storage Explorer or CLI to create the following tables in the same storage account:

* `ClaimedNames`
* `AuditLogs`
* `SlugMappings`

---

## 🔐 Entra ID Configuration

### App Registration

* Register a new app in Entra ID
* Expose an API with scopes (e.g., `user_access`, `admin_access`)
* Assign app roles: `reader`, `contributor`, `admin`
* Add users/groups to roles using Enterprise Applications → Users and Groups

### Set App Settings

On the Function App:

* `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_CLIENT_SECRET`
* `STORAGE_CONNECTION_STRING`
* (Optional) GitHub URL override for slug sync

---

## 🔁 Slug Sync Timer

The `slug_sync_timer` function runs weekly at **Sunday 4:00 AM UTC** to refresh the slug mappings from GitHub. This is defined via a `function.json` timer trigger.

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

## 🧪 Testing

* Ensure role-based access works with real Entra users
* Test slug updates manually (`POST /api/slug_sync`)
* Verify name claims and audits persist across restarts
