# feat(rules): Enable end-to-end Terraform provider testing

## Problem

The `sanmar/naming` Terraform provider cannot be tested end-to-end from the IaC devcontainer. Two gaps in the naming service prevent a clean `terraform plan → apply → destroy` cycle:

1. **No sandbox environment**: The naming service only accepts environments `alt`, `dev`, `prd`, `stg`, `tst`, `uat`. There is no `sbx` (sandbox) environment for safe, isolated testing that won't pollute real naming registries.

2. **Limited resource type coverage**: The slug/rules API only defines 3 resource types (`default`, `key_vault`, `storage_account`). Common Azure resource types like resource groups, virtual networks, subnets, and others have no slug mappings. The test-claim project needs at least a few more types to exercise the provider meaningfully.

### Current State (as of 2026-04-14)

| Item | Status |
|------|--------|
| Function App deployment | ✅ Restored — 10 functions registered, `func publish --build remote` succeeded |
| Auth level fix (`AuthLevel.ANONYMOUS`) | ✅ Deployed and verified |
| Authenticated requests (Bearer token) | ✅ Returns 200 with slug data |
| Unauthenticated requests | ✅ Returns 401 "Missing bearer token" |
| Provider v1.1.0 | ✅ Installed in filesystem mirror, `terraform init` resolves correctly |
| `terraform plan` (claims only) | ✅ Plans successfully with `storage_account` and `key_vault` types |
| `terraform apply` | ❌ Fails — environment `sbx` rejected, `tst` blocked by variable validation |
| End-to-end test lifecycle | ❌ Blocked |

### What We Tried

The test-claim project at `environs-iac/sanmar/applications/internal/azure-naming/test-claim/` was configured with:

- `environment = "sbx"` — safe sandbox choice, but naming service rejects it: `environment must be one of ['alt', 'dev', 'prd', 'stg', 'tst', 'uat']`
- `environment = "tst"` — valid in the naming service, but the test-claim variable validation restricts to `sbx` to prevent polluting real environments
- Data sources using Azure-format resource types (`microsoft.resources/resourcegroups`, `microsoft.network/virtualnetworks`, etc.) — all return null because the slug API doesn't have these mappings

### Error Messages

**Environment rejection** (from naming service `/api/claim`):
```
unexpected status 400: environment must be one of ['alt', 'dev', 'prd', 'stg', 'tst', 'uat']
```

**Slug not found** (from naming service `/api/slug`):
```json
{"message": "Slug not found for resource type 'microsoft.resources/resourcegroups'."}
```

## Root Cause

### Environment constraint

The `allowed_values` in the rules JSON files define a closed set of environments:

- `rules/us_storage_account.json` line 34: `"environment": ["prd", "stg", "tst", "uat", "alt", "dev"]`
- `rules/us_key_vault.json` line 34: `"environment": ["prd", "stg", "tst", "uat", "alt", "dev"]`

There is no `sbx` environment, which is the standard SanMar sandbox environment code used for isolated testing.

### Resource type coverage

Only 3 resource types are defined in `rules/`:

| File | Resource Type |
|------|--------------|
| `base.json` | `default` |
| `us_key_vault.json` | `key_vault` |
| `us_storage_account.json` | `storage_account` |

The naming service needs rules for common Azure resource types to be useful for real IaC workflows (resource groups, virtual networks, subnets, NSGs, etc.).

## Required Changes

### 1. Add `sbx` to allowed environments

Update all rule files to include `sbx` in the `allowed_values.environment` array:

```json
"environment": ["prd", "stg", "tst", "uat", "alt", "dev", "sbx"]
```

**Files to update:**
- `rules/us_storage_account.json`
- `rules/us_key_vault.json`
- Any future rule files

### 2. Add resource type rules for common Azure resources

Create rule files for at least:

| Resource Type | Suggested Slug | Rule File |
|--------------|----------------|-----------|
| `resource_group` | `rg` | `us_resource_group.json` |
| `virtual_network` | `vnet` | `us_virtual_network.json` |
| `subnet` | `snet` | `us_subnet.json` |
| `network_security_group` | `nsg` | `us_network_security_group.json` |

### 3. Consider Azure-format resource type aliases

The Terraform provider sends Azure-format resource types (e.g., `microsoft.resources/resourcegroups`). The slug API should either:
- Accept Azure-format types directly and map them internally, OR
- Document the expected short-form type names so provider authors know what to use

### 4. Deploy after changes

After updating rules and rebuilding, redeploy with:
```bash
func azure functionapp publish wus2-prd-fn-aznaming --build remote --python
```

## Verification

Once these changes are deployed, the test-claim project should complete a full lifecycle:

```bash
cd /workspaces/environs-iac/sanmar/applications/internal/azure-naming/test-claim
rm -rf .terraform .terraform.lock.hcl
terraform init        # Resolves sanmar/naming v1.1.0
terraform plan        # Plans claims + slug data sources
terraform apply       # Creates claims in sbx environment
terraform destroy     # Releases claims
```

## Related

- `.github/ISSUES/deploy-auth-fix-and-restore-function-app.md` — Function App deployment fix (resolved in v1.8.1)
- `.github/ISSUES/fix-auth-level-for-terraform-provider.md` — Auth level fix (resolved)
- `environs-iac/sanmar/applications/internal/azure-naming/test-claim/` — Test-claim project (blocked by this issue)
