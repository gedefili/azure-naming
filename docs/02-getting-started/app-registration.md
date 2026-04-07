# 🆔 App Registration Guide

This runbook explains the current standard for Entra ID registration with the Azure Naming service. The API registration is now created by Terraform from the `environs-iac` repository, and this repository only needs the resulting IDs for token requests, local testing, and application deployment.

---

## Prerequisites

- Access to the `environs-iac` repository deployment at `sanmar/applications/internal/azure-naming/service`.
- Entra ID permissions sufficient for Terraform to create app registrations, service principals, and role assignments.
- CLI access with `az` installed for verification and token testing.

---

## 1. Provision the API Registration Through Terraform

Run the Azure Naming service stack from `environs-iac`.

The canonical Terraform root is:

- `sanmar/applications/internal/azure-naming/service`

During `terraform apply`, Terraform creates:

- the Entra API application registration
- the service principal
- the delegated `user_access` scope
- the `reader`, `contributor`, and `admin` app roles
- the application secret defined by the stack inputs

The Function App is provisioned in the same apply and is configured with the resulting `AZURE_CLIENT_ID` and `AZURE_TENANT_ID` values.

### Capture IDs

- **Application (client) ID** → available from Terraform output `entra_app_client_id`
- **Directory (tenant) ID** → available from Terraform output `entra_tenant_id`
- **Application secret** → available from Terraform output `entra_app_client_secret` if your client flow needs it

---

## 2. Review the Terraform-Managed Roles and Scope

Terraform defines the application roles and delegated scope for the API registration. The expected values are:

- `reader`
- `contributor`
- `admin`
- delegated scope `user_access`

You normally do not create these manually anymore. Verify them in the Azure portal only if troubleshooting is required.

---

## 3. Assign Roles to Users or Groups

Terraform creates the registration, but role assignments to real users or groups still happen afterward:

1. Go to **Enterprise applications**.
2. Open the service principal created for the Azure Naming API.
3. Open **Users and groups**.
4. Assign the appropriate role (`reader`, `contributor`, `admin`) to each user or group.

Azure automatically exposes the API using the application ID URI pattern `api://<AZURE_CLIENT_ID>`. Tokens requested for that resource can then contain the assigned roles and delegated scopes.

---

> ℹ️ The service also supports group-based enforcement via `AZURE_ROLE_GROUP_<ROLE>`. Set those environment variables to Entra group object IDs if you prefer to map roles indirectly.

---

## 4. Optional: Register a Client Application for Testing

If you want a dedicated client that can request tokens without using the portal:

1. Create another app registration (for example, `AzureNamingClient`) with platform type **Public client/native** and redirect URI `http://localhost`.
2. Under **API permissions**, add **My APIs** → select `AzureNamingService` → delegated permission `.default` (or the specific scope you created).
3. Grant admin consent if requested.
4. Record the client ID (`TEST_CLIENT_ID`). This is what you pass to `tools/get_access_token.py --client-id`.

---

## 5. Validate With the Azure CLI

Run the following commands from a login session to verify everything is wired correctly:

```bash
az login  # if not already authenticated
az account get-access-token \
  --tenant "$AZURE_TENANT_ID" \
  --resource "api://$AZURE_CLIENT_ID" \
  --query accessToken -o tsv | head -c 20
```

To retrieve the claims and confirm the roles/scopes:

```bash
python3 tools/get_access_token.py --client-id "$TEST_CLIENT_ID" --resource "api://$AZURE_CLIENT_ID" --show-claims
```

You are ready to call the API once the token helper prints the expected `roles` and `scp` entries.

---

## 6. Legacy Cloud Shell Automation

The repository still contains helper scripts for manual registration work, but they are no longer the standard path for the API registration because Terraform in `environs-iac` now owns that resource.

- `tools/cloudshell/register_naming_api.sh` — legacy helper for manual API app registration creation
- `tools/cloudshell/register_naming_client.sh` — still useful for creating a testing client app

Usage example from Cloud Shell:

```bash
git clone https://github.com/gedefili/azure-naming.git
cd azure-naming

chmod +x tools/cloudshell/*.sh
export AZURE_CLIENT_ID="<API_APP_ID_FROM_TERRAFORM_OUTPUT>"
./tools/cloudshell/register_naming_client.sh
```

The scripts expect `az` and `jq` to be available (pre-installed in Cloud Shell). You can override defaults by setting environment variables before execution:

- `CLIENT_APP_NAME`, `REDIRECT_URI`, `SCOPE_VALUE`, `AZURE_CLIENT_ID` for the client script.

---

## Troubleshooting

- **Missing roles in the token:** Ensure the user or group has been assigned the App Role. Re-consent in the portal or re-authenticate via `az login` to refresh the token cache.
- **`AADSTS500011` errors:** The Application ID URI does not match what the client requested. Verify `api://<AZURE_CLIENT_ID>` is consistent across the API registration and token request.
- **Local bypass flags active in production:** Disable `ALLOW_LOCAL_AUTH_BYPASS` and related environment variables in production slots to avoid bypassing RBAC enforcement.

For deeper RBAC configuration details, continue with [Authentication & RBAC](auth.md).
