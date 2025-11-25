# Postman collection: Azure Naming API

This document explains how to import and use the Postman collection included with the repository for local manual testing and automated validation.

## Collection Versions

There are two Postman collections available:

### Current: Comprehensive Collection with Test Suites (v1.7.1+)

- **Location:** `docs/04-development/postman-local-collection.json`
- **Latest & Recommended** — Includes 27 requests with full test coverage
- **Features:**
  - 4 endpoint groups: Slug (6 tests), Claim (7 tests), Release (8 tests), Audit/Rules (5 tests)
  - Automatic test assertions for each request
  - Multiple scenarios per endpoint (happy path, errors, auth failures, edge cases)
  - Environment variable auto-population for chained tests
  - Ready for automation with Newman CLI
- **Updated:** v1.7.1 (Oct 2025)

### Legacy: Basic Collection

- **Location:** `tests/postman_collection.json`
- **Status:** Superseded by comprehensive collection
- **Contains:** Basic 4 requests (Slug Lookup, Slug Sync, Claim Name, Release Name)
- **Note:** Use comprehensive collection instead for new work

## Using the Comprehensive Collection

### Quick Start: Import and Run

1. **Ensure your local stack is running** (see `tests/readme.md`):
   - Start Azurite (table storage emulator) with: `python3 tools/start_local_stack.py`
   - Start the Azure Functions host with: `func host start` (or use the VS Code task)
   - The function host typically listens on port 7071
   - **Both Azurite AND Functions host must be running before importing the collection**
2. Open Postman and choose File → Import.
3. Pick `docs/04-development/postman-local-collection.json` from the repository and import it.

### Configuring Host and Auth

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

## Test Suites and Assertions

The comprehensive collection includes **automatic test scripts** for each request. These validate responses in Postman.

### What Tests Are Included

**1. Slug Endpoints (6 tests)**
- ✅ Valid resource type lookup (storage_account) → returns 200 + slug
- ✅ Different valid type (cosmos_account) → returns 200 + valid slug
- ❌ Invalid/unknown resource type → returns 404 + error message
- ❌ Missing required parameter (resource_type) → returns 400
- ✅ Slug Sync successful execution → returns 200 + message with counts
- ❌ Slug Sync without authentication → returns 401 or 500

**2. Claim Name Endpoints (7 tests)**
- ✅ Happy path (storage_account) → returns 200 + name with all fields
- ✅ Different region variant (eus instead of wus2) → returns 200 + name contains "eus"
- ❌ Missing required field (region) → returns 400 + error about region
- ❌ Missing required field (environment) → returns 400 + error about environment
- ❌ Invalid JSON in request body → returns 400 + error about JSON
- ❌ Without authentication → returns 401
- Auto-saves claimed name for downstream release tests

**3. Release Name Endpoints (8 tests)**
- ✅ Happy path with claimed name → returns 200 + success message
- ✅ Simplified release (name only) → returns 200 or 400 depending on partition key logic
- ❌ Non-existent name → returns 404 + "not found" error
- ❌ Missing required field (name) → returns 400 + error about name
- ❌ Invalid JSON in request body → returns 400
- ❌ Without authentication → returns 401
- Additional scenarios for authorization testing

**4. Audit & Rules Endpoints (5 tests)**
- ✅ Get all audit logs → returns 200 + array response
- ✅ Get filtered audit logs by name → returns 200 + array response
- ✅ Describe storage_account rule → returns 200 + rule with maxLength and segments
- ✅ Describe default rule → returns 200 + rule with segments
- ❌ Describe unknown rule type → returns 400 or 404

### Running Tests in Postman UI

1. **Import collection** into Postman desktop app
2. **Set environment variables:**
   - `baseUrl`: `http://localhost:7071` (usually default)
   - `auth_token`: Leave empty for local dev, or provide Bearer token for secured testing
3. **Click "Runner" button** (or use Test → Run Collection)
4. **Select the collection** and all requests
5. **Click "Run"** — Postman will execute all requests with automatic assertions
6. **Review results:**
   - Green checks (✓) = assertions passed
   - Red X (✗) = assertion failed
   - Each failed assertion shows expected vs actual

