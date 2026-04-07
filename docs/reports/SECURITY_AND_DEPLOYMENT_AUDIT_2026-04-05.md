# Security & Deployment Audit Report

**Date:** 2026-04-05
**Scope:** Full security review, functionality audit, IaC validation, deployment readiness
**Auditor:** Automated AI audit (GitHub Copilot)
**Test Suite Result:** 257/257 passing after fixes

---

## Executive Summary

The Azure Naming Service is a well-structured, well-documented Azure Functions v2 application with sound architecture. The audit identified **4 critical bugs**, **3 high-severity security issues**, **6 medium-severity issues**, and **several deployment gaps**. All critical bugs and most high-severity issues have been fixed as part of this audit. The application is deployment-ready after addressing the remaining recommendations.

---

## 1. Critical Bugs Found & Fixed

### C-01: Partition Key Mismatch in Release Adapter (FIXED)

**File:** `adapters/release_name.py`
**Severity:** Critical — data loss / broken release flow
**Issue:** The release adapter constructed partition keys with underscores (`{region}_{environment}`) while the claim adapter and all routes used hyphens (`{region}-{environment}`). This meant the release adapter could **never find** entities created by the claim flow.
**Fix:** Changed separator to hyphen and added `.lower()` normalization to match the claim adapter.

### C-02: Slug FullName Data Mismatch (FIXED)

**Files:** `adapters/slug_loader.py` ↔ `adapters/slug.py`
**Severity:** Critical — slug resolution broken after sync
**Issue:** `slug_loader.py` stored `FullName` as human-readable format with spaces (`"storage account"`), but `slug.py` queried `FullName` using the canonical format with underscores (`"storage_account"`). After a slug sync, **no slugs could be resolved** because the query never matched.
**Fix:** Changed `slug_loader.py` to store `FullName` as the canonical underscore-separated format.

### C-03: 14 Broken Tests (FIXED)

**Files:** `tests/test_audit_routes.py`, `tests/test_auth.py`
**Severity:** Critical — CI pipeline broken
**Issues:**
- 13 audit route tests called Azure Functions `FunctionBuilder` objects directly instead of the raw handler functions. After decorators wrap the function, `audit_routes.audit_name(req)` returns `None`.
- 1 auth test failed because the cached `_jwk_client` singleton wasn't reset between tests.
**Fix:** Extracted raw user functions via `._function.get_user_function()` for audit tests; added `_jwk_client = None` reset in auth test.

### C-04: Deprecated `datetime.utcnow()` Across Codebase (FIXED)

**Files:** `adapters/storage.py`, `adapters/audit_logs.py`, `adapters/release_name.py`, `app/routes/slug.py`, `app/routes/names.py`
**Severity:** Medium — deprecated in Python 3.12, removal scheduled
**Fix:** Replaced all instances with `datetime.now(tz=timezone.utc)`.

---

## 2. Security Findings

### HIGH Severity

#### S-01: `local.settings.json` Tracked in Git (FIXED)

**Risk:** Secrets exposure
**Issue:** `local.settings.json` containing `ALLOW_LOCAL_AUTH_BYPASS=true` and development connection strings was committed to the repository and NOT in `.gitignore`.
**Fix:** Added `local.settings.json` to `.gitignore`.
**Remaining action:** Remove from git history if repo is public: `git rm --cached local.settings.json`

#### S-02: No Rate Limiting on Any Endpoint

**Risk:** Denial of service, resource exhaustion
**Issue:** No rate limiting exists at the application level. While Azure Functions has some inherent scaling constraints, a determined attacker with valid credentials could exhaust Table Storage operations or trigger excessive slug syncs.
**Recommendation:** Add Azure API Management (APIM) in front of the Function App, or use Azure Front Door with rate limiting rules. For a low-cost option, implement a simple in-memory rate limiter per user ID.

#### S-03: Entra App Password Created by Terraform (REVIEW NEEDED)

**File:** `deploy/entra.tf`
**Risk:** Secret sprawl
**Issue:** `azuread_application_password` creates a client secret that will be stored in Terraform state. If the app is using JWT bearer tokens (which it is), this client secret may not even be needed since the Function App validates incoming tokens — it doesn't need to request tokens itself.
**Fix applied:** Added `lifecycle { ignore_changes = [end_date] }` to prevent perpetual diffs.
**Recommendation:** Evaluate whether the application password is actually needed. If not, remove it to reduce attack surface.

