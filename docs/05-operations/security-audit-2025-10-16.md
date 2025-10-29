# Azure Naming Service Security Audit

**Date:** 2025-10-16  
**Scope:** Application source code under `app/`, `core/`, `adapters/`, and supporting providers. Review performed at function or method granularity with a focus on security weaknesses, misuse of platform controls, and unsafe data handling. Findings list potential issues only (no remediation steps). All severity assessments are relative (High/Medium/Low) and qualitative.

---

## Module Reviews

### `core/auth.py`
- **Module overview:** JWT validation, role resolution, and local bypass helpers for Azure EasyAuth integration.
- **Function `_load_role_groups`** – *Low*: silently ignores missing environment variables, which can hide configuration drift that leaves group-based authorization non-functional.
- **Function `parse_client_principal`** – *Medium*: logs the full decoded principal (`logging.debug`) including PII and potentially tokens when debug logging is enabled; risk of credential leakage if debug logs are collected in lower environments.
- **Function `verify_jwt`** – *Medium*: creates a new `PyJWKClient` per request without caching, exposing the service to repeated outbound calls and potential availability issues (resource exhaustion/DoS) if the JWKS endpoint is slow; also treats any exception as `Invalid token`, masking configuration faults.
- **Function `require_role`** – *High*: `LOCAL_AUTH_BYPASS` enables unconditional authorization on any caller if the environment variable is set; lacks guardrails to prevent activation in production and returns HTTP 200 even when bypass is active, which could be misconfigured accidentally.
- **Function `get_user_roles`** – *Low*: depends on preconfigured group IDs; absence of IDs silently results in empty role list, potentially denying legitimate users without clear monitoring.
- **Function `is_authorized`** – *Medium*: includes `manager` as an allowed role though `ROLE_HIERARCHY` excludes it, meaning a token containing `manager` bypasses resource ownership checks even though that role is otherwise unknown.

### `core/name_service.py`
- **Module overview:** Generates compliant names, validates conflicts, persists claims, and emits audit logs.
- **Function `_normalise_payload`** – *Low*: no length/character normalization on optional fields before they join the name; relies entirely on downstream rule validation which may miss context-specific constraints (e.g., project names containing hyphen clusters).
- **Function `generate_and_claim_name`** – *High*: uses `check_name_exists` then `claim_name` with an `upsert` write; this is not atomic and allows a race condition where two requests can claim the same name simultaneously, breaking uniqueness guarantees claimed in API contracts.

### `core/name_generator.py`
- **Module overview:** Renders names based on templates or segment lists.
- **Function `build_name`** – *Low*: template rendering catches `KeyError` but returns a generic `ValueError` message that reveals placeholder names to callers; small information leak but useful for attackers crafting payloads.

### `core/naming_rules.py`
- **Module overview:** Loads and exposes naming rules from JSON layers and optional providers.
- **Function `_load_provider_from_env`** – *Medium*: imports arbitrary module path from environment without sandboxing; if environment variables are attacker-controlled (CI or compromised configuration), arbitrary code execution is possible on function startup.
- **Function `_sync_shared_state`** – *Low*: stores global copies of rules without thread safety; concurrent reloads could observe partially populated dictionaries (unlikely under normal usage but possible in multi-worker scenarios).
- **Function `describe_rule`** – *Low*: error message leaks full list of available resource types in `KeyError`, aiding reconnaissance.

### `core/slug_service.py`
- **Module overview:** Manages the slug provider chain.
- **Function `_load_providers_from_env` / `register_slug_provider`** – *Medium*: Accepts callable paths from environment and executes them immediately; similar arbitrary code execution vector when environment is untrusted.
- **Function `get_slug`** – *High*: Propagates exceptions from providers, potentially disclosing internal provider errors (connection strings, stack traces) to API callers when unhandled.

### `core/user_settings.py`
- **Module overview:** Manages persistent and session-based default settings for users.
- **Class `InMemorySettingsRepository`** – *Low*: No eviction of stale session data beyond manual deletion; potential unbounded memory growth in long-lived processes.
- **Class `TableStorageSettingsRepository`** – *Medium*: Returns entire entity contents including unexpected keys (besides reserved fields); if attackers insert malicious entries with sensitive data, they are echoed back in defaults without validation.
- **Method `UserSettingsService.apply_defaults`** – *Low*: Overwrites falsy values (`""`, `0`) from payload with stored defaults, possibly bypassing client attempts to clear defaults.

### `core/validation.py`
- **Module overview:** Basic validation for generated names.
- **Function `validate_name`** – *Low*: Does not enforce minimum length or segment-specific rules; relies entirely on naming rules, which may allow short or ambiguous names if misconfigured.

### `app/dependencies.py`
- **Module overview:** Re-exports services and Azure SDK placeholders for use in routes.
- **Module-level behavior** – *Low*: Falls back to stub `AzureError`/`ResourceNotFoundError` classes when SDK missing, which could cause logic to treat serious connection failures as ordinary not-found errors without logging.