### Running Tests with Newman (CLI)

For automated CI/CD pipelines:

```bash
# Install Newman (one-time)
npm install -g newman

# Run the collection against local environment
newman run docs/04-development/postman-local-collection.json \
  --reporters cli,json

# With custom environment variables
newman run docs/04-development/postman-local-collection.json \
  --globals <(echo '{"values":[{"key":"baseUrl","value":"http://localhost:7071"},{"key":"auth_token","value":"your-token"}]}') \
  --reporters cli,json,html \
  --reporter-html-export test-results.html
```

## Requests Included in Comprehensive Collection

**Group 1: Slug Endpoints (6 tests)**
1. **1.1 Slug Lookup - Valid Resource Type (storage_account)** — GET `/api/slug?resource_type=storage_account`
   - ✅ Validates that storage_account maps to "st" slug
2. **1.2 Slug Lookup - Different Valid Type (cosmos)** — GET `/api/slug?resource_type=cosmos`
   - ✅ Tests different resource type with dynamic slug validation (cosmos → cosmos_db)
3. **1.3 Slug Lookup - Invalid/Unknown Type** — GET `/api/slug?resource_type=unknown_resource_xyz`
   - ❌ Validates 404 error handling for unknown types
4. **1.4 Slug Lookup - Missing Parameter** — GET `/api/slug` (no query string)
   - ❌ Validates 400 error handling for missing required parameter
5. **1.5 Slug Sync - Fetch and Update** — POST `/api/slug_sync`
   - ⭐ **Run this first!** — Populates SlugMappings table
   - ✅ Validates sync completion and shows created/updated/existing counts
6. **1.6 Slug Sync - Without Authentication** — POST `/api/slug_sync` (no auth header)
   - ❌ Validates authentication requirement (401 or 500)

### Valid Resource Types

