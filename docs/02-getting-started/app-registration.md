# 🆔 App Registration Guide

This runbook walks through registering the Azure Naming Function in Entra ID (Azure Active Directory) so that callers can request tokens and the service can enforce role-based access control. Complete these steps before attempting to obtain bearer tokens or configure branch protections.

---

## Prerequisites

- Entra ID tenant admin permissions (or delegated rights to create app registrations and roles).
- The Azure Function already deployed (or a plan to deploy it) so you know which audience the tokens should target.
- CLI access with `az` installed (optional but recommended for verification).

---

## 1. Register the API (Server) Application

1. Sign in to the **Azure portal** → **Entra ID** → **App registrations** → **New registration**.
2. Name the app (for example, `AzureNamingService`).
3. Choose **Accounts in this organizational directory only** unless you need multi-tenant access.
4. Leave the redirect URI blank (the Function relies on EasyAuth/JWT validation rather than direct redirects) and click **Register**.

### Capture IDs

- **Application (client) ID** → set this as `AZURE_CLIENT_ID` in app configuration.
- **Directory (tenant) ID** → set this as `AZURE_TENANT_ID`.

---

## 2. Define App Roles

Professional deployments use App Roles to represent `reader`, `contributor`, and `admin` permissions.

1. Inside the registration, open **App roles** → **Create app role**.
2. Create the following roles (member type `Users/Groups`):
   - Display name `Sanmar Naming Reader`, value `reader`.
   - Display name `Sanmar Naming Contributor`, value `contributor`.
   - Display name `Sanmar Naming Admin`, value `admin`.
3. Save each role. Azure may take a minute to propagate the new roles.

---

## 3. Expose the API

1. Navigate to **Expose an API**.
2. If an Application ID URI is not set, click **Set**, then enter `api://<AZURE_CLIENT_ID>`.
3. Under **Scopes defined by this API**, add a delegated scope (for example, `user_access`).
   - Set **Who can consent?** to **Admins and users**.
   - Provide a meaningful admin/user consent description.
   - Enable the scope.
4. Azure automatically enables the `.default` shorthand. Tokens requested for `api://<AZURE_CLIENT_ID>/.default` will contain any scopes and app roles assigned to the caller.

---

## 4. Assign Roles to Users or Groups

1. Go to **Enterprise applications** → search for the new API registration.
2. Open **Users and groups** → **Add user/group**.
3. Select the user(s) or group(s) and assign the appropriate role (`reader`, `contributor`, `admin`).
4. Repeat for each audience segment.

> ℹ️ The service also supports group-based enforcement via `AZURE_ROLE_GROUP_<ROLE>`. Set those environment variables to Entra group object IDs if you prefer to map roles indirectly.

---

## 5. Optional: Register a Client Application for Testing

If you want a dedicated client that can request tokens without using the portal:

1. Create another app registration (for example, `AzureNamingClient`) with platform type **Public client/native** and redirect URI `http://localhost`.
2. Under **API permissions**, add **My APIs** → select `AzureNamingService` → delegated permission `.default` (or the specific scope you created).
3. Grant admin consent if requested.
4. Record the client ID (`TEST_CLIENT_ID`). This is what you pass to `tools/get_access_token.py --client-id`.

---

## 6. Validate With the Azure CLI

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

## 7. Cloud Shell Automation (Optional)

If you prefer to automate the registration from Azure Cloud Shell, the repository includes helper scripts:

- `tools/cloudshell/register_naming_api.sh` — Creates the API app registration, configures roles (`reader`, `contributor`, `admin`), adds the delegated scope, and provisions the service principal.
- `tools/cloudshell/register_naming_client.sh` — Creates a public client app wired to the API scope so you can request tokens for testing.

Usage example from Cloud Shell:

```bash
git clone https://github.com/gedefili/azure-naming.git
cd azure-naming

chmod +x tools/cloudshell/*.sh
./tools/cloudshell/register_naming_api.sh

export AZURE_CLIENT_ID="<API_APP_ID_FROM_PREVIOUS_STEP>"
./tools/cloudshell/register_naming_client.sh
```

Both scripts expect `az` and `jq` to be available (pre-installed in Cloud Shell). You can override defaults by setting environment variables before execution:

- `API_APP_NAME`, `SCOPE_NAME` for the API script.
- `CLIENT_APP_NAME`, `REDIRECT_URI`, `SCOPE_VALUE`, `AZURE_CLIENT_ID` for the client script.

---

## Troubleshooting

- **Missing roles in the token:** Ensure the user or group has been assigned the App Role. Re-consent in the portal or re-authenticate via `az login` to refresh the token cache.
- **`AADSTS500011` errors:** The Application ID URI does not match what the client requested. Verify `api://<AZURE_CLIENT_ID>` is consistent across the API registration and token request.
- **Local bypass flags active in production:** Disable `ALLOW_LOCAL_AUTH_BYPASS` and related environment variables in production slots to avoid bypassing RBAC enforcement.

For deeper RBAC configuration details, continue with [Authentication & RBAC](auth.md).
