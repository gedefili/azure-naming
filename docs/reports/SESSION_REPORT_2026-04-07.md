# Session Report — April 7, 2026

## Objective

Authenticate against the live Azure Naming API (`wus2-prd-fn-aznaming.azurewebsites.net`) and prepare the GitHub Actions deploy pipeline for first deployment.

---

## Part 1: Resolving Authentication Issues

### Problem

The Azure CLI could not obtain a bearer token for the API resource `api://520a3d65-7b9a-4a1f-a399-caa56df4c68d`. Three distinct errors were encountered and resolved in sequence.

### Error 1 — AADSTS650057: Invalid resource

**Cause:** Requesting a token with `--resource api://520a3d65-...` uses the v1 token endpoint, which requires explicit pre-authorization.

**Fix:** Switched to the v2 endpoint by using `--scope api://520a3d65-.../.default` instead of `--resource`.

### Error 2 — Azure CLI service principal missing from tenant

**Cause:** The Microsoft Azure CLI app (`04b07795-8ddb-461a-bbee-02f9e1bf7b46`) had no service principal object in the SanMar Corporation tenant (`7c5d5df7-38dc-4b8d-b84e-4c5697ddf810`).

**Fix:** Created the service principal:

```bash
az ad sp create --id 04b07795-8ddb-461a-bbee-02f9e1bf7b46
```

Result: SP object ID `59a064a3-04b7-46fc-85a5-9d73def90b1e`

### Error 3 — AADSTS65001: User/admin has not consented

**Cause:** Even with the Azure CLI pre-authorized on the API app registration, there was no OAuth2 permission grant in the tenant allowing the CLI SP to act on behalf of users against the API.

**Fixes applied (two steps):**

1. **Pre-authorized Azure CLI on the API registration** via Microsoft Graph:

```bash
az rest --method PATCH \
  --uri "https://graph.microsoft.com/v1.0/applications/e389b9c2-64e8-4847-a093-a191c5e95606" \
  --body '{"api":{"preAuthorizedApplications":[{
    "appId":"04b07795-8ddb-461a-bbee-02f9e1bf7b46",
    "delegatedPermissionIds":["2e566b39-efb4-226c-95b1-ef574d20e0a3"]
  }]}}'
```

2. **Granted tenant-wide admin consent** via an OAuth2 permission grant:

```bash
az rest --method POST \
  --uri "https://graph.microsoft.com/v1.0/oauth2PermissionGrants" \
  --body '{
    "clientId": "59a064a3-04b7-46fc-85a5-9d73def90b1e",
    "consentType": "AllPrincipals",
    "resourceId": "06d0a28b-5eef-48b8-965f-48394a24b338",
    "scope": "user_access"
  }'
```

### Outcome

Token acquisition now works:

```bash
az account get-access-token \
  --scope api://520a3d65-7b9a-4a1f-a399-caa56df4c68d/.default \
  --query accessToken -o tsv
```

Returns a valid 1622-character JWT.

---

## Part 2: Key IDs Reference

| Entity | ID |
|--------|-----|
| API app registration (application) | `520a3d65-7b9a-4a1f-a399-caa56df4c68d` |
| API app registration (object) | `e389b9c2-64e8-4847-a093-a191c5e95606` |
| API service principal (object) | `06d0a28b-5eef-48b8-965f-48394a24b338` |
| Azure CLI app ID | `04b07795-8ddb-461a-bbee-02f9e1bf7b46` |
| Azure CLI SP (object, in tenant) | `59a064a3-04b7-46fc-85a5-9d73def90b1e` |
| Delegated scope `user_access` ID | `2e566b39-efb4-226c-95b1-ef574d20e0a3` |
| Tenant (SanMar Corporation) | `7c5d5df7-38dc-4b8d-b84e-4c5697ddf810` |
| Subscription (management-tools) | `cfe7cbd7-1b9d-4f5c-9459-57d72559d3f5` |

---

## Part 3: GitHub Actions Deploy Pipeline

### Workflow

`deploy.yml` triggers on every push to `main`. It:
1. Checks out the code
2. Installs Python 3.11 + dependencies
3. Runs `pytest -q`
4. Logs into Azure via `azure/login@v2`
5. Publishes to the function app via `Azure/functions-action@v1`

### Service Principal Created

A dedicated service principal was created for GitHub Actions:

```bash
az ad sp create-for-rbac \
  --name "github-actions-azure-naming-deploy" \
  --role Contributor \
  --scopes "/subscriptions/cfe7cbd7-1b9d-4f5c-9459-57d72559d3f5/resourceGroups/wus2-prd-rg-aznaming"
```

