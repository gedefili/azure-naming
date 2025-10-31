# Security Documentation

This directory contains comprehensive security documentation for the Azure Naming API project.

## Quick Start

- **New to security?** Start with [`SECURITY_OVERVIEW.md`](#) (coming soon)
- **Fixed HIGH issues?** See [`SECURITY_FIXES_HIGH_ISSUES.md`](./SECURITY_FIXES_HIGH_ISSUES.md)
- **Want to report an issue?** See [`SECURITY.md`](../SECURITY.md) in root docs
- **Implementing RBAC?** See [`SECURITY_VALIDATION.md`](./SECURITY_VALIDATION.md)

## Documentation Index

### Issue Remediation

| Document | Focus | Audience |
|----------|-------|----------|
| [SECURITY_FIXES_HIGH_ISSUES.md](./SECURITY_FIXES_HIGH_ISSUES.md) | 5 HIGH severity fixes applied Oct 31, 2025 | Developers, Auditors |
| [REMAINING_SECURITY_ISSUES.md](../REMAINING_SECURITY_ISSUES.md) | 9 MEDIUM severity issues (future work) | Architects, Risk Managers |
| [SECURITY_VALIDATION.md](./SECURITY_VALIDATION.md) | Validation & RBAC implementation | Developers |

### Guidance Documents

| Document | Focus | Audience |
|----------|-------|----------|
| [SECURITY_METADATA_HANDLING.md](../SECURITY_METADATA_HANDLING.md) | Safe handling of audit metadata | Developers |
| [SECURITY_UPDATES_SUMMARY.txt](../SECURITY_UPDATES_SUMMARY.txt) | Timeline of all security updates | Project Managers |

---

## Security Status

### Current Issues (as of Oct 31, 2025)

**Resolved (5):**
- ✅ OData injection in audit filters
- ✅ OData injection in slug lookup  
- ✅ Race condition on name claim
- ✅ Race condition on name release
- ✅ Anonymous function binding

**Pending (9):**
- ⏳ Unvalidated metadata in audit logs
- ⏳ Missing rate limiting on endpoints
- ⏳ RBAC gap: insufficient role validation
- ⏳ And 6 more (see REMAINING_SECURITY_ISSUES.md)

---

## Key Concepts

### Input Validation

All user input must be validated before use:

```python
# app/routes/audit.py
def _validate_datetime(dt_str: str):
    """Validate datetime format and reject OData injection."""
    # Checks: format, keywords, special characters
    
# adapters/slug.py
def _escape_odata_string(value: str):
    """Properly escape strings for OData queries."""
    # Doubles single quotes: "x'y" → "x''y"
```

### Concurrency Control

Use ETags and atomic operations to prevent race conditions:

```python
# adapters/storage.py
claim_table.create_entity(entity)  # Atomic (fails if exists)

# app/routes/names.py
update_entity(..., match_condition="MatchIfNotModified", etag=etag)
```

### Authentication & Authorization

All endpoints require authentication by default:

```python
# app/__init__.py
app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

# Per-route RBAC available
@require_role("admin")
def admin_endpoint(req):
    ...
```

---

## Testing & Verification

### Unit Tests

```bash
# Run all security-related tests
pytest tests/test_audit_routes.py -v
pytest tests/test_slug_adapter.py -v

# Run full suite (78/82 pass)
pytest tests/ -v
```

### Security Review Checklist

- [ ] All input validation functions have tests
- [ ] OData queries use _escape_odata_string()
- [ ] Concurrent operations use ETags or create_entity()
- [ ] Endpoints use FUNCTION auth level
- [ ] Error messages don't leak sensitive data
- [ ] Audit logging captures all sensitive operations

---

## Deployment

### Prerequisites

1. **EasyAuth Enabled**: Required for FUNCTION auth level
   ```bash
   az functionapp auth enable --name myFunctionApp
   ```

2. **Identity Provider Configured**: Azure AD, GitHub, or other OIDC provider
   ```bash
   az functionapp auth update --aad-client-id <id> --aad-client-secret <secret>
   ```

### Post-Deployment Verification

```bash
# Verify endpoint requires auth
curl https://app.azurewebsites.net/api/names/generate
# Expected: 401 Unauthorized

# Verify with valid token
curl -H "Authorization: Bearer $TOKEN" \
  https://app.azurewebsites.net/api/names/generate
# Expected: 200 OK or 403 Forbidden
```

---

## Contact & Escalation

- **Security Questions:** See SECURITY.md in root docs
- **Report Vulnerability:** Email security team (details in SECURITY.md)
- **Audit Schedule:** Quarterly (next: Jan 31, 2026)

---

## Document Versions

| Date | Version | Status | Changes |
|------|---------|--------|---------|
| Oct 31, 2025 | 1.0 | Current | Initial security docs, 5 HIGH issues fixed |
| Oct 16, 2025 | 0.1 | Archived | Security audit identified 14 issues |

---

**Last Updated:** October 31, 2025  
**Maintained By:** GitHub Copilot  
**Next Review:** January 31, 2026
