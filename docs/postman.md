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

Requests included

- Slug Lookup — GET `/api/slug?resource_type=storage_account`
- Slug Sync — POST `/api/slug_sync` (admin operation)
- Claim Name — POST `/api/claim` (JSON body included)
- Release Name — POST `/api/release` (JSON body included)

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

- If requests return 500 / connection refused, confirm the function host is running and Azurite (or the configured Table Storage) is available.
- If slug lookup returns 404, run the `Slug Sync` request and confirm `SlugMappings` contains the expected slug.

If you'd like, I can add a short README snippet that links to `docs/postman.md` from `tests/readme.md` so contributors discover it more easily.
