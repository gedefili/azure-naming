# Azure Naming Web UX

Modern, dynamically-themed single-page web app for the SanMar Azure Naming
service.

- React 19 + Vite + TypeScript
- `@azure/msal-browser` PKCE login (Authorization Code with PKCE)
- TanStack Query for API state
- Runtime CSS-variable theming with deterministic per-user accent
- Lucide icons

## Layout

```
web/
├── package.json
├── vite.config.ts
├── tsconfig.json
├── index.html
├── public/
│   └── favicon.svg
└── src/
    ├── main.tsx              # entrypoint
    ├── App.tsx               # router + topbar
    ├── api/                  # API client + hook
    ├── auth/                 # MSAL config + token hook
    ├── components/           # ClaimsTable, ClaimDrawer, ConfirmDialog
    ├── pages/                # MyClaimsPage, AllClaimsPage, SettingsPage
    ├── styles/global.css     # CSS variables and base styles
    ├── theme/                # ThemeProvider + derivation helpers
    └── test-setup.ts
```

## Local development

```bash
cd web
npm install
cp .env.example .env.local
# edit .env.local with VITE_ENTRA_TENANT_ID, VITE_ENTRA_CLIENT_ID,
# VITE_NAMING_API_CLIENT_ID, VITE_NAMING_API_BASE_URL
npm run dev
```

The dev server runs at <http://localhost:5173> and proxies `/api/*` to the
local Functions host (default <http://localhost:7071>).

## Build

```bash
npm run build
```

Output goes to `dist/` and is published to the Static Web App by the
`build-web.yml` pipeline (provisioned in
`environs-iac/sanmar/applications/internal/azure-naming/web/`).

## Tests

```bash
npm test
```

Vitest + Testing Library + jsdom. Theme derivation is fully unit-tested.

## Configuration

| Env var | Purpose |
|---------|---------|
| `VITE_NAMING_API_BASE_URL` | Naming Service API base URL (e.g. `https://wus2-prd-fn-aznaming.azurewebsites.net`) |
| `VITE_ENTRA_TENANT_ID` | Entra tenant ID for MSAL authority |
| `VITE_ENTRA_CLIENT_ID` | This SPA's app registration client ID |
| `VITE_NAMING_API_CLIENT_ID` | The Naming Service API's app registration client ID (used to request `api://<id>/user_access`) |
| `VITE_APP_VERSION` | Optional version label shown on the Settings page |

## Authentication flow

1. User clicks **Sign in with Microsoft** → `loginRedirect`.
2. After redirect, MSAL stores the ID token in `sessionStorage`.
3. API calls go through `useApiClient`, which calls `acquireTokenSilent`
   for `api://<naming-api>/user_access` and attaches it as a bearer.
4. On 401, MSAL falls back to `acquireTokenRedirect`.
5. Roles are read from `idTokenClaims.roles`. The UI conditionally
   renders the **All Claims** and **Settings** admin features, but the
   server is the authoritative gate via `require_role` in every handler.

## Theming

The `ThemeProvider` resolves a `mode` (`auto`/`light`/`dark`) and a
`hue` (0-360) into a set of CSS custom properties applied to
`document.documentElement`. The default hue is derived from a hash of
the signed-in user's username and constrained to a SanMar-friendly band.
Users can override via the Settings page.

All accent shades are paired with a precomputed accessible text color
(via `oklch()` lightness adjustment), so a random hue never breaks
contrast.

## Security

- Tokens live in `sessionStorage` only.
- Every fetch sets `Authorization: Bearer …` and `X-Sanmar-Source: web`
  so the audit log can distinguish web traffic from CLI or Confluence.
- Destructive actions (release, purge) require typed confirmation.
- The CSP recommended for the deployed Static Web App is documented in
  the project spec at
  `/workspaces/docs-iac/projects/platform/azure-naming-experience/web-ux-spec.md`.
