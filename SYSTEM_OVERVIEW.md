# Azure Naming Service — System Overview

## Executive Summary

The Azure Naming Service is a secure, auditable REST API built on Azure Functions v2 that generates, tracks, and manages compliant Azure resource names. The service uses Azure Table Storage for persistence, Entra ID for authentication, and follows enterprise standards for naming conventions across cloud infrastructure.

## Architecture

**Core Components:**
- **Azure Functions** (HTTP triggers + Timer triggers) — RESTful API endpoints and scheduled slug synchronization
- **Azure Table Storage** — Three main tables persist all application state: `ClaimedNames`, `AuditLogs`, and `SlugMappings`
- **Entra ID** — OAuth 2.0 token validation and role-based access control (three roles: Reader, Contributor, Admin)

**Data Flow:**
Users send authenticated HTTPS requests to Function endpoints, which validate tokens against Entra ID, apply naming rules loaded from JSON configuration, reserve names in Table Storage, and return auditable responses. A weekly timer trigger synchronizes slug mappings (e.g., resource type short codes) from external sources into the `SlugMappings` table.

## Key Features

| Feature | Description |
|---------|-------------|
| **Name Generation** | RESTful claim endpoint (`POST /api/claim`) accepts resource type, region, environment, and optional metadata to generate unique, compliant names following JSON-defined rules |
| **Name Lifecycle** | Names transition through states: claimed (in-use), released (recyclable), with full audit trail of all operations |
| **Slug Resolution** | Provider chain resolves resource type slugs (e.g., `storage_account` → `stg`) with pluggable sources and Table Storage fallback |
| **Audit Logging** | Every claim, release, and sync operation logged with user identity, timestamp, and metadata in `AuditLogs` table |
| **Role-Based Access** | Three Entra ID roles grant granular permissions: read-only access, contributor (full API), or admin (cross-user audits) |
| **Extensible Rules** | Naming rules in `/rules/*.json` define templates, patterns, and allowed values per resource type and region |

## Storage Design

**ClaimedNames Table:**
- Partition Key: `{region}-{environment}` (e.g., `wus2-prod`)
- Row Key: Generated name (e.g., `stg-sds-prod-wus2-001`)
- Columns: `InUse` (bool), `ResourceType`, `ClaimedBy` (user), `ClaimedAt` (timestamp), `Metadata` (JSON), `ReleasedAt` (nullable)
- Concurrency: ETag-based optimistic locking prevents duplicate claims

**AuditLogs Table:**
- Partition Key: `{user_id}` (Entra object ID)
- Row Key: Reverse timestamp + operation ID for time-ordered queries
- Columns: Operation (claim/release/sync), Name, ResourceType, Status, Error, Metadata
- Purpose: Complete audit trail for compliance and debugging

**SlugMappings Table:**
- Partition Key: `default`
- Row Key: Resource type identifier (e.g., `storage_account`)
- Columns: `Slug`, `FullName`, `Source` (provider name), `UpdatedAt` (sync timestamp)
- Purpose: Cache for slug resolution; synced weekly via timer trigger

## Development Stack

- **Language:** Python 3.11
- **Framework:** Azure Functions v2 with FastAPI-style routing
- **Dependencies:** `azure-functions`, `azure-data-tables`, `azure-functions-openapi`, `PyJWT`, `requests`, `pytest`
- **Validation:** Pydantic models enforce request/response schemas
- **Testing:** Pytest with coverage; local testing via Azurite (Azure Storage emulator)

## API Endpoints

| Endpoint | Method | Purpose | Role |
|----------|--------|---------|------|
| `/api/claim` | POST | Generate and reserve a name | Contributor+ |
| `/api/release` | POST | Return a name to available pool | Contributor+ |
| `/api/slug` | GET | Resolve resource type slug | Reader+ |
| `/api/audit` | GET | Query audit logs for own activity | Reader+ |
| `/api/audit_bulk` | GET | Query audit logs by user/project | Admin |
| `/api/slug_sync` | POST | Manually refresh slug mappings | Admin |
| `/api/docs` | GET | Interactive Swagger UI | Reader+ |

## Production Considerations

- **Deployment:** Azure Functions (Consumption or Premium plan), Table Storage (Standard tier)
- **Scaling:** Serverless auto-scaling; Table Storage handles millions of requests/day
- **Security:** HTTPS only, token validation on every request, no function keys required
- **Monitoring:** Application Insights integration for logging and alerting

### Cost Projection

**Usage Scenario:** 10 API calls/day × 5 days/week = 50 executions/week = 2,600/year

**Annual Breakdown:**
- **Azure Functions:** 2,600 executions @ $0.20/million = ~$0.01
- **Table Storage:** ~2,600 read/write operations @ $0.01/10K operations = ~$0.26
- **Data ingress/egress:** Minimal (internal traffic); ~$0 for typical office-to-cloud patterns
- **Application Insights:** Included in free tier for this volume
- **Total Estimated Annual Cost:** **$0.50–2.00** (negligible; well below free tier thresholds)

**Note:** Azure's free tier provides 1M executions/month and 5GB Table Storage queries/month, so this workload operates completely within free tier limits.

## File Organization

| Directory | Purpose |
|-----------|---------|
| `core/` | Domain logic: name generation, slug resolution, validation |
| `adapters/` | External integrations: Table Storage, audit logs, slug providers |
| `app/` | HTTP layer: routes, request/response models, dependency injection |
| `rules/` | JSON naming rule definitions per resource type |
| `providers/` | Pluggable slug resolution strategies |
| `docs/` | Comprehensive guides: setup, deployment, API reference |

---

**For detailed documentation**, see `docs/index.md` for guides on deployment, local development, authentication, and API usage.
