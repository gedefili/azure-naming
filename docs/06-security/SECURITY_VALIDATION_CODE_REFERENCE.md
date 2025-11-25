# Security Validation: Code References

## Overview
This document provides exact code locations and implementation details for the security validation of the release endpoint.

---

## Core Security Functions

### 1. Authentication: `require_role()`
**File**: `core/auth.py` (lines 129-160)

**Purpose**: Validate JWT token and extract user ID + roles

```python
def require_role(headers: Dict[str, str], min_role: str = "reader") -> tuple[str, List[str]]:
    """Verify JWT and ensure the caller has at least the given role."""
    
    canonical_min_role = _canonicalize_role(min_role)
    if not canonical_min_role:
        raise AuthError("Invalid role configuration", status=500)

    if LOCAL_AUTH_BYPASS:
        # Development mode only - bypasses JWT validation
        logging.debug("[auth] Local auth bypass enabled...")
        return LOCAL_BYPASS_USER_ID, LOCAL_BYPASS_ROLES

    # Production path: JWT validation required
    claims = verify_jwt(headers)  # Raises AuthError(401) if missing/invalid
    roles = claims.get("roles", [])
    if isinstance(roles, str):
        roles = [roles]
    roles = _canonicalize_roles(roles)

    # RBAC hierarchy check
    allowed_roles = ROLE_HIERARCHY[ROLE_HIERARCHY.index(canonical_min_role) :]
    if not set(roles).intersection(allowed_roles):
        raise AuthError("Forbidden", status=403)

    return claims.get("oid", ""), roles
```

**Called From**: 
- `app/routes/names.py:84` in `release_name()` function

**Returns**: 
- `(user_id: str, user_roles: List[str])` on success
- Raises `AuthError(401)` if token missing or invalid
- Raises `AuthError(403)` if role insufficient

---

### 2. JWT Validation: `verify_jwt()`
**File**: `core/auth.py` (lines 103-120)

**Purpose**: Validate JWT signature and extract claims

```python
def verify_jwt(headers: Dict[str, str]) -> dict:
    """Validate Authorization bearer token and return claims."""
    
    # Check for Bearer token
    auth_header = headers.get("Authorization") or headers.get("authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise AuthError("Missing bearer token", status=401)

    token = auth_header.split(" ", 1)[1]

    if not JWKS_URL:
        raise AuthError("Tenant ID not configured", status=500)

    # Validate against Azure AD JWKS
    jwk_client = PyJWKClient(JWKS_URL)
    try:
        signing_key = jwk_client.get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=CLIENT_ID or None,
        )
        logging.debug(f"[auth] Verified JWT claims: {claims}")
        return claims
    except (InvalidTokenError, Exception) as exc:
        logging.exception("[auth] JWT validation failed")
        raise AuthError("Invalid token", status=401) from exc
```

**Key Points**:
- RS256 signature validation (cannot be forged)
- Audience validation against CLIENT_ID
- Extracts `oid` (user ID) and `roles` from claims

---

### 3. Authorization: `is_authorized()`
**File**: `core/auth.py` (lines 201-212)

**Purpose**: Verify user has permission to release the resource

```python
def is_authorized(user_roles: List[str], user_id: str, claimed_by: str, released_by: str) -> bool:
    """Check if user has access to a resource.
    
    User must be admin/manager OR directly involved (claimer/releaser).
    """
    
    # Admin bypass - always allowed
    if "admin" in user_roles or "manager" in user_roles:
        return True
    
    # Non-admin: must be the claimer or previous releaser
    return user_id.lower() in [
        (claimed_by or "").lower(),
        (released_by or "").lower(),
    ]
```

**Called From**: 
- `app/routes/names.py:121` in `release_name()` function

**Returns**:
- `True` if admin OR user_id matches claimed_by/released_by
- `False` otherwise

---

### 4. Release Endpoint: `release_name()`
**File**: `app/routes/names.py` (lines 72-147)

**Purpose**: Main endpoint for releasing a claimed name

