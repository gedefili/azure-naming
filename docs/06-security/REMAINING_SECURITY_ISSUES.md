# Remaining Security Issues - Comprehensive Analysis

**Date**: October 31, 2025  
**Analysis Type**: Post-Metadata-Sanitization Security Review  
**Basis**: Pre-existing security audit from October 16, 2025  
**Status**: 14 Issues Identified (1 NEW from metadata work, 13 PRE-EXISTING)

---

## Executive Summary

The metadata sanitization work completed successfully addresses one class of attacks (control characters, type confusion). However, the comprehensive security audit from October 16 identified **14 additional security issues** that remain unaddressed:

### By Severity
- **HIGH**: 5 issues (OData injection, concurrency, auth defaults)
- **MEDIUM**: 9 issues (code execution, upstream trust, logging, enumeration)

### By Category
- **Query Injection**: 2 HIGH issues (audit filters, slug lookup)
- **Concurrency**: 2 HIGH issues (claim/release without ETags)
- **Authentication**: 2 HIGH + 2 MEDIUM issues (defaults, bypass)
- **Code Execution**: 2 MEDIUM issues (environment imports)
- **Data Trust**: 2 MEDIUM issues (upstream, storage)
- **Observability**: 2 MEDIUM issues (logging, enumeration)
- **Other**: 2 MEDIUM issues (scope, configuration)

---

## Critical Issues (Must Fix Before Production)

### ISSUE #1: OData Injection in Audit Filters ⚠️ HIGH

**File**: `app/routes/audit.py` (lines 37-52)  
**Severity**: HIGH (Data Exfiltration, Query Abuse, DoS)  
**Status**: ❌ NOT FIXED

**Vulnerable Code**:
```python
def _build_filter(params: Dict[str, str]) -> str:
    filters: List[str] = []
    
    user = params.get("user")
    if user:
        filters.append(f"User eq '{_escape(user.lower())}'")  # ← VULNERABLE
    
    # ... more fields similarly vulnerable
    
    start = params.get("start")  # ← DATETIME - NO ESCAPING AT ALL
    if start:
        filters.append(f"EventTime ge datetime'{start}'")
    
    end = params.get("end")      # ← DATETIME - NO ESCAPING AT ALL
    if end:
        filters.append(f"EventTime le datetime'{end}'")
```

**Attack Vector**:
```
Attacker sends: start="2025-01-01' or 1 eq 1 or '1'='1"
Filter becomes: "EventTime ge datetime'2025-01-01' or 1 eq 1 or '1'='1'"
Result: Returns ALL audit entries, bypassing RBAC checks
```

**Current Mitigation**: 
- Single quotes escaped (doubled) for string fields
- NO escaping for datetime fields
- Does not protect against all OData syntax