- **SP client ID:** `f117e43d-fab7-4c86-a47d-d59c3f7e4a8a`
- **Role:** Contributor
- **Scope:** Resource group `wus2-prd-rg-aznaming` only (least-privilege)

### GitHub Secrets Configured

| Secret | Value |
|--------|-------|
| `AZURE_CREDENTIALS` | Full SDK-auth JSON for the deploy SP |
| `AZURE_FUNCTIONAPP_NAME` | `wus2-prd-fn-aznaming` |

Both were set via `gh secret set` on repo `gedefili/azure-naming`.

---

## Part 4: Deployment — Issues Found and Resolved

### Deploy Attempt 1 — Functions return 404

**Symptom:** All endpoints returned HTTP 404 despite the default landing page loading.

**Root cause 1 — Missing `AzureWebJobsFeatureFlags`:**
The Python v2 programming model requires `AzureWebJobsFeatureFlags=EnableWorkerIndexing` to tell the host to delegate function discovery to the Python worker. This was not set.

**Root cause 2 — Extension bundle too old:**
`host.json` specified extension bundle `[2.*, 3.0.0)`. The v2 Python model requires bundle v3 or v4.

**Fix:** Updated `host.json` to `[4.*, 5.0.0)` and added the app setting.

### Deploy Attempt 2 — Still 404

**Root cause 3 — Dependencies not bundled:**
The GitHub Actions workflow installed dependencies into the system Python but shipped the zip without them. On Linux Consumption without remote build, the zip must contain `.python_packages/lib/site-packages/`.

**Fix:** Added a `pip install --target=".python_packages/lib/site-packages"` step to the workflow.

### Deploy Attempt 3 — 401 Unauthorized

**Root cause 4 — GLIBC compatibility:**
The `cryptography` package compiled on Ubuntu 24.04 (GLIBC 2.39) failed to load on the Azure Functions host (GLIBC < 2.33):
```
ImportError: /lib/x86_64-linux-gnu/libc.so.6: version `GLIBC_2.33' not found
(required by cryptography/hazmat/bindings/_rust.abi3.so)
```

**Fix:** Changed pip install to use `--platform manylinux2014_x86_64 --only-binary=:all:` to pull pre-built wheels compatible with the Azure Functions host OS.

### Deploy Attempt 4 — Success!

After the platform fix, all 11 functions registered and the app became functional. However, `AuthLevel.FUNCTION` requires a function key (`?code=...`) in addition to the bearer token.

### App Settings Added

| Setting | Value |
|---------|-------|
| `AzureWebJobsFeatureFlags` | `EnableWorkerIndexing` |
| `SANMAR_SLUGS_CONNECTION` | Same connection string as `AzureWebJobsStorage` |

---

## Part 5: Live Endpoint Test Results

All tests performed against `https://wus2-prd-fn-aznaming.azurewebsites.net` with bearer token + function key.

| Endpoint | Method | HTTP Status | Result |
|----------|--------|-------------|--------|
| `/api/slug?resource_type=storage_account` | GET | 200 | `{"slug": "st"}` |
| `/api/slug?resource_type=key_vault` | GET | 200 | `{"slug": "kv"}` |
| `/api/openapi.json` | GET | 200 | Full 28KB OpenAPI 3.0 spec |
| `/api/docs` | GET | 200 | Swagger UI HTML |
| `/api/rules` | GET | 200 | `{"resourceTypes": ["default", "key_vault", "storage_account"]}` |
| `/api/slug_sync` | POST | 200 | `86 existing slugs` |
| `/api/claim` | POST | 200 | Generated name `wus2devstsanmarntest` |

---

## Part 6: Remaining Items

1. **Integration tests workflow** — Fails at "Initialize containers" (Docker/Azurite service container issue). Pre-existing; unrelated to this deploy.
2. **CodeQL workflow** — Fails at "Perform CodeQL Analysis". Pre-existing.
3. **Function key requirement** — `AuthLevel.FUNCTION` means callers need a function key (`?code=...`). Consider switching to `AuthLevel.ANONYMOUS` if you want bearer-token-only auth (the app implements its own JWT RBAC via `require_role()`), or configure Azure EasyAuth on the Function App to remove the `?code=` requirement.
4. **Store function key as GitHub secret** — If keeping `FUNCTION` auth level, add the function key to secrets for CI/Postman workflows.