```python
def release_name(req: func.HttpRequest) -> func.HttpResponse:
    """Release a previously claimed name."""
    
    logging.info("[release_name] Processing release request with RBAC.")

    # LAYER 1: AUTHENTICATION - Verify JWT and extract user/roles
    try:
        user_id, user_roles = require_role(req.headers, min_role="contributor")
    except AuthError as exc:
        return func.HttpResponse(str(exc), status_code=exc.status)

    # Parse request
    try:
        data = req.get_json()
    except ValueError:
        return func.HttpResponse("Invalid JSON payload.", status_code=400)

    name = (data.get("name") or "").lower()
    reason = data.get("reason", "not specified")

    if not name:
        return func.HttpResponse("Missing required field: name.", status_code=400)

    # LAYER 2: DATA VALIDATION - Build partition key
    region = (data.get("region") or "").lower()
    environment = (data.get("environment") or "").lower()

    partition_key = None
    if region and environment:
        partition_key = f"{region}-{environment}"

    # LAYER 3: RETRIEVE ENTITY
    try:
        names_table = get_table_client(NAMES_TABLE_NAME)
        if partition_key:
            entity = names_table.get_entity(partition_key=partition_key, row_key=name)
        else:
            return func.HttpResponse(
                "Unable to determine partition key. Please provide region and environment.",
                status_code=400
            )
    except Exception:
        logging.exception("[release_name] Name not found during release.")
        return func.HttpResponse("Name not found.", status_code=404)

    # LAYER 4: AUTHORIZATION - Check ownership
    if not is_authorized(user_roles, user_id, entity.get("ClaimedBy"), entity.get("ReleasedBy")):
        return func.HttpResponse("Forbidden: not authorized to release this name.", status_code=403)

    # Update entity
    entity["InUse"] = False
    entity["ReleasedBy"] = user_id
    entity["ReleasedAt"] = datetime.utcnow().isoformat()
    entity["ReleaseReason"] = reason

    try:
        names_table.update_entity(entity=entity, mode=UpdateMode.REPLACE)
    except Exception:
        logging.exception("[release_name] Failed to update storage during release.")
        return func.HttpResponse("Error releasing name.", status_code=500)

    # Audit logging
    metadata = {
        "Region": entity.get("PartitionKey", "").split("-")[0] if entity.get("PartitionKey") else None,
        "Environment": entity.get("PartitionKey", "").split("-")[1] if entity.get("PartitionKey") else None,
        "ResourceType": entity.get("ResourceType"),
        "Slug": entity.get("Slug"),
        "Project": entity.get("Project"),
        "Purpose": entity.get("Purpose"),
        "System": entity.get("System"),
        "Index": entity.get("Index"),
    }
    metadata = {key: value for key, value in metadata.items() if value}

    write_audit_log(name, user_id, "released", reason, metadata=metadata)

    return json_message("Name released successfully.", status_code=200)
```

---

## Security Configuration

### RBAC Hierarchy
**File**: `core/auth.py` (lines 40-45)

```python
ROLE_HIERARCHY = ["reader", "contributor", "admin"]
ROLE_ALIASES = {
    "reader": "reader",
    "contributor": "contributor",
    "admin": "admin",
    "sanmar-naming-reader": "reader",
    "sanmar-naming-contributor": "contributor",
    "sanmar-naming-admin": "admin",
    "sanmar.naming.reader": "reader",
    "sanmar.naming.contributor": "contributor",
    "sanmar.naming.admin": "admin",
}
ROLE_GROUPS = _load_role_groups()
```

**Impact**:
- Role hierarchy enforced: `reader < contributor < admin`
- Multiple role name formats supported (dash/dot separated)
- Groups loaded from environment: `AZURE_ROLE_GROUP_READER`, `AZURE_ROLE_GROUP_CONTRIBUTOR`, `AZURE_ROLE_GROUP_ADMIN`

---

### Local Development Bypass
**File**: `core/auth.py` (lines 73-81)

```python
LOCAL_AUTH_BYPASS = _to_bool(os.environ.get("ALLOW_LOCAL_AUTH_BYPASS", ""))
LOCAL_BYPASS_USER_ID = os.environ.get("LOCAL_BYPASS_USER_ID", "local-dev-user")
_LOCAL_BYPASS_RAW = [
    role.strip()
    for role in os.environ.get("LOCAL_BYPASS_ROLES", "contributor,admin").split(",")
    if role.strip()
]
LOCAL_BYPASS_ROLES = _canonicalize_roles(_LOCAL_BYPASS_RAW) or ["contributor"]
```

**Important**:
- Only enabled if `ALLOW_LOCAL_AUTH_BYPASS=true` environment variable set
- Default: OFF (production security mode)
- When enabled: Returns fixed user ID with contributor/admin roles
- Used only for local development with Azurite/Functions

---

## Response Codes

| Status | Error | Condition |
|--------|-------|-----------|
| **401** | Missing bearer token | No Authorization header or invalid format |
| **401** | Invalid token | JWT signature validation fails |
| **403** | Forbidden | User role below minimum (contributor) |
| **403** | Forbidden: not authorized to release this name | User doesn't own name and isn't admin |
| **400** | Missing required field: name | Name field is empty |
| **400** | Unable to determine partition key | Region/environment not provided |
| **404** | Name not found | Entity doesn't exist in table |
| **500** | Error releasing name | Storage operation failed |
| **200** | Name released successfully | Release completed |

