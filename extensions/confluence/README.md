# Azure Naming Confluence Extension (Forge)

A Forge app that embeds a **Claim Azure Name** macro in any Confluence page.
Authors pick a resource type, region, and environment, click **Claim**, and the
page renders the canonical name issued by the Azure Naming Service.

## Why Forge (not Connect)?

Forge isolates extension code from the Confluence runtime, takes care of
hosting, scopes, and storage, and lets us pin egress to our backend domain
through `permissions.external.fetch.backend`. The naming spec calls Forge out
explicitly as the right choice.

## Layout

```
extensions/confluence/
├── manifest.yml          # Forge module + permission manifest
├── package.json
├── tsconfig.json
├── src/
│   ├── index.tsx         # UI Kit macro + resolver entrypoints
│   └── api.ts            # Backend HTTP client + Entra token caching
└── README.md
```

## Permissions

| Scope | Why |
|-------|-----|
| `read:page:confluence` | Resolve the page context for the macro |
| `write:page.property:confluence` | Persist a `sanmar.naming.claims` property pointing at the canonical claim |
| `read:user:confluence` | Surface the editor's identity for audit context |
| External fetch backend: `https://aznaming.sanmar.com`, `https://login.microsoftonline.com` | Hit the naming API and Entra token endpoint |

## Authentication

The Forge backend performs a `client_credentials` token request against
Entra using a service-principal Forge app registration. The access token
is cached for the duration of `expires_in - 60s`. Every API call sends:

- `Authorization: Bearer <token>`
- `X-Sanmar-Source: confluence-forge`

The naming API audit log uses the source header to attribute changes to the
extension while still recording the calling app principal.

## Local development

```bash
cd extensions/confluence
npm install
forge register   # one-time, creates ari:cloud:ecosystem::app/SANMAR_NAMING
forge variables set ENTRA_TENANT_ID …
forge variables set ENTRA_CLIENT_ID …
forge variables set NAMING_API_BASE_URL https://aznaming.sanmar.com
forge variables set NAMING_API_RESOURCE api://<naming-api-client-id>
forge variables set --encrypt ENTRA_CLIENT_SECRET …
forge deploy
forge install --site sanmar.atlassian.net --product confluence
```

## Macro behaviour

1. Author inserts the macro on a page, opens the gear, and picks
   `resourceType`, `region`, `environment`, and an optional `project`.
2. The macro shows the placeholder until **Claim Name** is clicked.
3. The Forge resolver POSTs `/api/claim` with `source: confluence-forge`.
4. On success, the canonical name is rendered as bold text along with the
   region/environment chip.
5. The macro does not currently re-fetch on view (sub-issue follow-up).

## Page property contract

When a name is claimed, the macro stores the claim id in a page property
`sanmar.naming.claims` with the schema:

```json
{
  "items": [
    {
      "name": "wus2-prd-st-aznaming",
      "resource_type": "storage_account",
      "region": "wus2",
      "environment": "prd",
      "claimed_by": "user@sanmar.com",
      "claimed_at": "2026-04-26T15:04:05Z"
    }
  ]
}
```

This is documented in
`/workspaces/docs-iac/projects/platform/azure-naming-experience/confluence-extension-spec.md`.

## Residual work

- Wire `storage.secret('entra-client-secret')` for the secret instead of
  `process.env.ENTRA_CLIENT_SECRET`. Forge variables marked `--encrypt`
  are exposed via `process.env`, but the API for `storage.secret` is
  preferred for rotation.
- Persist the claim onto the page property after success.
- Add a "Release" path on the macro for the original claimer.
- Wire `forge tunnel` for live debugging.