### `app/errors.py`
- **Module overview:** Converts exceptions to HTTP responses.
- **Function `handle_name_generation_error`** – *Medium*: Logs full stack traces for all unexpected exceptions, potentially exposing secrets or user payloads in central logging systems.

### `app/models.py`
- **Module overview:** Pydantic schemas for request/response bodies.
- **Model `NameClaimRequest`** – *Low*: `extra="allow"` means arbitrary fields are accepted and passed through, potentially triggering unexpected behavior downstream (stored metadata, logging of sensitive info).
- **Model `SlugLookupResponse`** – *Low*: Allows arbitrary extra fields to be returned; malicious metadata pulled from storage can surface directly to clients.

### `app/responses.py`
- **Module overview:** JSON response helpers.
- **Function `build_claim_response`** – *Low*: Does not enforce string encoding on display entries; relies on `NameGenerationResult` to sanitize.

### `app/routes/names.py`
- **Module overview:** HTTP endpoints for claiming and releasing names.
- **Function `_handle_claim_request`** – *Medium*: Accepts arbitrary JSON (no schema validation) and hands it to business logic; combined with `extra="allow"` this permits injection of unexpected fields that may influence defaults or logs.
- **Function `claim_name`** – *Medium*: Auth level is anonymous in host configuration; relies entirely on custom header enforcement. If EasyAuth is disabled/misconfigured, the endpoint becomes unauthenticated.
- **Function `release_name`** – *High*: Retrieves entity and writes back with `mode="Replace"` without ETag concurrency checks; attackers can replay stale updates to overwrite `ReleasedBy` and `ReleasedAt`, compromising audit integrity. Also writes user-controlled `reason` directly to storage without validation (potential for log injection when consumed elsewhere).

### `app/routes/audit.py`
- **Module overview:** Exposes audit information via queryable endpoints.
- **Function `_build_filter`** – *High*: `start` and `end` parameters are embedded into OData filters without escaping; an attacker can inject arbitrary OData clauses, leading to data exfiltration or query abuse. Other string fields are sanitized only by doubling single quotes, which may still be bypassed for other metacharacters.
- **Function `_query_audit_entities`** – *Low*: `list_entities` without pagination could leak excessive data and exhaust memory, permitting DoS via broad queries.
- **Function `audit_bulk`** – *Medium*: Relies on caller-supplied `user` parameter for authorization check; timing differences reveal whether a user ID exists in logs (user enumeration). Also returns all metadata fields without scrubbing, which can leak project/system identifiers.

### `app/routes/slug.py`
- **Module overview:** Slug lookup and synchronization endpoints.
- **Function `_resolve_slug_payload`** – *High*: Calls `core.slug.get_slug`, which in turn builds a query using unsanitized input (see adapter finding); permits injection into Table queries. Metadata hydration suppresses some personally identifiable keys but not others; any new field stored server-side will be reflected to clients without approval.
- **Function `_perform_slug_sync`** – *Medium*: Trusts upstream GitHub data blindly; a compromised upstream repository can overwrite local slug mappings with malicious values that influence resource naming. Exception handler catches all errors and performs upsert, disguising real failures.
- **Function `slug_lookup`** – *Medium*: Auth level `ANONYMOUS`; if `require_role` fails open due to bypass env, this route is publicly queriable.
- **Function `slug_sync`** – *Low*: Returns minimal detail on failure, hindering detection of misconfiguration (blind spot rather than vulnerability).
- **Function `slug_sync_timer`** – *Low*: No safeguards against repeated failures; could thrash storage when upstream is consistently unavailable.

### `app/routes/docs.py`
- **Module overview:** Serves OpenAPI JSON and Swagger UI.
- **Function `_normalise_openapi_spec`** – *Low*: Adds `/api` server entry even when spec already contains external URLs, potentially misleading clients into targeting the wrong origin.
- **Function `openapi_spec`** – *Medium*: Auth level `ANONYMOUS`; exposes complete API surface (including error responses) to unauthorized users if `require_role` bypass is active.

### `app/routes/rules.py`
- **Module overview:** Exposes naming rules over HTTP.
- **Function `list_naming_rules`** – *Low*: Returns entire rule structures (`expand=details`) without redaction; if naming rules contain internal comments or metadata, they are exposed to callers.
- **Function `get_naming_rule`** – *Low*: Distinguishes unknown vs known resource types clearly (404 vs 200), enabling enumeration.

### `adapters/storage.py`
- **Module overview:** Azure Table helpers for names.
- **Function `_get_service`** – *Medium*: Reuses a single `TableServiceClient` instance without renewing connection strings; if credentials rotate, service must restart, otherwise operations may fail unpredictably.
- **Function `get_table_client`** – *Low*: Creates table if missing without confirmation of caller intent; could allow privilege escalation if attacker guesses table names.
- **Function `check_name_exists`** – *Medium*: Returns `False` on `ResourceNotFoundError` but swallows other exceptions (e.g., auth failures) by letting them propagate; combined with retry logic elsewhere could expose stack traces.
- **Function `claim_name`** – *High*: Uses `upsert_entity` with `MERGE`, which allows overwriting existing entities without concurrency checks; malicious client could overwrite metadata of names they do not own by racing the claim process.

