# Issue Remediation Report — 2026-04-16

## Summary

Assessed all five documents in `.github/ISSUES/`. Three were already remediated,
one required code fixes, and two are operational utility scripts (not issues).

| # | Document | Type | Status |
|---|----------|------|--------|
| 1 | `fix-auth-level-for-terraform-provider.md` | Bug | **Already remediated** |
| 2 | `provider-rejects-201-created-status.md` | Bug | **Fixed in this session** |
| 3 | `automate-post-deploy-slug-sync.md` | Enhancement | **Already remediated** |
| 4 | `publish-provider-acr.sh` | Utility script | N/A — not an issue |
| 5 | `pull-provider-acr.sh.sh` | Utility script | N/A — not an issue |

## Issue Details

### 1. fix-auth-level-for-terraform-provider.md — REMEDIATED

**Problem:** `AuthLevel.FUNCTION` in `app/__init__.py` blocked Bearer token
authentication, causing the Terraform provider to receive 401 before
application code ran.

**Current state:** `app/__init__.py` already uses `AuthLevel.ANONYMOUS` with
the correct docstring. All routes call `require_role()` for JWT-based auth.
No action needed.

### 2. provider-rejects-201-created-status.md — FIXED

**Problem:** The Terraform provider's `ClaimName` method in
`provider/client.go` only accepted HTTP 200, but the `/api/claim` endpoint
correctly returns HTTP 201 Created. This caused `terraform apply` to report
an error even though the claim was created server-side, orphaning claims.

**Root cause:** Two bugs in `provider/client.go`:

1. `ClaimName` status check: `resp.StatusCode != http.StatusOK` rejected 201.
2. `doRequest` retry logic: the early-return condition `resp.StatusCode < 500`
   returned 429 Too Many Requests responses immediately instead of retrying,
   since 429 < 500.

**Fixes applied:**

- **`provider/client.go` line ~196** — `ClaimName` now accepts both 200 and 201:
  ```go
  if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusCreated {
  ```

- **`provider/client.go` line ~104** — `doRequest` early-return now excludes 429:
  ```go
  if err == nil && resp.StatusCode < 500 && resp.StatusCode != http.StatusTooManyRequests {
  ```

**Verification:**
- Go build: passed
- Go tests: all passed (including `TestRetryLogic` which was previously failing)
- Python tests: 260 passed

### 3. automate-post-deploy-slug-sync.md — REMEDIATED

**Problem:** Deployments did not trigger slug sync, leaving newly deployed
environments without slug data until a manual call or the weekly timer.

**Current state:** `azure-pipelines.yml` deploy stage already includes
post-deploy slug sync logic — acquires a bearer token, calls
`POST /api/slug_sync` with retries, and fails the pipeline if sync doesn't
succeed. The issue document itself notes resolution in v1.8.2.

### 4–5. Shell Scripts (publish/pull-provider-acr.sh)

These are operational utility scripts for publishing and pulling the Terraform
provider binary to/from ACR via ORAS. They were misplaced in `.github/ISSUES/`.
Moved to `tools/` as `publish_provider_acr.sh` (already existed) and
`pull_provider_acr.sh` (created from the ISSUES draft with updated headers).
The originals have been deleted from `.github/ISSUES/`. Documentation added
in `tools/PROVIDER_ACR_README.md`.

## Files Changed

| File | Change |
|------|--------|
| `terraform-provider-sanmar/provider/client.go` | Accept 201 in `ClaimName`; fix 429 retry bypass in `doRequest` |
| `tools/pull_provider_acr.sh` | New — moved from `.github/ISSUES/pull-provider-acr.sh.sh` with updated headers |
| `tools/PROVIDER_ACR_README.md` | New — documents publish/pull ACR scripts |
| `.github/ISSUES/publish-provider-acr.sh` | Deleted — superseded by `tools/publish_provider_acr.sh` |
| `.github/ISSUES/pull-provider-acr.sh.sh` | Deleted — superseded by `tools/pull_provider_acr.sh` |
