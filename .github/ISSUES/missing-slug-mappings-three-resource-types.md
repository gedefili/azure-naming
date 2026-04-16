# gap(slugs): Missing slug mappings for 3 resource types

## Summary

Testing the `sanmar/naming` Terraform provider **v1.2.0** against the
test-claim fixture with 22 common Azure resource types found that **3 types**
have no slug mapping in the naming service. The provider correctly returns an
error diagnostic (the null-object bug from v1.1.1 is fixed), but these types
cannot be used until slugs are added.

## Missing Resource Types

| Resource Type | Expected Slug | CAF Abbreviation |
|---------------|---------------|------------------|
| `container_app` | `ca` | `ca` |
| `container_app_environment` | `cae` | `cae` |
| `subnet` | `snet` | `snet` |

## Context

The slug sync source was recently switched to Microsoft CAF abbreviations
(commit `533bac1`). These three types either:
- are not present in the CAF abbreviation list under the keys the sync uses, or
- use a different resource type key format than what the sync expects

The previous test run (v1.1.1) showed 8 missing types. The CAF sync fixed 5 of
them (`app_service`, `container_registry`, `cosmosdb_account`,
`managed_identity`, `private_dns_zone`, `public_ip_address`, `sql_database`,
`sql_server`) but these 3 remain.

## Successful Resource Types (19 of 22)

`app_service`, `app_service_plan`, `application_insights`, `container_registry`,
`cosmosdb_account`, `function_app`, `key_vault`, `log_analytics_workspace`,
`managed_identity`, `network_interface`, `network_security_group`,
`private_dns_zone`, `private_endpoint`, `public_ip_address`, `resource_group`,
`sql_database`, `sql_server`, `storage_account`, `virtual_network`

## Provider Behaviour

With v1.2.0, the provider correctly returns an error diagnostic instead of a
null object:

```
│ Error: Failed to lookup slug
│
│   with data.sanmar_slug.this["subnet"],
│   on main.tf line 49, in data "sanmar_slug" "this":
│   49: data "sanmar_slug" "this" {
│
│ no slug mapping exists for resource type "subnet"
```

This is the correct behaviour — the null-object bug from v1.1.1 is resolved.

## Required Fix

Add slug mappings for these 3 resource types to the slug sync source or as
manual entries in Azure Table Storage:

```
container_app           → ca
container_app_environment → cae
subnet                  → snet
```

If these are missing from the CAF abbreviation list, add them as manual
overrides in the `SlugMappings` table.

## Test Environment

| Component | Value |
|-----------|-------|
| Provider version | `sanmar/naming` v1.2.0 |
| Terraform version | v1.14.8 on linux_amd64 |
| Test fixture | `environs-iac/sanmar/applications/internal/azure-naming/test-claim/` |
| Naming service | `https://wus2-prd-fn-aznaming.azurewebsites.net` |
| Date tested | 2026-04-16 |

## Verification

After adding the 3 slug mappings:

1. Trigger a slug sync or add entries manually
2. Re-run: `terraform init && terraform apply -auto-approve && terraform destroy -auto-approve`
3. All 22 resource types should complete the full lifecycle

## Related

- `.github/ISSUES/provider-null-slug-and-201-status-bugs.md` — previous test run findings (v1.1.1)
- `commit 533bac1` — CAF slug sync source switch
