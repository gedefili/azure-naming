# bug(provider): Null object on missing slugs + ClaimName rejects HTTP 201 Created

## Outcome

Status: Remediated in source on 2026-04-16.

Implemented changes:

- `terraform-provider-sanmar/provider/data_source_slug.go` now returns an explicit provider diagnostic when a slug mapping does not exist, instead of removing state and producing a Terraform null object failure.
- `terraform-provider-sanmar/provider/client.go` now accepts `201 Created` from `POST /api/claim` and `204 No Content` from `POST /api/release`.
- `terraform-provider-sanmar/provider/client.go` also fixes an additional retry defect discovered during verification: `429 Too Many Requests` is now retried instead of being returned immediately.
- `adapters/slug_fetcher.py` now layers local overrides on top of the upstream Azure naming spec so the eight missing resource types resolve during slug sync.
- `azure-pipelines.yml` now includes a `publish_provider` stage triggered by `provider-v*` tags so provider releases are published to ACR via CI/CD instead of requiring a manual local publish.
- `terraform-provider-sanmar/VERSION` was added and set to `1.2.0` for source-controlled provider versioning.

## Summary

Testing the `sanmar/naming` Terraform provider **v1.1.1** against the test-claim
fixture (`environs-iac/sanmar/applications/internal/azure-naming/test-claim/`)
revealed two provider-level bugs that block the full claim lifecycle.

---

## Bug 1: Provider produces null object for unmapped resource types

### Problem

When `data.sanmar_slug` queries a resource type that has no slug mapping in the
naming service, the provider returns a **null object** instead of an empty result
or a diagnostic error. Terraform's plugin framework treats null data source
results as a provider bug and halts the plan.

### Symptoms

```
│ Warning: Slug not found
│
│   with data.sanmar_slug.this["app_service"],
│   on main.tf line 49, in data "sanmar_slug" "this":
│   49: data "sanmar_slug" "this" {
│
│ No slug mapping returned for resource type app_service
╵
╷
│ Error: Provider produced null object
│
│ Provider "provider[\"registry.terraform.io/sanmar/naming\"]" produced a null
│ value for data.sanmar_slug.this["app_service"].
│
│ This is a bug in the provider, which should be reported in the provider's own
│ issue tracker.
╵
```

### Affected resource types (8 of 22 tested)

| Resource Type | Expected Slug |
|---------------|---------------|
| `app_service` | `app` |
| `container_registry` | `cr` |
| `cosmosdb_account` | `cosmos` |
| `managed_identity` | `id` |
| `private_dns_zone` | `pdnsz` |
| `public_ip_address` | `pip` |
| `sql_database` | `sqldb` |
| `sql_server` | `sql` |

### Successful resource types (14 of 22 tested)

`app_service_plan`, `application_insights`, `container_app`,
`container_app_environment`, `function_app`, `key_vault`,
`log_analytics_workspace`, `network_interface`, `network_security_group`,
`private_endpoint`, `resource_group`, `storage_account`, `subnet`,
`virtual_network`

### Root Cause

`provider/data_source_slug.go` — when the naming service returns no mapping for
a resource type, the provider sets the data source state to `nil` instead of
returning a populated (but empty) state object or an error diagnostic.

The Terraform plugin framework requires that `Read` always sets the state to a
non-nil value for data sources. Returning nil tells Terraform the object does
not exist, which is a protocol violation for data sources.

### Required Fix

Implemented.

In `provider/data_source_slug.go`, when no slug mapping is found:

**Option A (preferred):** Return an error diagnostic so the user knows the
resource type is not supported:

```go
resp.Diagnostics.AddError(
    "Slug not found",
    fmt.Sprintf("No slug mapping for resource type %q", resourceType),
)
return
```

**Option B:** Return a populated state with empty slug and a warning:

```go
data.Slug = types.StringValue("")
data.Id = types.StringValue(fmt.Sprintf("slug:%s", resourceType))
resp.Diagnostics.AddWarning(
    "Slug not found",
    fmt.Sprintf("No slug mapping returned for resource type %s", resourceType),
)
resp.State.Set(ctx, &data)
```

### Workaround

Limit `for_each` in the test-claim fixture to only the 14 resource types that
have slug mappings in the naming service. This avoids the null object error but
does not fix the provider.

---

## Bug 2: ClaimName rejects HTTP 201 Created (carried forward from v1.1.0)

### Problem

The `ClaimName` method in `provider/client.go` (line 195) only accepts
HTTP 200 OK. The `/api/claim` endpoint correctly returns HTTP 201 Created on
successful claim creation, so the provider treats every successful claim as an
error.

### Symptoms

- `terraform plan` succeeds (slug data sources return 200)
- `terraform apply` creates the claim server-side (201 response with full JSON
  payload) but the provider reports an error
- Claims are created on the server but **not recorded in Terraform state**,
  producing orphaned names
- Subsequent `terraform apply` attempts may create duplicate claims

### Root Cause

`provider/client.go` line 195:

```go
if resp.StatusCode != http.StatusOK {
    return nil, decodeError(resp)
}
```

### Required Fix

```go
if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusCreated {
    return nil, decodeError(resp)
}
```

Also audit `ReleaseName` (line 227) — the `/api/release` endpoint may return
`204 No Content` on successful release.

### Status

Implemented in source. The `ClaimName` client now accepts `200 OK` and
`201 Created`, and `ReleaseName` accepts `200 OK` and `204 No Content`.
The previous `v1.1.1` binary still exhibits the bug until a new provider
release is published.

---

## Missing slug mappings (service-side)

Independent of the provider bugs, the naming service was missing slug mappings
for 8 common Azure resource types from the upstream source. This is now
remediated in source by adding local override mappings during slug sync, so the
service can resolve these resource types even when the upstream Azure naming
spec does not define them.

The following overrides are now added during slug sync:

- `app_service`
- `container_registry`
- `cosmosdb_account`
- `managed_identity`
- `private_dns_zone`
- `public_ip_address`
- `sql_database`
- `sql_server`

---

## Test Environment

| Component | Value |
|-----------|-------|
| Provider version | `sanmar/naming` v1.1.1 |
| Terraform version | v1.14.8 on linux_amd64 |
| Test fixture | `environs-iac/sanmar/applications/internal/azure-naming/test-claim/` |
| Naming service endpoint | `https://wus2-prd-fn-aznaming.azurewebsites.net` |
| Date tested | 2026-04-16 |

## Verification

Completed verification in this repository:

1. `go test ./provider/...` passed in `terraform-provider-sanmar/` after the fixes.
2. `pytest tests/test_adapters_extended.py -q` passed, including the new local slug override coverage.
3. `pytest tests/test_utils.py -q` passed, confirming slug sync still stores canonical resource type values.

Additional release path implemented:

4. `azure-pipelines.yml` now publishes the provider when a `provider-v*` tag is pushed.
5. The intended release tag for this remediation is `provider-v1.2.0`.

Not completed in this repository session:

6. End-to-end Terraform apply/destroy against the external `test-claim` fixture was not run here because that fixture lives outside this workspace and requires external environment access.

## Related

- `.github/ISSUES/fix-auth-level-for-terraform-provider.md` — Auth level fix (resolved)
- `provider/client.go` — 201 status bug (line 195)
- `provider/data_source_slug.go` — Null object bug

## Release Notes

To publish the remediated provider through CI/CD:

1. Merge the PR into `main`.
2. Create an annotated tag `provider-v1.2.0` on the merge commit.
3. Push the tag so Azure DevOps runs the `publish_provider` stage and publishes `sanmar/naming:1.2.0` to ACR.
