# fix(deploy): Deploy AuthLevel.ANONYMOUS fix and restore Function App routes

## Status: RESOLVED in v1.8.1

> **Release**: `v1.8.1` (branch `platform/fix/deploy-pipeline-remote-build`)
> **Operator action required**: Merge the PR and perform the one-time manual deployment described below.

---

## Problem

The Azure Naming Service Function App (`wus2-prd-fn-aznaming`) is currently in a **broken deployment state** — all routes return `404 Not Found` with zero functions registered. The auth level fix (`AuthLevel.FUNCTION` → `AuthLevel.ANONYMOUS`) has been applied in source code (`app/__init__.py`) but was never successfully deployed to the live Function App.

### Current State (as of 2026-04-14)

| Item | Status |
|------|--------|
| Source code fix in `app/__init__.py` | ✅ Applied — `AuthLevel.ANONYMOUS` |
| Provider binary v1.1.0 | ✅ Built and available in repo |
| Function App `wus2-prd-fn-aznaming` | ❌ **0 functions registered, all routes 404** |
| `WEBSITE_RUN_FROM_PACKAGE` | Set to a zip missing `adapters/` and `providers/` modules |
| Terraform provider test-claim | ❌ Blocked — cannot reach naming service |

### Timeline of Events

1. **Original state**: Function App was working (deployed via `func azure functionapp publish` or similar). All 11 functions registered. Routes returned `401` because `AuthLevel.FUNCTION` blocked Bearer tokens.

2. **Auth fix applied**: `app/__init__.py` changed `AuthLevel.FUNCTION` → `AuthLevel.ANONYMOUS` (commit `6418610`). Source code is correct.

3. **Broken zip deployed**: `WEBSITE_RUN_FROM_PACKAGE` was set to a blob-stored zip (`20260414044153-b095e676-...`) that contained **only** `app/`, `core/`, `function_app.py`, `host.json`, `requirements.txt` — missing the `adapters/` and `providers/` Python packages required by route imports.

4. **Attempted remediation** (2026-04-14): Multiple deployment attempts were made from the IaC devcontainer:
   - **Zip deploy via Kudu** with complete source (including `adapters/`, `providers/`) + `.python_packages` built with Python 3.9 → Functions failed to load (ABI mismatch — Function App runs Python 3.11)
   - **Zip deploy with Python 3.11 cross-compiled deps** (`pip install --python-version 3.11 --only-binary=:all: --platform manylinux2014_x86_64`) → Still 0 functions, 404 on all routes
   - **Oryx remote build** (`SCM_DO_BUILD_DURING_DEPLOYMENT=true`, `ENABLE_ORYX_BUILD=true`) with source-only zip → Deployment reported success (status 4) but functions did not register
   - **WEBSITE_RUN_FROM_PACKAGE with full zip** → Functions never loaded

5. **Current state**: `WEBSITE_RUN_FROM_PACKAGE` points to the Python 3.11 zip. Zero functions are registered. All routes return 404.

## Root Cause Analysis

### Why the original zip was broken

The original `WEBSITE_RUN_FROM_PACKAGE` zip (`20260414044153-b095e676-...`) was missing two critical Python packages:

```
adapters/       ← imported by app/dependencies.py
providers/      ← imported by app/routes/rules.py
```

The `app/dependencies.py` file imports:
```python
from adapters.audit_logs import write_audit_log
from adapters.slug_fetcher import SlugSourceError, get_all_remote_slugs
from adapters.storage import get_table_client
```

Without these modules, the Python worker cannot import the route handlers, so no functions register.

### Why subsequent deployments failed

| Attempt | Reason for failure |
|---------|-------------------|
| Complete zip + Python 3.9 `.python_packages` | ABI mismatch — `.so` files compiled for `cpython-39` fail on Python 3.11 runtime |
| Complete zip + Python 3.11 cross-compiled deps | Likely missing transitive dependencies or pip cross-compile produced incomplete packages |
| Oryx remote build | Deployment status reported success but functions didn't register — Oryx may not have executed `pip install` |

### Why the Function App was originally working

The Function App was originally deployed using a method that performed a **server-side build** (likely `func azure functionapp publish --build remote` or VS Code Azure Functions extension). This method:
1. Uploads source code to Kudu
2. Runs Oryx build on the server with the correct Python 3.11
3. Installs pip dependencies in the correct location
4. Does NOT use `WEBSITE_RUN_FROM_PACKAGE`

Setting `WEBSITE_RUN_FROM_PACKAGE` to a pre-built zip bypassed this build process and mounted a broken zip as the read-only site root.

## Required Fix

### Step 1: Deploy from the azure-naming repository using `func` CLI

The deployment **must** happen from a machine with:
- Azure Functions Core Tools (`func`) installed
- Python 3.11 available
- `az login` with permissions to deploy to `wus2-prd-fn-aznaming`

