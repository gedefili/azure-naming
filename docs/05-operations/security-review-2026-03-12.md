# Azure Naming Service — Security Review 2026-03-12

**Date:** 2026-03-12
**Scope:** Full repository — application code, infrastructure-as-code, CI/CD pipelines, dependencies, configuration, and tooling
**Reviewer:** Automated security analysis
**Prior audit:** [security-audit-2025-10-16.md](security-audit-2025-10-16.md) — this review expands on and supersedes those findings

---

## Executive Summary

This review identifies **36 security findings** across the Azure Naming Service codebase, covering application security, infrastructure configuration, CI/CD supply chain, and operational practices. The findings break down as:

| Severity | Count | Key Themes |
|----------|-------|------------|
| **Critical** | 2 | Auth bypass without production guard, metadata injection overwriting storage entities |
| **High** | 7 | Missing JWT issuer validation, dynamic code loading, unpinned CI actions, storage network exposure, access keys in config, client secret in Terraform outputs |
| **Medium** | 16 | OData injection, unbounded queries, anonymous auth levels, shell injection surface, silent audit failures, outdated actions, cert-skip flag, no deploy permissions |
| **Low** | 8 | Race conditions (mitigated), dead code, partition-key mismatch, information leaks |
| **Info** | 3 | Azurite dev keys, predictable GUIDs |

**Top 3 priorities for immediate remediation:**
1. Add a production guard on `ALLOW_LOCAL_AUTH_BYPASS` (C-01)
2. Filter entity metadata to prevent field overwrite injection (C-02)
3. Add JWT issuer validation (H-01)

---

## Category 1: Authentication & Authorization

### C-01 — Local Auth Bypass Without Production Guard
- **Severity:** CRITICAL
- **File:** `core/auth.py` (module-level constants + `require_role()`)
- **Description:** `ALLOW_LOCAL_AUTH_BYPASS` completely disables JWT authentication and grants configurable roles (default: `contributor,admin`). The flag is evaluated at import time and persists for the process lifetime. There is **no runtime check** to prevent this from activating in Azure. If `local.settings.json` is deployed or the env var is accidentally set, all endpoints become unauthenticated with admin privileges.
- **Vulnerable code:**
  ```python
  LOCAL_AUTH_BYPASS = _to_bool(os.environ.get("ALLOW_LOCAL_AUTH_BYPASS", ""))
  
  # In require_role():
  if LOCAL_AUTH_BYPASS:
      roles = LOCAL_BYPASS_ROLES  # grants full access
  ```
- **Recommendation:**
  ```python
  _is_azure = bool(os.environ.get("WEBSITE_INSTANCE_ID"))
  if LOCAL_AUTH_BYPASS and _is_azure:
      raise RuntimeError("ALLOW_LOCAL_AUTH_BYPASS must not be enabled in Azure")
  if LOCAL_AUTH_BYPASS:
      logging.warning("[auth] ⚠ Local auth bypass is ACTIVE — local dev only")
  ```

### H-01 — Missing JWT Issuer Validation
- **Severity:** HIGH
- **File:** `core/auth.py` → `verify_jwt()`
- **Description:** `jwt.decode()` validates audience and algorithm but does not validate the `issuer` claim. A JWT from a different Azure AD tenant that includes the correct audience would pass validation.
- **Vulnerable code:**
  ```python
  claims = jwt.decode(
      token, signing_key.key,
      algorithms=["RS256"],
      audience=CLIENT_ID or None,
      # issuer= is missing
  )
  ```
- **Recommendation:**
  ```python
  expected_issuer = f"https://login.microsoftonline.com/{TENANT_ID}/v2.0"
  claims = jwt.decode(
      token, signing_key.key,
      algorithms=["RS256"],
      audience=CLIENT_ID,
      issuer=expected_issuer,
      options={"require": ["exp", "iss", "aud"]},
  )
  ```

### H-02 — Dynamic Module Import from Environment Variables
- **Severity:** HIGH
- **Files:** `core/naming_rules.py` → `_load_provider_from_env()`, `core/slug_service.py`
- **Description:** `NAMING_RULE_PROVIDER` and `SLUG_PROVIDER` env vars are passed to `importlib.import_module()` without validation. If an attacker influences environment variables (compromised pipeline, SSRF to metadata service), this is arbitrary code execution.
- **Vulnerable code:**
  ```python
  module = importlib.import_module(module_path)  # arbitrary module
  factory = getattr(module, attr_name)
  ```
- **Recommendation:** Validate provider paths against an explicit allowlist of trusted modules.