---

## Test Scenarios

### Scenario: No Token
```python
# Request
POST /api/release
# Missing Authorization header

# Expected Result
AuthError("Missing bearer token", 401)

# Code Path
release_name() → require_role() → verify_jwt()
  → auth_header check → raise AuthError(401)
```

### Scenario: Invalid Token
```python
# Request
POST /api/release
Authorization: Bearer invalid.token.here

# Expected Result
AuthError("Invalid token", 401)

# Code Path
release_name() → require_role() → verify_jwt()
  → jwt.decode() → InvalidTokenError → raise AuthError(401)
```

### Scenario: Reader Role
```python
# Request
POST /api/release
Authorization: Bearer <valid_token_with_reader_role>

# Expected Result
AuthError("Forbidden", 403)

# Code Path
release_name() → require_role()
  → allowed_roles = ["contributor", "admin"]
  → user_roles = ["reader"]
  → intersection is empty → raise AuthError(403)
```

### Scenario: Non-Owner
```python
# Request
POST /api/release
Authorization: Bearer <valid_token_user=bob_role=contributor>
Body: { "name": "wus2prdsanmarsterp-01", "region": "wus2", "environment": "prd" }

# Entity in Storage
ClaimedBy: "alice"
InUse: true

# Expected Result
HttpResponse("Forbidden: not authorized to release this name.", 403)

# Code Path
release_name()
  → require_role() → OK (bob has contributor role)
  → get_entity() → OK (name found, claimed by alice)
  → is_authorized(["contributor"], "bob", "alice", None)
    → "admin" not in ["contributor"] → False
    → "bob" not in ["alice", ""] → False
    → return False
  → return HttpResponse(403)
```

### Scenario: Owner with Correct Role
```python
# Request
POST /api/release
Authorization: Bearer <valid_token_user=alice_role=contributor>
Body: { "name": "wus2prdsanmarsterp-01", "region": "wus2", "environment": "prd" }

# Entity in Storage
ClaimedBy: "alice"
InUse: true

# Expected Result
HttpResponse("Name released successfully.", 200)

# Code Path
release_name()
  → require_role() → OK (alice has contributor role, user_id=alice)
  → get_entity() → OK (name found, claimed by alice)
  → is_authorized(["contributor"], "alice", "alice", None)
    → "admin" not in ["contributor"] → skip
    → "alice" in ["alice", ""] → True
    → return True
  → update_entity(InUse=False, ReleasedBy="alice")
  → write_audit_log()
  → return HttpResponse(200)
```

### Scenario: Admin Releases Others' Name
```python
# Request
POST /api/release
Authorization: Bearer <valid_token_user=charlie_role=admin>
Body: { "name": "wus2prdsanmarsterp-01", "region": "wus2", "environment": "prd" }

# Entity in Storage
ClaimedBy: "alice"
InUse: true

# Expected Result
HttpResponse("Name released successfully.", 200)

# Code Path
release_name()
  → require_role() → OK (charlie has admin role, user_id=charlie)
  → get_entity() → OK (name found, claimed by alice)
  → is_authorized(["admin"], "charlie", "alice", None)
    → "admin" in ["admin"] → True
    → return True (admin bypass)
  → update_entity(InUse=False, ReleasedBy="charlie")
  → write_audit_log()
  → return HttpResponse(200)
```

---

## Audit Logging

### `write_audit_log()` Function
**File**: `adapters/audit_logs.py`

**Called**: After successful release in `release_name()`

**Logs**:
- `name`: The released resource name
- `user_id`: User who performed the release
- `action`: "released"
- `note`: Release reason
- `metadata`: Resource details (region, environment, slug, system, etc.)
- `timestamp`: ISO format UTC timestamp

**Impact**: Provides complete audit trail of all releases for compliance/security investigations

---

## Summary

| Security Layer | Implementation | Code Location |
|---|---|---|
| **Authentication** | JWT with RS256 signature validation | `core/auth.py:103-120` |
| **RBAC** | Role hierarchy check against minimum required | `core/auth.py:151-155` |
| **Resource Ownership** | User ID vs ClaimedBy field | `core/auth.py:204-212` |
| **Data Validation** | Name must exist in table | `app/routes/names.py:110-118` |
| **Audit Trail** | All operations logged | `app/routes/names.py:140` |

All layers are required to pass for release to succeed.