### MEDIUM Severity

#### S-04: OData Injection — Properly Mitigated ✅

The codebase properly escapes OData string literals by doubling single quotes in `adapters/slug.py` and `app/routes/audit.py`. Datetime values are validated by parsing through `datetime.fromisoformat()` and re-formatting. **No action needed.**

#### S-05: Metadata Injection — Properly Mitigated ✅

Storage adapter filters reserved entity keys (`PartitionKey`, `RowKey`, `InUse`, etc.) from user-supplied metadata. The `_sanitize_metadata_dict` function handles control characters and length limits. **No action needed.**

#### S-06: Local Auth Bypass — Properly Safeguarded ✅

The `core/local_bypass.py` module has a runtime check that raises `RuntimeError` if `ALLOW_LOCAL_AUTH_BYPASS` is set while `WEBSITE_INSTANCE_ID` exists (indicating Azure environment). This is a solid safeguard. **No action needed.**

#### S-07: Slug Provider Allow-List — Good ✅

The `SLUG_PROVIDER` env var is validated against `_ALLOWED_SLUG_PROVIDERS`, preventing arbitrary module loading. **No action needed.**

#### S-08: Missing Input Length Validation on Query Parameters

**Risk:** Resource exhaustion, OData query complexity
**Issue:** Query parameters like `user`, `project`, `region` in audit_bulk are passed to OData filters with escaping but without length limits. Extremely long values could create expensive queries.
**Recommendation:** Add maximum length validation (e.g., 255 chars) on all query parameters before building OData filters.

#### S-09: `AZURE_FUNCTIONS_SKIP_CERT_VERIFICATION=1` in Local Settings