### `adapters/audit_logs.py`
- **Module overview:** Persists audit events.
- **Function `write_audit_log`** – *Medium*: Fails open by logging an error and returning when table client is unavailable; audit trail silently drops entries, allowing incidents to go unrecorded. Metadata sourced directly from callers may store attacker-controlled strings.

### `adapters/slug.py`
- **Module overview:** Default slug provider backed by Azure Table storage.
- **Function `get_slug`** – *High*: Constructs the OData filter `FullName eq '{human}' or ResourceType eq '{canonical}'` using unescaped user input. An attacker can inject OData clauses (e.g., `resource_type` containing `' or 1 eq 1 or ''`) to enumerate or tamper with slug data.
- **Function `_normalise_resource_type`** – *Medium*: Converts spaces/underscores but does not guard against other characters, enabling the injection noted above.
- **Function `TableSlugProvider.get_slug`** – *Low*: Defers to module-level `get_slug`, inheriting the same injection risk.

### `adapters/slug_fetcher.py`
- **Module overview:** Downloads slug definitions from GitHub.
- **Function `get_all_remote_slugs`** – *Medium*: No signature or hash verification; trust-on-first-use with a public URL. Regex parsing accepts any characters except quotes; attacker controlling upstream can inject extremely long strings causing memory spikes.

### `adapters/slug_loader.py`
- **Module overview:** Writes remote slug definitions into storage.
- **Function `sync_slug_definitions`** – *Medium*: Writes blindly to storage without conflict checks; compromised upstream data or MITM attack can replace every slug. Lacks retries for transient failures, so partial writes leave inconsistent state.

### `providers/json_rules.py`
- **Module overview:** Loads naming rules from JSON.
- **Function `_parse_rule_layer`** – *Low*: Trusts on-disk names—if attacker can add a JSON file, they can redefine naming behavior. Files outside repo (via env override) allow arbitrary injection of rule logic.
- **Function `_build_validators`** – *Medium*: Accepts callables in config? (No, constructs from config) safe. Validators rely on configuration; misconfiguration can disable required fields without warning.

### `app/__init__.py` and `function_app.py`
- **Module overview:** Wires routes to the Azure Functions host.
- **Module behavior** – *Low*: `http_auth_level=func.AuthLevel.ANONYMOUS` for the entire app assumes EasyAuth or manual checks everywhere; any new route added without `require_role` becomes public unintentionally.

---

## Aggregate Flow Assessment

1. **Authentication & Authorization Chain**  
   Combination of anonymous function bindings plus `require_role` puts heavy reliance on custom middleware. Misconfiguration (missing EasyAuth headers, setting `ALLOW_LOCAL_AUTH_BYPASS`, or introducing a new route without calling `require_role`) immediately exposes protected endpoints. The `manager` role mismatch introduces a hidden privilege escalation path. *Severity: High.*

2. **Name Claim Lifecycle**  
   `generate_and_claim_name` → `claim_name` uses optimistic checks without ETag enforcement. Attackers can race legitimate users to hijack claims or overwrite metadata. Release path (`release_name`) also writes without concurrency tokens, enabling rollback attacks where stale data reverts audit history. *Severity: High.*

3. **Slug Resolution & Sync**  
   User-supplied resource types flow into `adapters.slug.get_slug` and `_resolve_slug_payload`, creating an OData injection point that can read arbitrary rows or trigger expensive queries. Combined with trust-on-first-use slug sync, attackers controlling either input channel can manipulate slug mappings and thus generated names. *Severity: High.*

4. **Audit Reporting**  
   `_build_filter` exposes OData injection vectors via `start`/`end` parameters, enabling attackers to exfiltrate other users' audit data or enumerate table contents despite RBAC checks. The lack of pagination coupled with `list_entities` permits DoS by forcing massive responses. *Severity: High.*

5. **Observability & Logging**  
   Multiple modules log full exceptions and decoded principals, risking leakage of secrets, tokens, and personal identifiers into shared log sinks. Attackers who gain log access can harvest sensitive info. *Severity: Medium.*

6. **Extensibility Hooks**  
   Environment-driven provider overrides (`NAMING_RULE_PROVIDER`, `SLUG_PROVIDER`) execute arbitrary import paths; in multi-tenant or less-controlled environments this becomes a code execution vector. *Severity: Medium.*

7. **Upstream Trust Dependencies**  
   Slug synchronization fetches unsigned data from GitHub and writes it directly into production storage. An upstream compromise or MITM attack could inject malicious slug data, ultimately influencing generated names and potentially colliding with existing resources. *Severity: Medium.*

---

## Overall Risk Posture

The service exhibits several high-severity issues, primarily around storage query injection, missing concurrency controls, and reliance on environment toggles for authentication. Addressing the identified injection points, enforcing optimistic concurrency (ETags) on Table operations, and hardening authentication defaults should be prioritized. Secondary focus should include improving logging hygiene, validating upstream data, and tightening configuration-driven extensibility to reduce the attack surface.
