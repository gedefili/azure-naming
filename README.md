# 🧭 Azure Naming Function

This project provides a secure, auditable, and standards-compliant Azure naming service. It uses Azure Functions, Table Storage, and Entra ID for identity and access control.

<!-- Architecture Diagram -->
```mermaid
graph TD
    User[User] -->|"HTTPS request"| AzureFn["Azure Functions"]
    AzureFn -->|"Validate token"| EntraID["Entra ID"]
    AzureFn -->|"Read/Write"| Table["Azure Table Storage"]
    AzureFn -->|"Fetch slugs"| GitHub["GitHub"]
    Timer["slug_sync_timer"] -->|"Weekly trigger"| AzureFn
    Table --> ClaimedNames[("ClaimedNames")]
    Table --> AuditLogs[("AuditLogs")]
    Table --> SlugMappings[("SlugMappings")]
    GitHub -->|"Slug specs"| SlugMappings
```

---

## 📂 Folder Structure

| Folder             | Purpose                                         |
| ------------------ | ----------------------------------------------- |
| `function_app.py`  | Azure Functions v2 entry points (HTTP + Timer)  |
| `utils/`           | Shared modules (auth, slug fetcher, validation) |
| `docs/`            | Project documentation                           |

---

## 🧠 Features

* ✅ Slug-based, consistent naming generation
* 🔐 Role-based access control (Entra ID)
* 🧾 Audit logs and user history
* ♻️ Release + recycle name logic
* 🔁 Slug sync from Azure naming standards

---

## 📄 Endpoints

* `POST /api/claim` — generate and reserve a name
* `POST /api/generate` — legacy alias for claim
* `POST /api/release` — release an existing name
* `GET  /api/audit?name=` — audit a single name
* `GET  /api/audit_bulk?...` — audit a user/project/time
* `POST /api/slug_sync` — manually refresh slugs
* `GET  /api/docs` — interactive Swagger UI for every endpoint
* `GET  /api/openapi.json` — machine-readable OpenAPI 3.0 document

Each endpoint requires an `Authorization: Bearer <token>` header issued by Entra ID.

### 🔑 App Roles

Assign one of the custom app roles to callers in Entra ID:

| Role | Permissions |
| ---- | ----------- |
| **Sanmar Naming Reader** | View OpenAPI docs and query audits for your own activity. |
| **Sanmar Naming Contributor** | Generate/release names and query audits. |
| **Sanmar Naming Admin** | Everything above plus slug sync and cross-user audits. |

Tokens are validated server-side; no function keys are required.

---

## 🚀 Deploying

* Provision Azure Storage + Function App (see [deployment.md](docs/deployment.md))
* Create Tables: `ClaimedNames`, `AuditLogs`, `SlugMappings`
* Register app in Entra, assign roles

---

## 📚 Documentation

* [📘 Usage](docs/usage.md)
* [🔐 Authentication & RBAC](docs/auth.md)
* [🗃 Schemas & Naming Rules](docs/schema.md)
* [🚀 Deployment Guide](docs/deployment.md)
* [🧪 Local Development, Swagger & Postman](docs/local-testing.md)