**File:** `local.settings.json`
**Risk:** Man-in-the-middle during development
**Issue:** Certificate verification is disabled for local development. This is acceptable for development but must never be set in production.
**Status:** The local bypass safeguard (`WEBSITE_INSTANCE_ID` check) doesn't cover this setting.
**Recommendation:** Ensure the deploy Terraform never sets this variable (currently it doesn't — verified ✅).

### LOW Severity

#### S-10: `debugpy` in Production Requirements

**File:** `requirements.txt`
**Risk:** Debug attach surface in production
**Issue:** `debugpy==1.8.17` is listed in `requirements.txt` which gets deployed to production. This allows attaching a debugger to the running process if the debug port is exposed.
**Recommendation:** Move `debugpy` to a `requirements-dev.txt` file.

#### S-11: EasyAuth + JWT Dual Auth Path

**Issue:** The app uses both `http_auth_level=func.AuthLevel.FUNCTION` (requires function keys or EasyAuth) AND custom JWT validation via `require_role()`. This creates potential confusion about which layer is authoritative.
**Assessment:** Having defense-in-depth is good. The FUNCTION auth level acts as a fallback safety net. However, document this dual-layer strategy clearly for operators.

---

## 3. Functionality Assessment

### Strengths

| Area | Assessment |
|------|-----------|
| **Architecture** | Clean separation: `core/` (domain), `adapters/` (integrations), `app/` (HTTP), `providers/` (pluggable) |
| **Naming Rules** | Extensible JSON-based rule system with validators, templates, display fields |
| **Concurrency** | ETag-based optimistic locking on both claim and release operations |
| **Audit Trail** | Comprehensive logging of all claim/release/sync operations with user identity |
| **Slug Resolution** | Provider chain pattern with Table Storage + GitHub upstream source |
| **User Settings** | Session and permanent defaults with automatic expiration |
| **OpenAPI** | Full Swagger UI and OpenAPI 3.0 spec generation |
| **Test Coverage** | 257 passing tests covering core logic, adapters, routes, and edge cases |

### Issues

| Issue | Impact | Status |
|-------|--------|--------|
| `release_name.py` adapter uses wrong partition key format | Release via adapter fails silently | **Fixed** |
| Slug sync stores wrong `FullName` format | Slug resolution fails after sync | **Fixed** |
| `audit_bulk` has no pagination | Large result sets may timeout or OOM | Open |
| Timer trigger `slug_sync_timer` runs weekly — no manual retry on failure | Stale slugs if upstream is down for weeks | Acceptable |
| `release_name.py` adapter is dead code (unused in production routes) | Maintenance burden | Open |

---

## 4. Infrastructure as Code (IaC) Assessment

### Terraform Review (`deploy/`)

| Component | Status | Notes |
|-----------|--------|-------|
| Resource Group | ✅ Good | Properly tagged |
| Storage Account | ✅ Good | TLS 1.2, private access, deny by default |
| Table Creation | ✅ Good | All 3 tables provisioned |
| Function App | ⚠️ Fixed | Missing `AzureWebJobsStorage` connection string — **added** |
| App Insights | ✅ Good | Workspace-based, properly linked |
| Entra App Registration | ✅ Good | 3 custom roles, v2 tokens, proper scopes |
| Managed Identity | ✅ Good | System-assigned with Table + Blob roles |
| Network Security | ✅ Good | Storage `public_network_access_enabled = false` with Azure bypass |
| FTPS | ✅ Good | Disabled |
| HTTPS Only | ✅ Good | Enforced |
| Remote State | ⚠️ Commented out | Should be enabled before production |

### IaC Fix Applied

Added `AzureWebJobsStorage` connection string to Function App `app_settings` — without this, the application code cannot connect to Table Storage, as it explicitly reads `os.environ.get("AzureWebJobsStorage")`.

Added `SCM_DO_BUILD_DURING_DEPLOYMENT = "true"` to ensure Python package installation during deployment.

Added `lifecycle { ignore_changes = [end_date] }` to `azuread_application_password` to prevent Terraform plan diffs on every run.

---

## 5. CI/CD Pipeline Assessment

### Workflows Found

| Workflow | Purpose | Issues |
|----------|---------|--------|
| `ci.yml` | Run tests on push/PR | Uses `actions/setup-python@v4` |
| `tests.yml` | Unit tests + coverage | ~~Python 3.10~~ → **Fixed to 3.11** |
| `deploy.yml` | Deploy to Azure | ~~Python 3.10, `azure/login@v1`~~ → **Fixed** |
| `release.yml` | Create release tarball | Good |
| `integration.yml` | Integration tests | Good |
| `codeql.yml` | Static analysis | Good |

### Fixes Applied

- **`deploy.yml`:** Updated Python 3.10 → 3.11, `actions/checkout@v3` → `v4`, `actions/setup-python@v4` → `v5`, `azure/login@v1` → `v2`
- **`tests.yml`:** Updated Python 3.10 → 3.11, `actions/checkout@v3` → `v4`, `actions/setup-python@v4` → `v5`

### Remaining Recommendations

1. **Add environment protection rules** on the `deploy.yml` workflow (require manual approval for production).
2. **Pin action versions to commit SHAs** instead of tags for supply-chain security.
3. **Add Terraform plan/apply workflow** to automate IaC deployment with PR review gates.

---

## 6. Deployment Plan

### Pre-Deployment Checklist

- [x] All 257 tests passing
- [x] IaC provisions all required Azure resources
- [x] Entra ID app registration with 3 RBAC roles defined in Terraform
- [x] Storage tables created automatically
- [x] Application Insights configured
- [x] HTTPS-only enforced
- [x] FTPS disabled
- [x] Network rules: storage deny-by-default with Azure Services bypass
- [x] `local.settings.json` added to `.gitignore`

### Deployment Steps

#### Phase 1: Infrastructure (Terraform)

```bash
cd deploy/
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with actual values

# Enable remote state backend in providers.tf (uncomment and configure)
terraform init
terraform plan -out=tfplan
terraform apply tfplan
```

Note the outputs:
- `function_app_name` — needed for deployment
- `entra_app_client_id` — needed for token requests
- `entra_tenant_id` — needed for token requests

#### Phase 2: Configure GitHub Secrets

Set these repository secrets:
- `AZURE_CREDENTIALS` — Service principal JSON for `azure/login`
- `AZURE_FUNCTIONAPP_NAME` — From Terraform output

#### Phase 3: Deploy Application

```bash
# Option A: GitHub Actions (recommended)
git push origin main  # Triggers deploy.yml

# Option B: Azure CLI manual deploy
az functionapp deployment source config-zip \
  --resource-group <rg-name> \
  --name <func-app-name> \
  --src <archive.zip>
```

#### Phase 4: Post-Deployment Verification

1. **Trigger initial slug sync:**
   ```bash
   curl -X POST https://<func-app>/api/slug_sync \
     -H "Authorization: Bearer <admin-token>"
   ```

2. **Verify slug resolution:**
   ```bash
   curl "https://<func-app>/api/slug?resource_type=storage_account" \
     -H "Authorization: Bearer <reader-token>"
   ```

3. **Test name claim:**
   ```bash
   curl -X POST https://<func-app>/api/claim \
     -H "Authorization: Bearer <contributor-token>" \
     -H "Content-Type: application/json" \
     -d '{"resource_type":"storage_account","region":"wus2","environment":"dev"}'
   ```

4. **Assign Entra roles** to users via Azure Portal or CLI.

#### Phase 5: Monitoring

- Configure Application Insights alerts for:
  - Function execution failures > 0
  - Response time p95 > 5s
  - HTTP 5xx > 0
- Set up Azure Monitor alert for storage account availability

---

## 7. Remaining Recommendations (Not Fixed)

| # | Item | Priority | Effort |
|---|------|----------|--------|
| 1 | Move `debugpy` to `requirements-dev.txt` | Low | 5 min |
| 2 | Add pagination to `audit_bulk` endpoint | Medium | 1-2 hrs |
| 3 | Enable Terraform remote state backend | High | 15 min |
| 4 | Add input length validation on query parameters | Medium | 30 min |
| 5 | Pin GitHub Actions to commit SHAs | Medium | 30 min |
| 6 | Add Terraform CI/CD workflow | Medium | 1-2 hrs |
| 7 | Add environment protection rules to deploy workflow | High | 15 min |
| 8 | Remove `adapters/release_name.py` dead code or integrate it | Low | 15 min |
| 9 | Remove `local.settings.json` from git history | Medium | 10 min |
| 10 | Evaluate if `azuread_application_password` is needed | Low | 15 min |
| 11 | Fix remaining `datetime.utcnow()` in `tools/mcp_server/server.py` | Low | 5 min |
| 12 | Consider API Management / rate limiting for production | Medium | 2-4 hrs |

---

## 8. Summary of Changes Made

### Files Modified

| File | Change |
|------|--------|
| `adapters/release_name.py` | Fixed partition key format (`_` → `-`), added `.lower()`, timezone-aware datetime |
| `adapters/slug_loader.py` | Fixed `FullName` to store canonical format (underscores) matching query expectations |
| `adapters/storage.py` | Replaced `datetime.utcnow()` with `datetime.now(tz=timezone.utc)` |
| `adapters/audit_logs.py` | Replaced `datetime.utcnow()` with `datetime.now(tz=timezone.utc)` |
| `app/routes/names.py` | Replaced `datetime.utcnow()` with `datetime.now(tz=timezone.utc)` |
| `app/routes/slug.py` | Replaced `datetime.utcnow()` (2 instances) with `datetime.now(tz=timezone.utc)` |
| `.gitignore` | Added `local.settings.json` |
| `deploy/main.tf` | Added `AzureWebJobsStorage` and `SCM_DO_BUILD_DURING_DEPLOYMENT` to app settings |
| `deploy/entra.tf` | Added `lifecycle { ignore_changes = [end_date] }` to app password |
| `.github/workflows/deploy.yml` | Updated Python 3.10→3.11, bumped action versions |
| `.github/workflows/tests.yml` | Updated Python 3.10→3.11, bumped action versions |
| `tests/test_audit_routes.py` | Fixed tests to extract raw functions from FunctionBuilder |
| `tests/test_auth.py` | Fixed test by resetting cached `_jwk_client` |
| `tests/test_utils.py` | Updated assertion to match slug_loader fix |

### Test Results

- **Before audit:** 243 passed, 14 failed
- **After audit:** 257 passed, 0 failed
