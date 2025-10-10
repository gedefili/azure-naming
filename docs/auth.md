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

These are parsed in `core/auth.py` and validated at runtime.

---

## 🧑‍⚖️ Roles and Permissions

The app supports the following Entra roles:

| Role | Description |
| ---- | ----------- |
| `reader` | View OpenAPI docs and query audit history for your own activity. |
| `contributor` | Generate/release names and query audits (inherits reader access). |
| `admin` | Full control, including cross-user audits and slug sync operations. |

> 💡 Roles can be assigned via App Roles in Entra ID or via Group membership.

---

## 🧰 Role Enforcement

The shared function `require_role(headers, min_role)` is used by each endpoint.
It checks the role hierarchy:

```python
ROLE_HIERARCHY = ["reader", "contributor", "admin"]
```

### Example Usage:

```python
try:
    user, roles = require_role(req.headers, min_role="contributor")
except AuthError as e:
    return func.HttpResponse(str(e), status_code=e.status)
```

This pattern is used in:

* `/claim` & `/generate` — require at least **contributor**.
* `/release` — requires **contributor**.
* `/audit` — requires **reader** (plus ownership unless you are an admin).
* `/audit_bulk` — requires **reader**; cross-user queries restricted to **admin**.
* `/slug_sync` — requires **admin**.
* `/openapi.json` & `/docs` — require **reader**.

The `/slug_sync_timer` function **does not** require authentication, as it's internal and time-triggered.

---

## 👥 Group-Based Roles (Optional)

You may map Entra security groups to roles by resolving group claims in `auth.py`. This is useful if you prefer group-based RBAC instead of App Role Assignments.

Set the following environment variables to the corresponding Entra group object IDs:

| Environment Variable | Role Mapped |
| -------------------- | ----------- |
| `AZURE_ROLE_GROUP_READER` | `reader` |
| `AZURE_ROLE_GROUP_CONTRIBUTOR` | `contributor` |
| `AZURE_ROLE_GROUP_ADMIN` | `admin` |

Only variables that are present are enforced, so you can bootstrap the service with App Roles and gradually add group mappings.

---

## 🧪 Create a Test Client Application

Use these steps to provision a dedicated Entra ID app registration that you can use for local testing and token generation without affecting production clients.

1. **Register a single-page or native client app** in the Entra admin portal.
    * *Azure Portal → Entra ID → App registrations → New registration*
    * Name it something like `AzureNamingTestClient`.
    * Choose *Accounts in this organizational directory only*.
    * For native testing, add a redirect URI such as `http://localhost:8400` (or leave empty if you will only use the CLI).
2. **Grant your client access to the API.**
        * Open the newly created registration → *Expose an API*.
        * If the server-side Azure Naming registration has not been configured with roles yet, add them now under **App roles**. Create at least:
                - `Sanmar Naming Reader` (`value`: `reader`, member type **Users/Groups**)
                - `Sanmar Naming Contributor` (`value`: `contributor`, member type **Users/Groups**)
                - `Sanmar Naming Admin` (`value`: `admin`, member type **Users/Groups**)
            These three roles are sufficient for the built-in providers; additional roles may be required if you introduce custom providers or downstream systems with alternative access levels.
        * Add an Application ID URI: `api://<server-app-client-id>` (this is the ID from the Azure Naming Function registration).
        * Under *Scopes defined by this API* create at least one delegated permission if the list is empty:
            1. Click **Add a scope**.
            2. Set **Scope name** to `user_access` (or any descriptive value you prefer; avoid using `.default` here because it is a reserved alias, not an actual scope name).
            3. Provide a display name/description such as “User access to Azure Naming API.”
            4. Choose **Admins and users** for “Who can consent?” and mark the scope as **Enabled**.
           The moment you define your first scope (e.g., `user_access`), Azure automatically exposes the `.default` shorthand. That means when you request a token you can specify `--scope api://<server-app-client-id>/.default` (or `--resource api://<server-app-client-id>`) and the resulting token will include every delegated scope you created, including `user_access`.
3. **Assign App Roles to the test client.**
    * Navigate to *Enterprise applications* → select your API (server) registration.
    * Add your user account (or a service principal) to the `reader`, `contributor`, or `admin` roles as needed for testing.
4. **(Optional) Create a Client Secret** if you plan to use confidential flows.
    * *Certificates & secrets → New client secret.*
    * Store the value in a safe location (`local.settings.json` and source control are not appropriate places).
5. **Collect the IDs you will need locally:**
    * `AZURE_CLIENT_ID` – the API (server) registration ID.
    * `AZURE_TENANT_ID` – your Entra tenant ID.
    * `TEST_CLIENT_ID` – the client registration ID from step 1 (used when authenticating with MSAL or the Azure CLI).
6. **Request a token for the test client.**
    * If you are using the Azure CLI:

      ```bash
      az account get-access-token \
         --tenant "$AZURE_TENANT_ID" \
         --client-id "$TEST_CLIENT_ID" \
         --resource api://$AZURE_CLIENT_ID \
         --query accessToken -o tsv
      ```

    * Or use `python tools/get_access_token.py --client-id $TEST_CLIENT_ID --resource api://$AZURE_CLIENT_ID`.

Once the token flow succeeds you can copy the bearer token into Postman, curl, or the Swagger “Authorize” dialog to exercise the API.

---

## 🔍 Logging & Auditing Access

All authorization denials are logged with the user principal and operation.

Example:

```
[auth] Access denied for user: jsmith@contoso.com trying to audit_bulk
```

---

Next: [🗃 Table Schemas & Naming Rules](schema.md)
