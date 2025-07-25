# 🔐 Authentication & RBAC

This document explains how the Azure Naming Function implements user authentication and role-based access control (RBAC) using Entra ID (formerly Azure AD).

---

## 🔐 Authentication Flow

1. **Frontend or client app** requests an access token from Entra ID (Microsoft Identity Platform).
2. **User logs in** and consents to scopes.
3. Client sends the token in an HTTP `Authorization: Bearer <token>` header to the Azure Function.
4. The function verifies the token and parses claims from the JWT.

---

## 📜 Required Token Claims

The following claims are extracted:

| Claim           | Description                 |
| --------------- | --------------------------- |
| `oid`           | Object ID of the Entra user |
| `roles`         | Assigned Entra roles        |
| `email` / `upn` | Email or principal name     |

These are parsed in `utils/auth.py` and validated at runtime.

---

## 🧑‍⚖️ Roles and Permissions

The app supports the following Entra roles:

| Role      | Description                                        |
| --------- | -------------------------------------------------- |
| `user`    | Can claim, release, and audit only their own names |
| `manager` | Can audit *any* name or user history               |
| `admin`   | Full control, provisioning access, future tools    |

> 💡 Roles can be assigned via App Roles in Entra ID or via Group membership.

---

## 🧰 Role Enforcement

The shared function `require_role(headers, min_role)` is used by each endpoint.
It checks the role hierarchy:

```python
ROLE_HIERARCHY = ["user", "manager", "admin"]
```

### Example Usage:

```python
try:
    user, role = require_role(req.headers, min_role="user")
except AuthError as e:
    return func.HttpResponse(str(e), status_code=e.status)
```

This pattern is used in:

* `/claim`
* `/release`
* `/audit`
* `/audit_bulk`
* `/slug_sync`

The `/slug_sync_timer` function **does not** require authentication, as it's internal and time-triggered.

---

## 👥 Group-Based Roles (Optional)

You may map Entra security groups to roles by resolving group claims in `auth.py`. This is useful if you prefer group-based RBAC instead of App Role Assignments.

---

## 🔍 Logging & Auditing Access

All authorization denials are logged with the user principal and operation.

Example:

```
[auth] Access denied for user: jsmith@contoso.com trying to audit_bulk
```

---

Next: [🗃 Table Schemas & Naming Rules](schema.md)