### M-01 — PyJWKClient Instantiated Per Request
- **Severity:** MEDIUM
- **File:** `core/auth.py` → `verify_jwt()`
- **Description:** Every JWT validation call creates a new `PyJWKClient`, triggering an HTTP request to Microsoft's JWKS endpoint. Under load, this adds 100-300ms latency per request and creates DoS potential if the JWKS endpoint is slow.
- **Recommendation:** Cache the JWKS client at module level with `cache_keys=True, lifespan=3600`.

### M-02 — Anonymous Auth Level on Multiple Routes
- **Severity:** MEDIUM
- **Files:** `app/routes/rules.py`, `app/routes/slug.py`, `app/routes/docs.py`
- **Description:** Several routes override the app-level `FUNCTION` auth to `ANONYMOUS`. While they call `require_role()` internally, if C-01 (auth bypass) or EasyAuth misconfiguration occurs, these routes become completely public.
- **Recommendation:** Remove `auth_level=func.AuthLevel.ANONYMOUS` overrides; let the app-level `FUNCTION` key provide defense-in-depth.

### L-01 — Dead "manager" Role in Authorization
- **Severity:** LOW
- **File:** `core/auth.py` → `is_authorized()`
- **Description:** Checks for a `"manager"` role that doesn't exist in `ROLE_HIERARCHY` or `ROLE_ALIASES`. A token containing "manager" bypasses ownership checks even though the role is otherwise unknown.
- **Recommendation:** Remove the dead `"manager"` check or add it to the hierarchy.

### L-02 — Broad Exception Catch in JWT Validation
- **Severity:** LOW
- **File:** `core/auth.py`
- **Description:** `except (InvalidTokenError, Exception)` catches all errors including infrastructure failures. All are returned as 401, masking real issues.
- **Recommendation:** Catch `InvalidTokenError` → 401, catch `Exception` → 500 with distinct log messages.

---

## Category 2: Input Validation & Injection

### C-02 — Metadata Injection Overwrites Core Entity Fields
- **Severity:** CRITICAL
- **Files:** `adapters/storage.py` → `claim_name()`, `app/models.py`
- **Description:** `NameClaimRequest` uses `extra="allow"`, and `claim_name()` calls `entity.update(metadata)`. An attacker can submit `{"InUse": false, "ClaimedBy": "victim-id"}` to overwrite core entity fields in Table Storage.
- **Vulnerable code:**
  ```python
  entity = {"PartitionKey": ..., "RowKey": ..., "InUse": True, "ClaimedBy": ...}
  if metadata:
      entity.update(metadata)  # attacker-controlled keys overwrite above
  ```
- **Recommendation:**
  1. Change `NameClaimRequest` to `extra="forbid"` or `extra="ignore"`
  2. Filter metadata against a reserved-key blocklist before merging into the entity

### H-03 — OData Filter Injection in Audit Routes
- **Severity:** HIGH
- **File:** `app/routes/audit.py` → `_build_filter()`
- **Description:** The `start` and `end` datetime parameters are embedded into OData filters without escaping. Other string fields only double single-quotes, which may be insufficient for all OData operators. The `adapters/slug.py` `get_slug()` is similarly vulnerable — it constructs filters from user input with minimal escaping.
- **Recommendation:** Validate all filter inputs against strict patterns (alphanumeric + limited special chars), enforce max-length, and use parameterized queries where the Azure SDK supports them.

### M-03 — No Input Length Limits on Pydantic Models
- **Severity:** MEDIUM
- **File:** `app/models.py`
- **Description:** All string fields in `NameClaimRequest` lack `max_length` constraints. Extremely long strings flow through name generation, storage, and audit logging unchecked.
- **Recommendation:**
  ```python
  resource_type: str = Field(..., max_length=128)
  region: str = Field(..., max_length=32, pattern=r"^[a-z0-9]+$")
  environment: str = Field(..., max_length=32, pattern=r"^[a-z0-9]+$")
  ```

### M-04 — OData Injection in Slug Adapter
- **Severity:** MEDIUM
- **File:** `adapters/slug.py` → `get_slug()`
- **Description:** Constructs an OData filter `FullName eq '{human}' or ResourceType eq '{canonical}'` using minimally-escaped user input. Special OData operators or characters could manipulate the query.
- **Recommendation:** Validate input against `^[a-z0-9_.-]+$` before embedding in filters.

