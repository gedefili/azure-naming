# ops(deploy): Trigger slug sync after every application deployment

Tracked as Azure DevOps Issue `462296`.

## Problem

Azure Naming deployments currently publish code to the Function App and stop
there. Slug data is only refreshed when an operator manually calls
`POST /api/slug_sync` or when the weekly `slug_sync_timer` runs.

That leaves a deployment gap:

* newly deployed code may rely on the latest slug source immediately
* a fresh environment can remain partially usable until slug data is imported
* operators have to remember a manual post-deploy step for every rollout

## Root Cause

The deploy workflow in `.github/workflows/deploy.yml` only publishes the
Function App package. It does not perform any post-deploy initialization.

The application already exposes the required initialization hook via the
admin-protected `POST /api/slug_sync` endpoint, but no automation calls it as
part of deployment.

## Required Change

Update the deploy workflow to perform the slug sync after a successful publish:

1. Resolve the deployed Function App hostname from Azure.
2. Read the app registration client ID from the Function App's
   `AZURE_CLIENT_ID` app setting.
3. Acquire a bearer token for `api://<AZURE_CLIENT_ID>/.default` using the
   same Azure login context as the deployment.
4. Call `POST /api/slug_sync` with retries while the app warms up.
5. Fail the workflow if slug sync never succeeds.

## Operational Requirement

The service principal behind `AZURE_CREDENTIALS` must have the Azure Naming API
`admin` app role. Without that role assignment, the post-deploy call will
authenticate successfully with Azure but still fail authorization at the app
layer with `403 Forbidden`.

## Verification

After rollout, every successful deployment should show:

* Function App publish completed successfully
* post-deploy slug sync returned HTTP `200`
* response body confirming created/updated/existing slug counts

Manual fallback remains available:

```bash
TOKEN=$(az account get-access-token \
  --scope "api://<AZURE_CLIENT_ID>/.default" \
  --query accessToken -o tsv)

curl -X POST "https://<function-app>.azurewebsites.net/api/slug_sync" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{}'
```

## Resolution

Resolved in `v1.8.2` by updating `.github/workflows/deploy.yml` and the
deployment runbook so slug synchronization is part of the standard deployment
path instead of a manual follow-up task.