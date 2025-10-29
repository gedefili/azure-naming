# 📖 API Reference

Complete API specifications, endpoint documentation, and data schema references.

## Documents

- **[Usage & Endpoints](usage.md)** — Comprehensive endpoint reference with request/response examples
- **[Data Schema](schema.md)** — Azure Table Storage schema, naming rules, and provider architecture

## All Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/claim` | POST | Generate and claim a new name |
| `/api/slug` | GET | Look up the slug for a resource type |
| `/api/release` | POST | Release or recycle a previously claimed name |
| `/api/audit` | GET | Query audit logs for a specific name |
| `/api/audit_bulk` | GET | Bulk audit queries by user, project, or time range |
| `/api/slug_sync` | POST | Manually trigger slug synchronization |
| `/api/docs` | GET | Interactive Swagger/OpenAPI UI |
| `/api/openapi.json` | GET | OpenAPI 3.0 specification (machine-readable) |

## Authentication

All endpoints require an `Authorization: Bearer <token>` header with a valid Entra ID token. 

**Token Acquisition:**
- CLI/Testing → [Token Workflow](../04-development/token_workflow.md)
- Setup → [App Registration Guide](../02-getting-started/app-registration.md)

## Data Models

See [Data Schema](schema.md) for detailed information about:
- Azure Table Storage schema (ClaimedNames, AuditLogs, SlugMappings)
- Naming rules and validation
- Slug provider architecture
- JSON rule format

## Testing Endpoints

- **Postman** → [Postman Testing](../04-development/postman.md)
- **curl/CLI** → [Token Workflow](../04-development/token_workflow.md)
- **Local Setup** → [Local Testing](../04-development/local-testing.md)

## Quick Links

- [Back to Main Index](../index.md)
- [Full Documentation](../index.md#-api-reference)
- [Usage Examples](usage.md) — Start here for endpoint examples