### M-05 — Unhandled ValueError in Audit Bulk
- **Severity:** MEDIUM
- **File:** `app/routes/audit.py`
- **Description:** `_build_filter()` raises `ValueError` for invalid datetimes, but the call is outside the `try/except` block — causing a 500 error with potential stack trace leak.
- **Recommendation:** Catch `ValueError` and return a 400 response.

### M-06 — No Pagination on Audit Queries
- **Severity:** MEDIUM
- **File:** `app/routes/audit.py` → `_query_audit_entities()`
- **Description:** `list(table.query_entities(...))` materializes all matching entities into memory with no limit. An attacker with reader access can trigger queries returning millions of records, causing OOM.
- **Recommendation:** Enforce a server-side maximum (e.g., 1000 results) using `results_per_page` and `itertools.islice`.

### L-03 — Name Generation Error Leaks Placeholder Names
- **Severity:** LOW
- **File:** `core/name_generator.py` → `build_name()`
- **Description:** `KeyError` is caught and re-raised as a `ValueError` that reveals template placeholder names, aiding reconnaissance.
- **Recommendation:** Return a generic error without exposing template internals.

### L-04 — Rule Enumeration via Distinct Error Responses
- **Severity:** LOW
- **File:** `app/routes/rules.py`
- **Description:** Returns 404 for unknown resource types vs. 200 for valid ones, enabling enumeration of supported resource types.
- **Recommendation:** Acceptable risk for a documentation-style endpoint, but consider rate limiting.

---

## Category 3: Data & Storage Security

### H-04 — Storage Account Missing Network Restrictions (IaC)
- **Severity:** HIGH
- **File:** `deploy/main.tf`
- **Description:** The `azurerm_storage_account` has no `network_rules` block. By default this allows access from all networks, including the public internet.
- **Recommendation:**
  ```hcl
  network_rules {
    default_action = "Deny"
    bypass         = ["AzureServices"]
  }
  public_network_access_enabled = false
  ```

### H-05 — Storage Access Keys in Function App Settings (IaC)
- **Severity:** HIGH
- **File:** `deploy/main.tf`
- **Description:** `STORAGE_CONNECTION_STRING` and `SANMAR_SLUGS_CONNECTION` contain the full storage account access key as plaintext app settings. The Function App has a managed identity but doesn't use it for storage access.
- **Recommendation:** Use managed identity with `Storage Table Data Contributor` RBAC role instead of connection strings.

### H-06 — Client Secret Exposed as Terraform Output
- **Severity:** HIGH
- **File:** `deploy/outputs.tf`
- **Description:** The Entra client secret is a Terraform output (marked sensitive but present in state). If state file leaks, the application credential is compromised.
- **Recommendation:** Remove this output. Store secrets in Azure Key Vault and access via managed identity.

### M-07 — Release Name Uses Wrong Partition Key Format
- **Severity:** MEDIUM (logic bug with security impact)
- **File:** `adapters/release_name.py`
- **Description:** Uses `{region}_{environment}` (underscore, no `.lower()`) while `storage.py` uses `{region.lower()}-{environment.lower()}` (hyphen, lowered). Releases will never find entities created by claims — names cannot be properly released.
- **Recommendation:** Normalize to `{region.lower()}-{environment.lower()}` across the codebase.

### M-08 — Claim Uses Upsert Instead of Create (Race Condition)
- **Severity:** MEDIUM
- **File:** `adapters/storage.py` → `claim_name()`
- **Description:** Uses `upsert_entity` with `MERGE` mode instead of `create_entity`. Combined with the TOCTOU gap (check-then-claim), two concurrent requests can overwrite each other's claims.
- **Recommendation:** Use `create_entity()` which fails atomically on conflict. Remove the pre-existence check and handle `ResourceExistsError`.

### M-09 — Release Endpoint Lacks ETag Concurrency
- **Severity:** MEDIUM
- **File:** `app/routes/names.py` → `release_name`
- **Description:** Entity is retrieved and written back with `mode="Replace"` but no ETag check. Stale replays can overwrite `ReleasedBy` and `ReleasedAt`, corrupting audit integrity.
- **Recommendation:** Include the entity's ETag in the replace operation and handle conflicts.

### M-10 — Audit Log Write Fails Silently
- **Severity:** MEDIUM
- **File:** `adapters/audit_logs.py` → `write_audit_log()`
- **Description:** If audit writing fails, the exception is logged but the calling code is not notified. Actions proceed without audit records — violating audit trail integrity.
- **Recommendation:** Re-raise or return a status. For security-critical operations (claims), fail the operation if audit logging fails.

---

## Category 4: CI/CD & Supply Chain

