# ops(cleanup): Orphaned test claims from provider v1.1.0 201 bug

## Summary

Two test claims created during provider v1.1.0 testing remain held in the
naming service. They were created server-side (201 response) but never recorded
in Terraform state due to the 201-rejection bug in `ClaimName`. Subsequent
test runs with the fixed v1.2.0 provider hit **409 Conflict** because these
names are already claimed.

## Orphaned Claims

| Claimed Name | Resource Type | Region | Environment | System |
|--------------|---------------|--------|-------------|--------|
| `wus2tststsanmarnmtst` | `storage_account` | `wus2` | `tst` | `nmtst` |
| `wus2tstkvsanmarnmtst` | `key_vault` | `wus2` | `tst` | `nmtst` |

## Error During v1.2.0 Testing

```
│ Error: Failed to claim name
│
│   with sanmar_claim.this["storage_account"],
│   on main.tf line 60, in resource "sanmar_claim" "this":
│   60: resource "sanmar_claim" "this" {
│
│ unexpected status 409: Name 'wus2tststsanmarnmtst' is already in use.
```

## Required Action

Release these names via the naming service API:

```bash
TOKEN=$(az account get-access-token \
  --scope "api://520a3d65-7b9a-4a1f-a399-caa56df4c68d/.default" \
  --query accessToken -o tsv)

for NAME in wus2tststsanmarnmtst wus2tstkvsanmarnmtst; do
  curl -s -X POST \
    -H "Authorization: Bearer ${TOKEN}" \
    -H "Content-Type: application/json" \
    -d "{\"name\": \"${NAME}\", \"region\": \"wus2\", \"environment\": \"tst\", \"reason\": \"orphaned by provider v1.1.0 bug — 201 rejection\"}" \
    "https://wus2-prd-fn-aznaming.azurewebsites.net/api/release"
  echo ""
done
```

## Verification

After releasing the orphaned names:

1. Re-run `terraform apply -auto-approve` in the test-claim fixture
2. `storage_account` and `key_vault` claims should now succeed (201)
3. Run `terraform destroy -auto-approve` to clean up

## Context

- Original bug: `.github/ISSUES/provider-null-slug-and-201-status-bugs.md` (Bug 2)
- Fix applied in provider v1.2.0 (commit `fc9aad3`)
- The 201 fix is confirmed working — 17 of 19 claims succeeded in v1.2.0 testing
- Only these 2 legacy orphans remain from the v1.1.0 testing cycle