**Risk**:
- ✅ Data exfiltration (read other users' audit logs)
- ✅ Query abuse (discover table structure)
- ✅ Denial of service (force table scan)

**Fix Required**: Use parameterized queries or validated datetime parsing

---

### ISSUE #2: OData Injection in Slug Lookup ⚠️ HIGH

**File**: `adapters/slug.py` (lines ~25-35)  
**Severity**: HIGH (Data Exfiltration, Resource Manipulation)  
**Status**: ❌ NOT FIXED

**Vulnerable Code**:
```python
def get_slug(human: str, resource_type: str, *, client: TableClient) -> str:
    """Retrieve slug or default."""
    
    # Unsafe string interpolation
    query = f"FullName eq '{human}' or ResourceType eq '{resource_type}'"  # ← VULNERABLE
    
    entities = list(client.query_entities(query_filter=query))
    # ...
```

**Attack Vector**:
```
Attacker sends resource_type: "' or 1 eq 1 or ''"
Query becomes: "FullName eq '...' or ResourceType eq '' or 1 eq 1 or ''"
Result: Returns all slug entries, enabling manipulation of generated names
```

**Current Mitigation**: 
- `_normalise_resource_type()` removes some chars but not all
- No protection against quote-based injection

**Risk**:
- ✅ Slug enumeration (discover all mappings)
- ✅ Name collision attacks (corrupt slug resolution)
- ✅ Information disclosure

**Fix Required**: Use Table SDK's filter builder with proper escaping

---

### ISSUE #3: Race Condition in Name Claim ⚠️ HIGH

**File**: `adapters/storage.py:claim_name()` (lines ~85-106)  
**Severity**: HIGH (Hijacking, Metadata Overwrite)  
**Status**: ❌ NOT FIXED

**Vulnerable Code**:
```python
def claim_name(..., metadata: Dict[str, Any] = None) -> None:
    """Insert or update a claimed name entity in the ClaimedNames table."""
    
    entity = {
        "PartitionKey": partition_key,
        "RowKey": name,
        "InUse": True,
        "ResourceType": resource_type,
        "ClaimedBy": claimed_by,
        "ClaimedAt": datetime.utcnow().isoformat(),
    }
    
    if metadata:
        entity.update(metadata)
    
    # MERGE mode allows overwrite without checking if entity exists!
    table.upsert_entity(entity=entity, mode=UpdateMode.MERGE)  # ← VULNERABLE
```

**Attack Vector**:
```
1. User A initiates claim for "wus2prdsanmarsterp-01"
2. Same name already exists (abandoned/forgotten claim)
3. User B rapidly claims same name before User A's upsert completes
4. UpdateMode.MERGE overwrites User A's claim with User B's
5. Audit trail shows User B as original claimer
```

**Current Mitigation**: 
- Existence check in `generate_and_claim_name()` before `claim_name()`
- But race condition exists between check and update

**Risk**:
- ✅ Claim hijacking (take ownership of resource)
- ✅ Metadata poisoning (corrupt claimed resource state)
- ✅ Audit trail corruption

**Fix Required**: Use ETags for optimistic concurrency control

---

### ISSUE #4: Race Condition in Name Release ⚠️ HIGH

**File**: `app/routes/names.py:release_name()` (lines ~112-142)  
**Severity**: HIGH (Audit Rollback, Release Authority Usurp)  
**Status**: ❌ NOT FIXED

**Vulnerable Code**:
```python
def release_name(req: func.HttpRequest) -> func.HttpResponse:
    # ... auth checks pass ...
    
    try:
        entity = names_table.get_entity(partition_key=partition_key, row_key=name)
    except Exception:
        return func.HttpResponse("Name not found.", status_code=404)
    
    # VULNERABLE: No ETag saved from get_entity
    
    # Update entity
    entity["InUse"] = False
    entity["ReleasedBy"] = user_id
    entity["ReleasedAt"] = datetime.utcnow().isoformat()
    entity["ReleaseReason"] = reason
    
    # MERGE mode allows stale updates to overwrite!
    names_table.update_entity(entity=entity, mode=UpdateMode.REPLACE)  # ← VULNERABLE
```

**Attack Vector**:
```
1. User A reads entity (gets stale ETag)
2. System releases name (updates entity, increments ETag)
3. User A's stale update replays (REPLACE mode uses old data)
4. ReleasedBy/ReleasedAt reverts to User A's old values
5. Audit trail shows wrong user as releaser
```

**Current Mitigation**: 
- None. REPLACE mode blindly overwrites.

**Risk**:
- ✅ Audit trail corruption (who released?)
- ✅ Release authority usurpation (fake release by wrong user)
- ✅ Compliance violation

**Fix Required**: Use ETags for optimistic concurrency control

---

### ISSUE #5: Anonymous Function Bindings ⚠️ HIGH

**File**: `function_app.py` (module definition)  
**Severity**: HIGH (Accidental Public Exposure)  
**Status**: ❌ NOT FIXED

**Vulnerable Code**:
```python
# In function_app.py or via Azure Functions configuration
http_auth_level = func.AuthLevel.ANONYMOUS  # ← DANGEROUS DEFAULT
```

**Impact**:
```
- Any new route added WITHOUT require_role() call is immediately public
- If require_role() has a bug or is forgotten, endpoint becomes unauthenticated
- Relies on 100% developer discipline (impossible to enforce)
```

**Current Mitigation**: 
- Custom `require_role()` decorator on every route
- Relies entirely on developer discipline

**Risk**:
- ✅ Accidental public endpoints
- ✅ Bypassed if EasyAuth misconfigured
- ✅ Social engineering (convincing dev to skip auth)

**Fix Required**: Set `http_auth_level = func.AuthLevel.FUNCTION`, use EasyAuth

---

## High-Priority Issues (Should Fix Before Production)

### ISSUE #6: Arbitrary Module Import (Naming Rules) ⚠️ MEDIUM

**File**: `core/naming_rules.py:_load_provider_from_env()` (lines ~25-45)  
**Severity**: MEDIUM (Remote Code Execution if env controlled)  
**Status**: ❌ NOT FIXED

**Vulnerable Code**:
```python
def _load_provider_from_env(env_var: str, **kwargs) -> NamingRuleProvider | None:
    """Load a provider from an environment variable module path."""
    
    provider_path = os.environ.get(env_var)  # e.g., "my_module.MyProvider"
    if not provider_path:
        return None
    
    # Dangerous: Imports and instantiates arbitrary code
    module_name, class_name = provider_path.rsplit(".", 1)
    module = importlib.import_module(module_name)  # ← ARBITRARY CODE EXECUTION
    return getattr(module, class_name)(**kwargs)
```

**Attack Vector**:
```
Attacker compromises CI/CD environment or container image:
  - Sets NAMING_RULE_PROVIDER="malicious_package.Backdoor"
  - On function startup, imports and executes Backdoor()
  - Attacker gains RCE
```

**Current Mitigation**: 
- None. Any value in environment is trusted.

**Risk**:
- ✅ Remote code execution at startup
- ✅ Credential theft
- ✅ Lateral movement

**Fix Required**: Whitelist of allowed providers, validate paths

---

### ISSUE #7: Arbitrary Module Import (Slug Provider) ⚠️ MEDIUM

**File**: `core/slug_service.py:_load_providers_from_env()` (similar pattern)  
**Severity**: MEDIUM (RCE if env controlled)  
**Status**: ❌ NOT FIXED

**Same vulnerability as ISSUE #6** for slug providers.

**Fix Required**: Same as ISSUE #6

---

### ISSUE #8: Unsafe Upstream Trust (GitHub Slugs) ⚠️ MEDIUM

**File**: `adapters/slug_fetcher.py:get_all_remote_slugs()` (lines ~12-35)  
**Severity**: MEDIUM (Malicious Slug Injection, MITM)  
**Status**: ❌ NOT FIXED

**Vulnerable Code**:
```python
def get_all_remote_slugs(github_url: str) -> Dict[str, str]:
    """Fetch slugs from GitHub without verification."""
    
    response = requests.get(github_url)  # e.g., "https://raw.github.com/..."
    # NO signature verification, NO hash check
    
    # Parse and return slugs
    slugs = {}
    for line in response.text.split("\n"):
        match = re.match(r'(\S+)\s*:\s*(.+?)(?:\s*#.*)?$', line)  # ← PERMISSIVE REGEX
        if match:
            slugs[match.group(1)] = match.group(2)  # Any chars except quotes
    
    return slugs  # TRUST-ON-FIRST-USE
```

**Attack Vector**:
```
Option 1 (MITM):
  - Attacker intercepts slug fetch from GitHub
  - Returns malicious slug mappings
  - Names generated with attacker-controlled slugs

Option 2 (Upstream compromise):
  - Attacker compromises GitHub repo
  - Injects malicious slug data
  - All functions reading from repo get corrupted slugs
```

**Current Mitigation**: 
- Assumes HTTPS connection (but no cert pinning)
- No integrity verification

**Risk**:
- ✅ Name collision attacks
- ✅ Resource exhaustion (extremely long slugs)
- ✅ Information disclosure (debug slugs)

**Fix Required**: Cryptographic signature verification, hash pinning, or content-addressed storage

---

### ISSUE #9: Blind Storage Writes (Slug Sync) ⚠️ MEDIUM

**File**: `adapters/slug_loader.py:sync_slug_definitions()` (lines ~18-45)  
**Severity**: MEDIUM (Inconsistent State)  
**Status**: ❌ NOT FIXED

**Vulnerable Code**:
```python
def sync_slug_definitions(slugs: Dict[str, str], client: TableClient) -> None:
    """Write slug definitions to storage without conflict checks."""
    
    for slug_id, slug_value in slugs.items():
        entity = {
            "PartitionKey": "Slugs",
            "RowKey": slug_id,
            "Definition": slug_value,
        }
        
        # NO conflict checks, NO retries
        client.upsert_entity(entity, mode=UpdateMode.MERGE)  # ← BLINDLY OVERWRITES
        # If this fails halfway through 1000 slugs, table is left in inconsistent state
```

**Attack Vector**:
```
1. Sync starts with 1000 slug definitions
2. Completes 500 before network error
3. Sync doesn't retry - exits
4. Table left with 500 new slugs, 500 old (inconsistent)
5. Name generation uses mix of old/new definitions (unpredictable)
```

**Current Mitigation**: 
- None. Single upsert per entity.

**Risk**:
- ✅ Inconsistent state (half-updated)
- ✅ Unpredictable naming
- ✅ Difficult debugging

**Fix Required**: Batch transactional writes, retry logic, or atomic replace

---

### ISSUE #10: User Enumeration via Timing ⚠️ MEDIUM

**File**: `app/routes/audit.py:audit_bulk()` (lines ~210-260)  
**Severity**: MEDIUM (User Enumeration)  
**Status**: ❌ NOT FIXED

**Vulnerable Code**:
```python
def audit_bulk(req: func.HttpRequest) -> func.HttpResponse:
    """List audit records with optional filters."""
    
    user = params.get("user")  # User-supplied user ID to filter
    
    # ... build filter ...
    entities = list(table.query_entities(query_filter=filter_query))
    
    # If user supplies a non-existent user ID:
    # - Query returns 0 entities (fast)
    # - User enumeration via timing: if response is fast, user doesn't exist
    
    # If user supplies an existing user ID:
    # - Query returns many entities (slow)
    # - Timing reveals user exists
```

**Attack Vector**:
```
Attacker probes: "audit_bulk?user=john.doe@company.com"
  - Response time ~50ms → user doesn't exist
  - Response time ~500ms → user exists
Attacker: "audit_bulk?user=alice@company.com"
  - Response time ~400ms → user probably exists
Attacker builds user list via timing analysis
```

**Current Mitigation**: 
- None. Timing not normalized.

**Risk**:
- ✅ User enumeration (discover valid user IDs)
- ✅ Social engineering (target known users)
- ✅ Reconnaissance for phishing

**Fix Required**: Normalize response times or rate limit

---

### ISSUE #11: Manager Role Privilege Escalation ⚠️ MEDIUM

**File**: `core/auth.py:is_authorized()` (lines ~201-212)  
**Severity**: MEDIUM (Hidden Privilege Escalation)  
**Status**: ❌ NOT FIXED

**Vulnerable Code**:
```python
def is_authorized(user_roles: List[str], user_id: str, claimed_by: str, ...) -> bool:
    """Check if user has access to a resource."""
    
    # ROLE_HIERARCHY = ["reader", "contributor", "admin"]
    # But is_authorized checks for "manager" which is NOT in hierarchy
    
    if "admin" in user_roles or "manager" in user_roles:  # ← MANAGER NOT IN HIERARCHY
        return True
    
    return user_id.lower() in [claimed_by.lower(), ...]
```

**Attack Vector**:
```
Azure Entra ID has a "manager" role that's added to claims
or attacker crafts JWT with "manager" claim
Token is accepted by require_role() (no check)
is_authorized() grants admin-like access
Attacker bypasses resource ownership checks
```

**Current Mitigation**: 
- None. "manager" blindly trusted.

**Risk**:
- ✅ Privilege escalation (become admin without admin role)
- ✅ Bypass resource ownership (access others' resources)
- ✅ Audit trail corruption

**Fix Required**: Reconcile role definitions, validate claims

---

### ISSUE #12: LOCAL_AUTH_BYPASS Lacks Production Guard ⚠️ MEDIUM

**File**: `core/auth.py:require_role()` (lines ~73-81)  
**Severity**: MEDIUM (Accidental Auth Bypass in Production)  
**Status**: ❌ NOT FIXED

**Vulnerable Code**:
```python
LOCAL_AUTH_BYPASS = _to_bool(os.environ.get("ALLOW_LOCAL_AUTH_BYPASS", ""))

def require_role(headers: Dict[str, str], min_role: str = "reader") -> tuple:
    """Verify JWT and ensure the caller has at least the given role."""
    
    canonical_min_role = _canonicalize_role(min_role)
    
    if LOCAL_AUTH_BYPASS:  # ← NO PRODUCTION CHECK
        logging.debug("[auth] Local auth bypass enabled...")
        return LOCAL_BYPASS_USER_ID, LOCAL_BYPASS_ROLES  # Returns fake user/roles
    
    # Production path: JWT validation...
```

**Attack Vector**:
```
Production admin accidentally sets: ALLOW_LOCAL_AUTH_BYPASS=true
All endpoints become unauthenticated
Attackers bypass all auth checks
Audit logs show fake user "local-dev-user"
```

**Current Mitigation**: 
- Documented as "local dev only"
- But no enforcement

**Risk**:
- ✅ Complete auth bypass
- ✅ Audit trail corruption
- ✅ Configuration error (easy mistake)

**Fix Required**: Environment-aware guard (fail if production)

---

### ISSUE #13: PyJWKClient Not Cached ⚠️ MEDIUM

**File**: `core/auth.py:verify_jwt()` (lines ~103-120)  
**Severity**: MEDIUM (Performance, DoS Risk)  
**Status**: ❌ NOT FIXED

**Vulnerable Code**:
```python
def verify_jwt(headers: Dict[str, str]) -> dict:
    """Validate Authorization bearer token and return claims."""
    
    auth_header = headers.get("Authorization") or headers.get("authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise AuthError("Missing bearer token", status=401)
    
    token = auth_header.split(" ", 1)[1]
    
    # NEW CLIENT CREATED PER REQUEST!
    jwk_client = PyJWKClient(JWKS_URL)  # ← NO CACHING
    try:
        signing_key = jwk_client.get_signing_key_from_jwt(token)
        # ...
```

**Impact**:
```
- Each request creates new PyJWKClient
- Each client fetches JWKS from Azure AD (outbound HTTP)
- Under load: 1000 requests/sec = 1000 HTTP calls to JWKS endpoint
- Risk: Rate limiting, increased latency, DoS potential
```

**Current Mitigation**: 
- None. No caching.

**Risk**:
- ✅ Performance degradation
- ✅ Rate limiting from JWKS endpoint
- ✅ DoS vulnerability

**Fix Required**: Cache PyJWKClient or use token caching library

---

### ISSUE #14: Logging Leaks PII and Credentials ⚠️ MEDIUM

**File**: `core/auth.py:parse_client_principal()` (debug logging)  
**Severity**: MEDIUM (PII Leakage, Credential Exposure)  
**Status**: ❌ NOT FIXED

**Vulnerable Code**:
```python
def parse_client_principal(headers: Dict[str, str]) -> dict:
    """Parse the Azure EasyAuth principal header."""
    
    principal_header = headers.get("X-MS-CLIENT-PRINCIPAL")
    if principal_header:
        try:
            decoded = json.loads(
                base64.b64decode(principal_header).decode("utf-8")
            )
            logging.debug(f"[auth] Decoded principal: {decoded}")  # ← LOGS EVERYTHING
            return decoded
        except Exception as exc:
            logging.exception("[auth] Failed to parse principal")  # ← LOGS EXCEPTION
```

**Risk**:
```
If DEBUG logging is enabled:
- Full principal object logged (includes email, name, roles)
- If tokens in claims: exposed to log aggregation system
- Log files collected in shared APM system → accessible to many users
- PII accessible to: log admins, APM operators, anyone with read access
```

**Current Mitigation**: 
- Debug logging typically disabled
- But if enabled, leaks PII

**Risk**:
- ✅ PII leakage (emails, names)
- ✅ Credential exposure (if tokens in claims)
- ✅ Compliance violation (GDPR, HIPAA)

**Fix Required**: Log only necessary fields, strip sensitive data

---

## Summary: Remaining Issues by Priority

### MUST FIX (Blocks Production) - 5 Issues
1. ❌ OData injection in audit filters (HIGH)
2. ❌ OData injection in slug lookup (HIGH)
3. ❌ Race condition on claim (HIGH)
4. ❌ Race condition on release (HIGH)
5. ❌ Anonymous function binding (HIGH)

### SHOULD FIX (Before Production) - 9 Issues
6. ❌ Arbitrary module import - naming (MEDIUM)
7. ❌ Arbitrary module import - slug (MEDIUM)
8. ❌ Unsafe upstream trust (MEDIUM)
9. ❌ Blind slug writes (MEDIUM)
10. ❌ User enumeration via timing (MEDIUM)
11. ❌ Manager role escal (MEDIUM)
12. ❌ LOCAL_AUTH_BYPASS guard (MEDIUM)
13. ❌ PyJWKClient caching (MEDIUM)
14. ❌ Logging leaks PII (MEDIUM)

---

## Metadata Sanitization vs Remaining Issues

**What We Fixed** ✅
- Arbitrary metadata sanitization before storage
- Control character removal
- Type safety enforcement
- OData special chars in metadata keys/values

**What Still Needs Fixing** ❌
- OData injection in **query filters** (still vulnerable)
- Race conditions on **storage operations** (ETags)
- **Authentication configuration** defaults
- **Upstream data** integrity
- **Environment variable** exploitation
- **Logging** hygiene

---

## Relationship to Pre-Existing Audit

These 14 issues are **documented in the October 16, 2025 security audit** as HIGH/MEDIUM severity findings:

- **From audit**: "Several high-severity issues, primarily around storage query injection, missing concurrency controls, and reliance on environment toggles"
- **Our metadata work**: Fixed metadata content sanitization but did NOT address query injection, concurrency, or auth configuration

---

## Recommendations

### Immediate (Must Do)
1. Address the 5 HIGH issues before any production deployment
2. OData injection fixes are highest impact
3. ETag enforcement on claim/release
4. Function auth level hardening

### Short-term (Should Do)
5. Fix remaining 9 MEDIUM issues
6. Environment variable validation
7. Upstream signature verification
8. Logging sanitization

### Long-term (Nice to Have)
9. Full input validation framework
10. Concurrency testing
11. Security regression suite
12. Annual security audit

---

## Note

The metadata sanitization completed successfully **prevents injection of malicious content WITHIN metadata values**. However, the remaining 14 issues are **query injection, concurrency, and configuration** problems that exist **outside** the metadata handling scope.

These are **pre-existing findings** from the October 16 audit that should be tracked separately and prioritized for remediation.

**Status**: ✅ Metadata sanitization complete  
**Status**: ❌ Remaining security issues still open