The Azure Naming API supports 86 resource types from the official [Azure Terraform naming repository](https://github.com/Azure/terraform-azurerm-naming). Common examples include:

- `storage_account` → `st`
- `cosmos` → `cosmos_db`
- `key_vault` → `kv`
- `function_app` → `func`
- `application_gateway` → `agw`
- `azure_sql_database_server` → `sql`

**Error:** If you use `cosmos_account` (wrong) instead of `cosmos` (correct), you'll get:
```
"Slug not found for resource type 'cosmos_account'."
```

To find all supported resource types, run:
```bash
cd azure-naming && python3 -c "from adapters.slug_fetcher import get_all_remote_slugs; slugs = get_all_remote_slugs(); print('\n'.join(f'{k}: {v}' for k,v in sorted(slugs.items())))"
```

**Group 2: Claim Name Endpoints (7 tests)**
1. **2.1 Claim Name - Happy Path (storage_account)** — POST `/api/claim`
   - ✅ Full request with all fields → returns 200 + name with all metadata
   - Auto-saves name for release tests
2. **2.2 Claim Name - Different Region** — POST `/api/claim` (region=eus)
   - ✅ Validates regional variation → name contains correct region
3. **2.3 Claim Name - Missing Required Field (region)** — POST `/api/claim` (no region)
   - ❌ Validates 400 error for missing region
4. **2.4 Claim Name - Missing Required Field (environment)** — POST `/api/claim` (no environment)
   - ❌ Validates 400 error for missing environment
5. **2.5 Claim Name - Invalid JSON** — POST `/api/claim` (malformed JSON body)
   - ❌ Validates 400 error for invalid JSON
6. **2.6 Claim Name - Without Authentication** — POST `/api/claim` (no auth header)
   - ❌ Validates 401 unauthorized
7. All claim requests validate response has name, resourceType, region, environment, slug, claimedBy

**Group 3: Release Name Endpoints (8 tests)**
1. **3.1 Release Name - Happy Path** — POST `/api/release` with claimed name
   - ✅ Uses saved name from claim test → returns 200 + success message
2. **3.2 Release Name - Simplified (name only)** — POST `/api/release` with name field only
   - ✅ Validates simplified API (region/environment optional) → expects 200 or 400
3. **3.3 Release Name - Non-Existent Name** — POST `/api/release` with fake name
   - ❌ Validates 404 error for non-existent resource
4. **3.4 Release Name - Missing Name Field** — POST `/api/release` (no name)
   - ❌ Validates 400 error for missing required field
5. **3.5 Release Name - Invalid JSON** — POST `/api/release` (malformed body)
   - ❌ Validates 400 error for invalid JSON
6. **3.6 Release Name - Without Authentication** — POST `/api/release` (no auth)
   - ❌ Validates 401 unauthorized
7. All release requests validate success message or appropriate error

**Group 4: Audit & Rules Endpoints (5 tests)**
1. **4.1 Get Audit Logs - All Records** — GET `/api/audit`
   - ✅ Returns all audit logs as array
2. **4.2 Get Audit Logs - Filtered by Name** — GET `/api/audit?name={{claimed_name}}`
   - ✅ Uses auto-saved name → returns filtered results
3. **4.3 Describe Naming Rule - storage_account** — GET `/api/rules/storage_account`
   - ✅ Returns rule with resourceType, maxLength, segments
4. **4.4 Describe Naming Rule - default** — GET `/api/rules/default`
   - ✅ Returns default rule with segments property
5. **4.5 Describe Naming Rule - Unknown Type** — GET `/api/rules/unknown_rule_type`
   - ❌ Validates 404 or 400 error for unknown rule

### Quick Usage Examples

**Claiming a storage account name:**
```json
{
  "resource_type": "storage_account",
  "region": "wus2",
  "environment": "prd",
  "system": "erp",
  "index": "01"
}
```

**Releasing a claimed name (full request):**
```json
{
  "name": "sammer-st-prd-wus2-erp01",
  "region": "wus2",
  "environment": "prd",
  "reason": "no longer needed"
}
```

**Releasing a claimed name (simplified):**
```json
{
  "name": "sammer-st-prd-wus2-erp01",
  "reason": "test complete"
}
```

## Troubleshooting

- **"Slug not found for resource type 'storage_account'"** — This means the `SlugMappings` table is empty. Run the "Slug Sync" request first to populate it.
  - If Slug Sync reports "0 entries updated/created":
    - Check that **Azurite is running**: `ps aux | grep azurite` should show an active process
    - If not running, start it: `python3 tools/start_local_stack.py`
    - Then retry Slug Sync
  - If Azurite is running but still getting 0 entries, GitHub fetch may have failed (network issue, offline, or corporate firewall). See [Local Development Without GitHub](#local-development-without-github) above.
- **Claim Name returns 500 / Slug Lookup returns 404** — First run "Slug Sync" to ensure `SlugMappings` contains the expected slugs.
- **Requests return connection refused** — Confirm:
  - Azurite (table storage) is running on port 10002: `netstat -tlnp | grep 10002` or `lsof -i :10002`
  - Functions host is running on port 7071: `lsof -i :7071`
  - If neither is running, start local stack: `python3 tools/start_local_stack.py` and `func host start`
- **Requests return 401 Unauthorized** — Confirm you have provided a valid bearer token in the `auth_token` collection variable, or disable auth in local dev mode.
- **Tests fail in Postman UI** — Check:
  - Collection variables are set (baseUrl, auth_token)
  - Environment is selected
  - Requests are run in order (Slug Sync before others)
  - HTTP responses match expected status codes

## Workflow & CI Integration

- The included GitHub workflows (`.github/workflows/postman.yml` and `.github/workflows/integration.yml`) accept an optional workflow input named `bearer_token` when run via "Run workflow" in the Actions UI. If provided, the value will be used to populate the Postman environment's `auth_token` variable for Newman runs. These workflows are input-only and do not read repository secrets.

If you need CI-run authenticated Newman requests consider either dispatching the workflow with a short-lived bearer token as the `bearer_token` input or running integration tests locally using `tools/run_integration_locally.py` with a token obtained via `tools/get_access_token.py`.