### H-07 — Unpinned GitHub Actions (Supply Chain Risk)
- **Severity:** HIGH
- **Files:** All `.github/workflows/*.yml`
- **Description:** All GitHub Actions are referenced by mutable tag (`@v1`, `@v2`, `@v3`, `@v4`) instead of pinned SHA hashes. A compromised upstream action silently injects malicious code into every CI run.
- **Recommendation:** Pin every action to its full SHA commit hash:
  ```yaml
  - uses: actions/checkout@b4ffde65f46336ab88eb53be808477a3936bae11  # v4.1.1
  ```

### M-11 — deploy.yml Uses Legacy Service Principal Auth
- **Severity:** MEDIUM
- **File:** `.github/workflows/deploy.yml`
- **Description:** `azure/login@v1` with `creds: ${{ secrets.AZURE_CREDENTIALS }}` uses a long-lived service principal secret. If the secret leaks, the attacker has persistent Azure access.
- **Recommendation:** Switch to OIDC (workload identity federation) with short-lived tokens via `azure/login@v2`.

### M-12 — deploy.yml Missing Permissions Block and Environment Protection
- **Severity:** MEDIUM
- **File:** `.github/workflows/deploy.yml`
- **Description:** No `permissions:` block (workflow gets default broad token permissions) and no `environment:` with required reviewers. Any push to `main` triggers an unreviewed production deployment.
- **Recommendation:**
  ```yaml
  permissions:
    contents: read
    id-token: write
  jobs:
    build-and-deploy:
      environment: production
  ```

### M-13 — Outdated GitHub Actions Versions
- **Severity:** MEDIUM
- **Files:** `.github/workflows/deploy.yml`, `.github/workflows/codeql.yml`
- **Description:** `actions/checkout@v3`, `azure/login@v1`, and `github/codeql-action/*@v2` are deprecated and no longer receive security patches.
- **Recommendation:** Update to latest major versions (and pin to SHA).

---

## Category 5: Secrets & Configuration

### M-14 — TLS Certificate Verification Skip in Config
- **Severity:** MEDIUM
- **File:** `local.settings.json`
- **Description:** `AZURE_FUNCTIONS_SKIP_CERT_VERIFICATION: "1"` disables TLS verification. If this reaches production, MITM attacks are possible on all outbound HTTPS.
- **Recommendation:** Add a startup guard that refuses this setting when running on Azure (check `WEBSITE_INSTANCE_ID`).

### M-15 — Sensitive Data in Debug Logs
- **Severity:** MEDIUM
- **File:** `core/auth.py`
- **Description:** Full JWT claims and decoded client principals are logged at DEBUG level. These contain PII (user IDs, email, group memberships). Application Insights may capture DEBUG logs.
- **Recommendation:** Log only non-sensitive metadata: `logging.debug("[auth] Verified JWT for oid=%s", claims.get("oid"))`.

### M-16 — Dev Dependencies in Production requirements.txt
- **Severity:** MEDIUM
- **File:** `requirements.txt`
- **Description:** `debugpy==1.8.17` and `pytest==8.3.3` are included in the main requirements file. `debugpy` opens a debug port that allows remote code execution if activated. Both are bundled into the production deployment artifact.
- **Recommendation:** Separate into `requirements-dev.txt` and install only `requirements.txt` in production.

---

## Category 6: Infrastructure as Code

### M-17 — Function App Has No IP Restrictions or WAF
- **Severity:** MEDIUM
- **File:** `deploy/main.tf`
- **Description:** No `ip_restriction` blocks in `site_config`. The function is publicly accessible from the internet without network-level filtering.
- **Recommendation:** Add `ip_restriction` blocks for known networks, or deploy Azure Front Door / API Management with WAF.

### I-01 — Terraform State Not Configured for Remote Backend
- **Severity:** INFO
- **File:** `deploy/providers.tf`
- **Description:** Backend is commented out; state is stored locally containing all secrets. No locking for multi-user scenarios.
- **Recommendation:** Enable the Azure remote backend with encryption at rest.

### I-02 — Predictable GUIDs for App Roles
- **Severity:** INFO
- **File:** `deploy/entra.tf`
- **Description:** OAuth2 scope and app role IDs use obvious placeholder GUIDs (`00000000-...`, `11111111-...`). While not directly exploitable, predictable IDs could be used in token-crafting attempts.
- **Recommendation:** Generate random UUIDs.

