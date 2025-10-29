# Postman collection: Azure Naming API

This document explains how to import and use the Postman collection included with the repository for local manual testing.

Location

- The collection file is: `tests/postman_collection.json`

Importing the collection

1. Start your local stack and function host (see `tests/readme.md`). The function host typically listens on port 7071.
2. Open Postman and choose File → Import.
3. Pick `tests/postman_collection.json` from the repository and import it.

Configuring host and auth

- The collection uses `http://localhost:7071` by default. If your host uses a different port or address, update the request URLs or set an environment with a variable for the host.
- Most endpoints may require authentication depending on your configuration. For local testing you can:
  - Disable auth in the function host (local dev mode), or
  - Add an `Authorization: Bearer <token>` header to the requests in the collection.

## Getting Started: Required Setup Order

⚠️ **Important:** You must run requests in the correct order. Follow these steps:

1. **Run "Slug Sync (POST)" first** — This populates the `SlugMappings` table with slug definitions for all resource types
   - This is an admin operation and must be run before claiming names
   - Without this, all "Claim Name" requests will fail with `ValueError: Slug not found`
2. **Then run "Slug Lookup"** — Verify the slug was synced correctly
3. **Then run "Claim Name"** — Generate and reserve a name
4. **Finally run "Release Name"** — Release a claimed name back to the pool

Requests included

1. **Slug Sync** — POST `/api/slug_sync` ⭐ **Run this first!**
   - Populates the `SlugMappings` table with slug definitions
   - Admin operation; required before claiming names
2. **Slug Lookup** — GET `/api/slug?resource_type=storage_account`
   - Verifies the slug was synced for a given resource type
3. **Claim Name** — POST `/api/claim` (JSON body included)
   - Generates and reserves a name (requires slug to exist)
4. **Release Name** — POST `/api/release` (JSON body included)
   - Releases a previously claimed name back to the pool

Quick usage notes

- Run `Slug Sync` first to populate the `SlugMappings` table if your table is empty.
- `Claim Name` expects a JSON body with at least the following fields (example):

```json
{
  "resourceType": "storage_account",
  "region": "wus2",
  "environment": "prod",
  "slug": "st",
  "optional_inputs": {}
}
```

- `Release Name` expects the partitioning keys to identify the claimed name (example):

```json
{
  "region": "wus2",
  "environment": "prod",
  "name": "sanmar-st-prod-wus2"
}
```

Troubleshooting

- **"Slug not found for resource type 'storage_account'"** — This means the `SlugMappings` table is empty. Run the "Slug Sync" request first to populate it.
- **Claim Name returns 500 / Slug Lookup returns 404** — First run "Slug Sync" to ensure `SlugMappings` contains the expected slugs.
- **Requests return connection refused** — Confirm the function host is running on port 7071 and Azurite (or your configured Table Storage) is available.
- **Requests return 401 Unauthorized** — Confirm you have provided a valid bearer token in the `auth_token` collection variable, or disable auth in local dev mode.

If you'd like, I can add a short README snippet that links to `docs/postman.md` from `tests/readme.md` so contributors discover it more easily.

Workflow & CI notes

- The included GitHub workflows (`.github/workflows/postman.yml` and `.github/workflows/integration.yml`) accept an optional workflow input named `bearer_token` when run via "Run workflow" in the Actions UI. If provided, the value will be used to populate the Postman environment's `auth_token` variable for Newman runs. These workflows are input-only and do not read repository secrets.

If you need CI-run authenticated Newman requests consider either dispatching the workflow with a short-lived bearer token as the `bearer_token` input or running integration tests locally using `tools/run_integration_locally.py` with a token obtained via `tools/get_access_token.py`.