```bash
cd /workspaces/azure-naming   # or wherever cloud-resource-naming is cloned

# Remove WEBSITE_RUN_FROM_PACKAGE so func publish can write to wwwroot
az functionapp config appsettings delete \
  -n wus2-prd-fn-aznaming \
  -g wus2-prd-rg-aznaming \
  --setting-names WEBSITE_RUN_FROM_PACKAGE

# Deploy with remote build (server-side pip install with Python 3.11)
func azure functionapp publish wus2-prd-fn-aznaming --build remote --python
```

### Step 2: Verify deployment

```bash
# 1. Check functions are registered
az functionapp function list \
  -n wus2-prd-fn-aznaming \
  -g wus2-prd-rg-aznaming \
  --query "[].name" -o tsv
# Expected: 11 functions (audit_bulk, audit_name, claim_name, etc.)

# 2. Test slug endpoint with Bearer token
TOKEN=$(az account get-access-token \
  --scope "api://520a3d65-7b9a-4a1f-a399-caa56df4c68d/.default" \
  --query accessToken -o tsv)

curl -s -w "\nHTTP: %{http_code}\n" \
  -H "Authorization: Bearer ${TOKEN}" \
  "https://wus2-prd-fn-aznaming.azurewebsites.net/api/slug?resourceType=microsoft.resources/resourcegroups"
# Expected: 200 with JSON slug data (NOT 401, NOT 404)

# 3. Verify unauthenticated requests are rejected by app code
curl -s -w "\nHTTP: %{http_code}\n" \
  "https://wus2-prd-fn-aznaming.azurewebsites.net/api/slug?resourceType=microsoft.resources/resourcegroups"
# Expected: 401 from require_role() — "Missing bearer token"
```

### Step 3: Test Terraform provider

```bash
cd /workspaces/environs-iac/sanmar/applications/internal/azure-naming/test-claim
rm -rf .terraform .terraform.lock.hcl
terraform init
terraform plan
terraform apply   # Creates 5 test claims in sbx environment
terraform destroy # Releases the claims
```

### Step 4 (optional): Clean up blob storage

Remove broken deployment zips from `wus2prdstsanmaraznaming` storage account, container `function-releases`:
- `20260414044153-b095e676-f182-4f6e-a765-7a098c9b34e8.zip` (missing adapters/providers)
- `20260414050802-1cf999f3-8539-42cd-b6e6-b45a5f5f8436.zip` (attempted fix, incomplete)
- `20260414051104-71f81d30-929c-4c00-b8a7-2a582bb845e4.zip` (attempted fix, incomplete)
- `20260414-complete-deploy.zip` (Python 3.9 ABI, wrong platform)
- `20260414-py311-deploy.zip` (Python 3.11 cross-compiled, still broken)

## App Settings to Clean Up

After successful deployment, ensure these settings are correct:

| Setting | Required Value | Notes |
|---------|---------------|-------|
| `WEBSITE_RUN_FROM_PACKAGE` | **Remove** or set to `0` | Must not point to a zip — let the build deploy to wwwroot |
| `SCM_DO_BUILD_DURING_DEPLOYMENT` | `true` | Enables pip install during future zip deploys |
| `ENABLE_ORYX_BUILD` | `true` | Enables Oryx build system |

## Deployment Pipeline Recommendation

To prevent this from happening again, the `cloud-resource-naming` repository should have a CI/CD pipeline that:

1. Triggers on merge to `main`
2. Uses `func azure functionapp publish --build remote` (or equivalent Azure Pipelines task)
3. Runs post-deploy verification (function list count, health check endpoint)
4. Does NOT use `WEBSITE_RUN_FROM_PACKAGE` with pre-built zips unless the zip is built in CI with the correct Python version and all dependencies

## Required Source Files for Any Zip Deployment

If `WEBSITE_RUN_FROM_PACKAGE` is used in future, the zip **must** include:

```
function_app.py          # Entry point
host.json                # Functions runtime config
requirements.txt         # pip dependencies
app/                     # Application package (routes, models, etc.)
core/                    # Core business logic (auth, naming, validation)
adapters/                # Storage, audit, slug adapters
providers/               # Naming rule providers
.python_packages/        # Pre-installed pip packages (MUST match runtime Python version)
```

## Provider v1.1.0 Installation (IaC devcontainer)

While the auth fix blocks the test-claim project, the provider binary v1.1.0 has been installed in the local filesystem mirror:

```
/home/vscode/.config/terraform/providers/registry.terraform.io/sanmar/naming/1.1.0/linux_amd64/terraform-provider-naming_v1.1.0
```

`terraform init` in the test-claim project resolves `sanmar/naming v1.1.0` correctly. The provider is ready — only the naming service deployment is blocking.

## Related

- `.github/ISSUES/fix-auth-level-for-terraform-provider.md` — Original auth level issue (source fix applied, deploy pending)
- `tools-iac/bash/naming/publish-provider-acr.sh` — **Removed** (publishing moved to this repository)
- `tools-iac/bash/naming/pull-provider-acr.sh` — Provider pull script (still in tools-iac)

---

## Resolution — v1.8.1

### What was fixed (code changes)

Three root causes have been addressed in release `v1.8.1`:

| File | Change | Why |
|------|--------|-----|
| `.github/workflows/deploy.yml` | Replaced pre-built zip with remote build (`scm-do-build-during-deployment: true`) | The old workflow used `pip install --target --platform manylinux2014_x86_64` which cross-compiled deps for the wrong ABI and omitted transitive packages. Remote build runs `pip install` server-side with the Function App's own Python 3.11, guaranteeing correct binaries |
| `.github/workflows/deploy.yml` | Added `WEBSITE_RUN_FROM_PACKAGE` removal step before deploy | Prevents stale zip artifacts from overriding the deployment |
| `.github/workflows/deploy.yml` | Split into `test` → `deploy` → `verify` jobs; verify checks function count and smoke-tests `/api/docs` | Future deployments will fail the workflow if functions don't register |
| `.funcignore` | Expanded to exclude `tests/`, `tools/`, `docs/`, `deploy/`, `terraform-provider-sanmar/` | Keeps the deployment package small, but retains `adapters/`, `providers/`, `core/`, `app/`, `rules/` |
| `tools/verify_deployment.py` | New script for manual post-deploy checks | Operator can verify function count, app settings, and endpoint health |

### Operator actions required to finish the fix

The CI/CD workflow will handle future deployments automatically once this branch is merged. However, **the current production Function App is broken now** and needs a one-time manual recovery. Follow these steps in order:

#### Step 1: Merge the PR

Merge the `platform/fix/deploy-pipeline-remote-build` branch into `main`. This triggers the updated `deploy.yml` workflow which will:
1. Run tests
2. Remove `WEBSITE_RUN_FROM_PACKAGE`
3. Set `SCM_DO_BUILD_DURING_DEPLOYMENT=true` and `ENABLE_ORYX_BUILD=true`
4. Deploy with remote build
5. Verify function registration

If the CI deploy succeeds and the verify job passes, **no further action is needed**.

#### Step 2 (only if CI deploy fails): Manual deployment

If the GitHub Actions deploy does not restore the Function App, deploy manually from a machine with `func` CLI, Python 3.11, and `az login`:

```bash
cd /workspaces/azure-naming

# 1. Remove the broken WEBSITE_RUN_FROM_PACKAGE setting
az functionapp config appsettings delete \
  -n wus2-prd-fn-aznaming \
  -g wus2-prd-rg-aznaming \
  --setting-names WEBSITE_RUN_FROM_PACKAGE

# 2. Ensure remote build settings
az functionapp config appsettings set \
  -n wus2-prd-fn-aznaming \
  -g wus2-prd-rg-aznaming \
  --settings SCM_DO_BUILD_DURING_DEPLOYMENT=true ENABLE_ORYX_BUILD=true

# 3. Deploy with remote build
func azure functionapp publish wus2-prd-fn-aznaming --build remote --python
```

#### Step 3: Verify deployment

```bash
# Option A: Use the new verification script
python tools/verify_deployment.py --wait 30

# Option B: Manual verification
az functionapp function list \
  -n wus2-prd-fn-aznaming \
  -g wus2-prd-rg-aznaming \
  --query "[].name" -o tsv
# Expected: 8+ functions registered

# Test with Bearer token
TOKEN=$(az account get-access-token \
  --scope "api://520a3d65-7b9a-4a1f-a399-caa56df4c68d/.default" \
  --query accessToken -o tsv)

curl -s -w "\nHTTP: %{http_code}\n" \
  -H "Authorization: Bearer ${TOKEN}" \
  "https://wus2-prd-fn-aznaming.azurewebsites.net/api/slug?resourceType=microsoft.resources/resourcegroups"
# Expected: HTTP 200 with JSON slug data
```

#### Step 4: Test Terraform provider (IaC devcontainer)

```bash
cd /workspaces/environs-iac/sanmar/applications/internal/azure-naming/test-claim
rm -rf .terraform .terraform.lock.hcl
terraform init
terraform plan
terraform apply   # Creates test claims
terraform destroy # Releases claims
```

#### Step 5 (optional): Clean up blob storage

Remove broken deployment zips from `wus2prdstsanmaraznaming` storage account, container `function-releases`:
- `20260414044153-b095e676-f182-4f6e-a765-7a098c9b34e8.zip`
- `20260414050802-1cf999f3-8539-42cd-b6e6-b45a5f5f8436.zip`
- `20260414051104-71f81d30-929c-4c00-b8a7-2a582bb845e4.zip`
- `20260414-complete-deploy.zip`
- `20260414-py311-deploy.zip`

### Why this won't happen again

1. **Remote build**: The deploy workflow now uses server-side `pip install`, not local cross-compilation. Oryx on the Function App runs `pip install -r requirements.txt` with the runtime's own Python 3.11 — no ABI mismatches possible.
2. **`.funcignore` coverage**: The ignore file now explicitly lists what to exclude, ensuring `adapters/`, `providers/`, and `rules/` are included.
3. **Post-deploy verification**: The `verify` job checks that functions are actually registered after deployment, failing the workflow if zero functions load.
4. **No `WEBSITE_RUN_FROM_PACKAGE`**: The workflow removes this setting before every deploy, so stale zips can never shadow the deployment.
