# fix(auth): Change AuthLevel.FUNCTION to AuthLevel.ANONYMOUS for Terraform provider compatibility

## Problem

The Azure Naming Service Function App is configured with `http_auth_level=func.AuthLevel.FUNCTION` in `app/__init__.py`. This means the Azure Functions runtime **requires a function key** (`?code=<key>`) on every request, and rejects any request without one with a raw `401 Unauthorized` before application code runs.

The Terraform provider (`terraform-provider-sanmar`) authenticates using `Authorization: Bearer <token>` via `DefaultAzureCredential` — it does **not** send a function key. This causes all provider requests to fail with `401`.

### Reproduction

```bash
# Acquire a valid token
TOKEN=$(az account get-access-token \
  --scope "api://520a3d65-7b9a-4a1f-a399-caa56df4c68d/.default" \
  --query accessToken -o tsv)

# This fails with 401 even though the token is valid
curl -sv -H "Authorization: Bearer ${TOKEN}" \
  "https://wus2-prd-fn-aznaming.azurewebsites.net/api/slug?resourceType=microsoft.resources/resourcegroups"

# HTTP/1.1 401 Unauthorized — rejected by Functions runtime, not app code
```

The token itself is valid (contains `"roles":["admin"]`, correct `aud` and `iss`), but the Functions runtime rejects the request before `require_role()` in the application code is ever called.

### Root Cause

In `app/__init__.py` line 18:

```python
app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)
```

`AuthLevel.FUNCTION` tells the Azure Functions host to enforce function-key authentication at the infrastructure level. This is independent of — and runs before — Easy Auth or custom JWT validation.

### Why Easy Auth Doesn't Help

Easy Auth is **disabled** on this Function App:

```json
{
  "properties": {
    "platform": { "enabled": false }
  }
}
```

When Easy Auth is disabled, `AuthLevel.FUNCTION` only accepts requests with a valid `?code=` parameter or `x-functions-key` header. Bearer tokens are ignored at this layer.

## Proposed Fix

### Change Required

In `app/__init__.py`, change:

```python
# BEFORE
app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

# AFTER
app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)
```

### Why This Is Safe

The application already implements its own JWT-based authentication and RBAC in `core/auth.py`:

1. **Every route calls `require_role(req.headers, min_role="...")`** — this validates the JWT (signature, audience, issuer, expiry) and checks role claims
2. **The JWT validation is robust** — uses `PyJWKClient` with cached JWKS keys from Microsoft's endpoint, validates `aud=AZURE_CLIENT_ID`, `iss=https://login.microsoftonline.com/{TENANT_ID}/v2.0`
3. **Role hierarchy is enforced** — reader < contributor < admin, with aliased role names

The `FUNCTION` auth level was intended as defense-in-depth, but it prevents the primary auth mechanism (Bearer JWT) from working with the Terraform provider. The `require_role()` decorator provides the same protection, and is actually **more specific** because it also enforces role-based access control.

### Comment Update

Update the docstring and comments in `app/__init__.py` to reflect the change:

```python
"""Application package exposing the shared FunctionApp instance.

The FunctionApp uses ANONYMOUS authentication at the Azure Functions runtime
level. All authorization is handled by the application layer via require_role()
in each route handler, which validates Entra ID JWT bearer tokens and enforces
role-based access control (reader/contributor/admin).

Every endpoint MUST call require_role() — there is no infrastructure-level
fallback. Code reviews should verify this on all new routes.
"""

from __future__ import annotations

import azure.functions as func

# ANONYMOUS at the Functions level — all auth is handled by require_role()
# in each route handler via JWT validation against Entra ID
app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)
```

### Files to Change

| File | Change |
|------|--------|
| `app/__init__.py` | `AuthLevel.FUNCTION` → `AuthLevel.ANONYMOUS`, update docstring |

No other files need changes — route handlers already use `require_role()`.

### Verification After Deploy

```bash
# 1. Slug lookup (requires reader role)
TOKEN=$(az account get-access-token \
  --scope "api://520a3d65-7b9a-4a1f-a399-caa56df4c68d/.default" \
  --query accessToken -o tsv)

curl -s -H "Authorization: Bearer ${TOKEN}" \
  "https://wus2-prd-fn-aznaming.azurewebsites.net/api/slug?resourceType=microsoft.resources/resourcegroups"
# Expected: 200 with JSON slug data

# 2. Unauthenticated request (no token)
curl -s "https://wus2-prd-fn-aznaming.azurewebsites.net/api/slug?resourceType=microsoft.resources/resourcegroups"
# Expected: 401 from require_role() — "Missing bearer token"

# 3. Terraform provider test
cd /workspaces/environs-iac/sanmar/applications/internal/azure-naming/test-claim
terraform apply
# Expected: 5 claims created successfully
```

### Security Audit Checklist

Before merging, verify:

- [ ] Every route in `app/routes/` calls `require_role()` before any business logic
- [ ] `core/auth.py` validates: JWT signature via JWKS, `aud` claim, `iss` claim, `exp` claim
- [ ] Unauthenticated requests return 401 (test with `curl` without Bearer header)
- [ ] Invalid tokens return 401 (test with an expired or forged token)
- [ ] Wrong role returns 403 (test reader token against admin endpoint)

## Context

### Where This Was Discovered

During implementation of ACR-based distribution of the `terraform-provider-sanmar` binary (see `tools-iac` and `docs-iac` for related changes). The provider builds, publishes, installs, and resolves correctly — the only remaining blocker is this auth-level mismatch.

### Related Components

| Component | Status |
|-----------|--------|
| Provider binary build | ✅ Compiled v1.0.0 (Go 1.22, 16MB, linux/amd64) |
| ACR distribution (`wus2prdcrsanmariac.azurecr.io/terraform/providers/sanmar/naming`) | ✅ Published |
| Filesystem mirror install (`pull-provider-acr.sh`) | ✅ Working |
| `terraform init` resolution | ✅ `sanmar/naming v1.0.0` installed |
| `terraform validate` | ✅ Configuration valid |
| `terraform apply` | ❌ Blocked by this Function App 401 |

### Provider Auth Flow

The Terraform provider in `terraform-provider-sanmar/provider/client.go`:
1. Creates `azidentity.DefaultAzureCredential` at init
2. On each request, calls `cred.GetToken()` with the configured scope
3. Adds `Authorization: Bearer <token>` header
4. Sends HTTP request to the endpoint

It does **not** support function keys, nor should it — JWT Bearer is the standard pattern for Entra-secured APIs.

### Function App Environment Variables (Confirmed Set)

| Variable | Value |
|----------|-------|
| `AZURE_TENANT_ID` | `7c5d5df7-38dc-4b8d-b84e-4c5697ddf810` |
| `AZURE_CLIENT_ID` | `520a3d65-7b9a-4a1f-a399-caa56df4c68d` |

These match the token's `iss` and `aud` claims, so JWT validation will succeed once the request reaches the application layer.
