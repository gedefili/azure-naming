# Postman collection: Azure Naming API

This document explains how to import and use the Postman collection included with the repository for local manual testing.

Location

- The collection file is: `tests/postman_collection.json`

Importing the collection

1. **Ensure your local stack is running** (see `tests/readme.md`):
   - Start Azurite (table storage emulator) with: `python3 tools/start_local_stack.py`
   - Start the Azure Functions host with: `func host start` (or use the VS Code task)
   - The function host typically listens on port 7071
   - **Both Azurite AND Functions host must be running before importing the collection**
2. Open Postman and choose File → Import.
3. Pick `docs/04-development/postman-local-collection.json` from the repository and import it.

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
   - **Note:** Slug Sync fetches definitions from GitHub (`Azure/terraform-azurerm-naming` repo). If the sync reports "0 entries updated/created", check:
     - Network connectivity (GitHub must be reachable)
     - If offline/no internet, see [Local Development Without GitHub](#local-development-without-github) below
2. **Then run "Slug Lookup"** — Verify the slug was synced correctly
3. **Then run "Claim Name"** — Generate and reserve a name
4. **Finally run "Release Name"** — Release a claimed name back to the pool

### Local Development Without GitHub

If you cannot reach GitHub (offline development, corporate firewall, etc.), the Slug Sync will fail with "0 entries updated/created". To work around this:

1. **Option A: Use pre-seeded test data** (recommended for quick testing)
   - Run the integration tests which pre-populate slugs:
     ```bash
     python3 tools/run_integration_locally.py
     ```
   - This adds sample slugs to `SlugMappings` table
   - Then use Postman to test with those slugs

2. **Option B: Manually seed the table** 
   - Insert a test row directly into Azurite:
     ```bash
     # Use Azure Storage Explorer or run this Python snippet
     from tools.lib import storage_config
     from azure.data.tables import TableClient
     
     table = TableClient.from_connection_string(
         storage_config.AZURITE_CONNECTION_STRING,
         table_name="SlugMappings"
     )
     table.upsert_entity({
         "PartitionKey": "slug",
         "RowKey": "st",
         "FullName": "storage_account"
     })
     ```
   - Then use Postman with `storage_account` as the resource type

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
  - If Slug Sync reports "0 entries updated/created":
    - Check that **Azurite is running**: `ps aux | grep azurite` should show an active process
    - If not running, start it: `python3 tools/start_local_stack.py`
    - Then retry Slug Sync
  - If Azurite is running but still getting 0 entries, GitHub fetch may have failed (network issue, offline, or corporate firewall). See [Local Development Without GitHub](#local-development-without-github) below.
- **Claim Name returns 500 / Slug Lookup returns 404** — First run "Slug Sync" to ensure `SlugMappings` contains the expected slugs.
- **Requests return connection refused** — Confirm:
  - Azurite (table storage) is running on port 10002: `netstat -tlnp | grep 10002` or `lsof -i :10002`
  - Functions host is running on port 7071: `lsof -i :7071`
  - If neither is running, start local stack: `python3 tools/start_local_stack.py` and `func host start`
- **Requests return 401 Unauthorized** — Confirm you have provided a valid bearer token in the `auth_token` collection variable, or disable auth in local dev mode.

If you'd like, I can add a short README snippet that links to `docs/postman.md` from `tests/readme.md` so contributors discover it more easily.

Workflow & CI notes

- The included GitHub workflows (`.github/workflows/postman.yml` and `.github/workflows/integration.yml`) accept an optional workflow input named `bearer_token` when run via "Run workflow" in the Actions UI. If provided, the value will be used to populate the Postman environment's `auth_token` variable for Newman runs. These workflows are input-only and do not read repository secrets.

If you need CI-run authenticated Newman requests consider either dispatching the workflow with a short-lived bearer token as the `bearer_token` input or running integration tests locally using `tools/run_integration_locally.py` with a token obtained via `tools/get_access_token.py`.
