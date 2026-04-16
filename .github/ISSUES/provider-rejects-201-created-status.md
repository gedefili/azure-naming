# bug(provider): ClaimName rejects HTTP 201 Created as unexpected status

## Problem

The Terraform provider's `ClaimName` method in `provider/client.go` only accepts `HTTP 200 OK` from the `/api/claim` endpoint. However, the naming service correctly returns `HTTP 201 Created` when a name is successfully claimed. The provider treats 201 as an error, causing `terraform apply` to fail even though the claim was created server-side.

### Symptoms

- `terraform plan` succeeds (slug data sources return 200)
- `terraform apply` creates the claim on the server (201 response with full JSON payload) but the provider reports an error
- Claims are created on the server but **not recorded in Terraform state**, making them orphaned
- Subsequent `terraform apply` attempts may create duplicate claims

### Error Output

```
Error: Failed to claim name

  with sanmar_claim.storage_account,
  on main.tf line 25, in resource "sanmar_claim" "storage_account":
  25: resource "sanmar_claim" "storage_account" {

unexpected status 201: {"name": "wus2tststsanmarnmtst", "resourceType": "storage_account",
"region": "wus2", "environment": "tst", "slug": "st", "system": "nmtst", "purpose": "data",
"display": [...], "summary": "Storage account 'wus2tststsanmarnmtst' for system 'NMTST' in TST-WUS2",
"claimedBy": "54b86504-6934-4230-bcf6-efe891ac0a3d"}
```

### Root Cause

`provider/client.go` line 195:

```go
if resp.StatusCode != http.StatusOK {
    return nil, decodeError(resp)
}
```

This rejects any status code other than 200. The `/api/claim` endpoint returns `201 Created` (the correct HTTP semantic for resource creation), so the provider treats the successful response as an error.

## Required Fix

In `provider/client.go`, the `ClaimName` method should accept both 200 and 201:

```go
if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusCreated {
    return nil, decodeError(resp)
}
```

Also audit `ReleaseName` (line 227) and any other methods for the same pattern — `DELETE`/release endpoints may return `204 No Content`.

## Orphaned Claims to Clean Up

The following test claims were created on the server but not captured in Terraform state and need manual release:

| Name | Resource Type | Environment | System |
|------|--------------|-------------|--------|
| `wus2tststsanmarnmtst` | `storage_account` | `tst` | `nmtst` |
| `wus2tstkvsanmarnmtst` | `key_vault` | `tst` | `nmtst` |

Release via API:
```bash
TOKEN=$(az account get-access-token \
  --scope "api://520a3d65-7b9a-4a1f-a399-caa56df4c68d/.default" \
  --query accessToken -o tsv)

for NAME in wus2tststsanmarnmtst wus2tstkvsanmarnmtst; do
  curl -s -X POST \
    -H "Authorization: Bearer ${TOKEN}" \
    -H "Content-Type: application/json" \
    -d "{\"name\": \"${NAME}\", \"region\": \"wus2\", \"environment\": \"tst\", \"reason\": \"orphaned by provider bug\"}" \
    "https://wus2-prd-fn-aznaming.azurewebsites.net/api/release"
  echo ""
done
```

## Verification

After fixing the provider and rebuilding:

1. Install the new binary in the filesystem mirror
2. Clean the test-claim state: `rm -rf .terraform .terraform.lock.hcl terraform.tfstate*`
3. Run: `terraform init && terraform apply -auto-approve && terraform destroy -auto-approve`
4. Full lifecycle should complete without errors

## Test-Claim Project

The test-claim project is at `environs-iac/sanmar/applications/internal/azure-naming/test-claim/`. It uses:
- `resource_type = "storage_account"` and `"key_vault"` (the two types with slug mappings)
- `environment = "tst"` (valid in the allowed_values list)
- `system = "nmtst"` (short enough to stay within the 24-char name limit)

## Related

- `.github/ISSUES/deploy-auth-fix-and-restore-function-app.md` — Function App deployment (resolved v1.8.1)
- `.github/ISSUES/enable-end-to-end-provider-testing.md` — Resource type coverage gaps
- `provider/client.go` — Source of the bug (line 195)