### I-03 — Entra App Password Timestamp Drift
- **Severity:** INFO
- **File:** `deploy/entra.tf`
- **Description:** `end_date = timeadd(timestamp(), "8760h")` changes on every plan, causing unnecessary secret rotation churn.
- **Recommendation:** Use a `time_static` resource and add `lifecycle { ignore_changes = [end_date] }`.

---

## Category 7: Tooling & Local Development

### M-18 — Shell Injection Surface in Process Utilities
- **Severity:** MEDIUM
- **File:** `tools/lib/process_utils.py`
- **Description:** `kill_process_by_port` uses `shell=True` with string interpolation. The `run_command` function accepts `shell=True` as a parameter. While current callers don't pass user input, the interface is dangerous.
- **Recommendation:** Validate PIDs are strictly numeric, use list-form `subprocess.run()`, and remove `shell=True` support.

### L-05 — MCP Server Has No Authentication
- **Severity:** LOW
- **File:** `tools/mcp_server/server.py`
- **Description:** The MCP server processes JSON-RPC over stdin/stdout with no authentication (default user = `"system"`). Acceptable for local dev but must never be network-exposed.
- **Recommendation:** Add a startup warning and ensure it binds only to stdio.

### L-06 — Slug Fetcher Trusts Upstream Without Verification
- **Severity:** LOW
- **Files:** `adapters/slug_fetcher.py`, `adapters/slug_loader.py`
- **Description:** Slug definitions are downloaded from a hardcoded GitHub URL with no signature or hash verification. A compromised upstream can inject malicious slug mappings.
- **Recommendation:** Add content hash verification or pin to a specific commit SHA.

### L-07 — Storage Connection Cached Without Rotation Handling
- **Severity:** LOW
- **File:** `adapters/storage.py` → `_get_service()`
- **Description:** A single `TableServiceClient` is cached at module level. If credentials rotate, the service must restart.
- **Recommendation:** Acceptable for short-lived Function App processes, but document the constraint.

### L-08 — InMemorySettingsRepository Has No Eviction
- **Severity:** LOW
- **File:** `core/user_settings.py`
- **Description:** No eviction of stale session data; potential unbounded memory growth in long-lived processes.
- **Recommendation:** Add a TTL or LRU eviction policy, or accept as low-risk for short-lived consumption plan instances.

---

## Remediation Priority Matrix

| Priority | ID | Finding | Effort |
|----------|----|---------|--------|
| **P0 — Immediate** | C-01 | Auth bypass production guard | Small |
| **P0 — Immediate** | C-02 | Metadata injection blocklist | Small |
| **P0 — Immediate** | H-01 | JWT issuer validation | Small |
| **P1 — This Sprint** | H-02 | Provider import allowlist | Small |
| **P1 — This Sprint** | H-03 | OData filter input validation | Medium |
| **P1 — This Sprint** | H-04 | Storage network restrictions | Small |
| **P1 — This Sprint** | H-05 | Managed identity for storage | Medium |
| **P1 — This Sprint** | H-06 | Remove secret from TF outputs | Small |
| **P1 — This Sprint** | H-07 | Pin GitHub Actions to SHA | Small |
| **P2 — Next Sprint** | M-01–M-18 | All medium findings | Varies |
| **P3 — Backlog** | L-01–L-08, I-01–I-03 | Low and info findings | Small |

---

## Comparison with Prior Audit (2025-10-16)

The [prior security audit](security-audit-2025-10-16.md) identified many of the same patterns. Key differences in this review:

| Aspect | 2025-10-16 Audit | This Review |
|--------|------------------|-------------|
| **Scope** | Application code only | Full repo: app + IaC + CI/CD + tooling + deps |
| **IaC coverage** | Not reviewed (didn't exist) | 6 findings in Terraform config |
| **CI/CD coverage** | Not reviewed | 5 findings in GitHub Actions |
| **Dependency audit** | Not reviewed | debugpy in prod, unpinned actions |
| **Metadata injection** | Noted as `extra="allow"` | Elevated to Critical with exploitation path |
| **Auth bypass** | Noted as High | Elevated to Critical: no production guard exists |
| **Remediation guidance** | Findings only (no fixes) | Each finding includes concrete fix code |

---

## Methodology

- **Static analysis:** Manual review of all Python source, Terraform HCL, YAML pipelines, and JSON config
- **OWASP Top 10 mapping:** Each finding mapped against the 2021 OWASP Top 10 categories
- **Threat model:** API-facing attack surface (authenticated users with valid tokens), CI/CD supply chain, infrastructure misconfiguration, insider/deployment accidents
- **Tools:** Code reading, grep-based pattern analysis, Terraform validation
