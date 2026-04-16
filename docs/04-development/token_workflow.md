# Obtaining a bearer token and queueing the Azure DevOps Postman run

This document collects the exact commands and short instructions to:

- obtain a short-lived Entra ID bearer token for local testing,
- export it into an environment variable, and
- queue the Azure DevOps `azure-naming` pipeline with the Postman stage enabled.

Prerequisites

- Azure CLI (`az`) installed and you are logged in (`az login`).
- `python3` available and able to run `tools/get_access_token.py` in this repo (optional but recommended).
- `jq` installed for safe JSON handling.
- Azure DevOps CLI configured for the `Infrastructure Administration` project.

Set these repo-specific values before running the examples below (replace with your values):

```bash
export ADO_ORG="https://dev.azure.com/sanmarcloud"
export ADO_PROJECT="Infrastructure Administration"
export PIPELINE_NAME="azure-naming"
export REF="main"                    # branch to queue on
export AZURE_CLIENT_ID="<AZURE_CLIENT_ID>"  # the API app registration for the naming API
```

Section A — Obtain a token

A1. Quick (Azure CLI)

Print a token to stdout:

```bash
az account get-access-token --resource api://$AZURE_CLIENT_ID --query accessToken -o tsv
```

Export it into an env var:

```bash
export BEARER_TOKEN="$(az account get-access-token --resource api://$AZURE_CLIENT_ID --query accessToken -o tsv)"
```

A2. Recommended: use the repo helper (wraps az and shows claims)

This helper prints the raw token between clear markers and optionally decoded claims.

```bash
python3 tools/get_access_token.py --show-claims --client-id "$AZURE_CLIENT_ID"
```

To extract the token automatically and export it:

```bash
export BEARER_TOKEN="$(python3 tools/get_access_token.py --client-id "$AZURE_CLIENT_ID" 2>/dev/null \
  | sed -n '/^=== Bearer Token ===$/,/^=== End Token ===$/p' \
  | sed '1d;$d' \
  | tr -d '\n')"
```

Quick check:

```bash
echo "token length: $(echo -n "$BEARER_TOKEN" | wc -c)"
```

A2b. Save the token directly into your local `.env`

If you already have a token:

```bash
python3 tools/save_access_token.py --token "$BEARER_TOKEN" --show-claims
```

If Azure CLI is available and your IDs are set:

```bash
export AZURE_TENANT_ID="<tenant-id>"
export AZURE_CLIENT_ID="<api-app-id>"

python3 tools/save_access_token.py --show-claims
```

This writes `FUNCTION_BASE_URL`, `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `TEST_CLIENT_ID`, and `ACCESS_TOKEN` into the local `.env` file.

If you want to persist a testing client ID for other auth flows, pass it explicitly when saving or updating the env file:

```bash
python3 tools/save_access_token.py --token "$BEARER_TOKEN" --test-client-id "<public-client-id>"
```

Note: `tools/save_access_token.py` uses `az account get-access-token` for Azure CLI flows, and that command requests tokens as the signed-in Azure CLI client. It does not support overriding the client application with `TEST_CLIENT_ID`.

A3. Non-interactive (client credentials — requires app registration + secret)

```bash
curl -s -X POST "https://login.microsoftonline.com/<TENANT_ID>/oauth2/v2.0/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "client_id=<CLIENT_ID>&scope=<API_SCOPE>&client_secret=<CLIENT_SECRET>&grant_type=client_credentials" \
  | jq -r .access_token > /tmp/bearer_token.txt

export BEARER_TOKEN="$(cat /tmp/bearer_token.txt)"
```

Section B — Verify token locally (optional)

Run a quick Newman run locally using the token before dispatching the workflow:

```bash
jq --arg token "$BEARER_TOKEN" '.values |= map(if .key=="auth_token" then .value=$token else . end)' tests/postman_environment.json > /tmp/env.json
npx newman run tests/postman_collection.json -e /tmp/env.json --insecure
```

Section C — Queue the Postman stage in Azure DevOps

C1. Queue from the Azure DevOps CLI

```bash
az pipelines run \
  --organization "$ADO_ORG" \
  --project "$ADO_PROJECT" \
  --name "$PIPELINE_NAME" \
  --branch "$REF" \
  --parameters runPostman=true postmanBearerToken="$BEARER_TOKEN" postmanBaseUrl="https://wus2-prd-fn-aznaming.azurewebsites.net"
```

C2. Queue without an auth token

```bash
az pipelines run \
  --organization "$ADO_ORG" \
  --project "$ADO_PROJECT" \
  --name "$PIPELINE_NAME" \
  --branch "$REF" \
  --parameters runPostman=true
```

C3. Queue from the Azure DevOps UI

- Go to **Pipelines** in Azure DevOps and open the `azure-naming` pipeline.
- Click **Run pipeline**.
- Set `runPostman` to `true`.
- Optionally paste a short-lived bearer token into `postmanBearerToken` and set `postmanBaseUrl`.
- Start the run.

Section D — Troubleshooting

- If the queue command fails, confirm `az devops configure` is pointing at the correct organization and project.
- If Azure DevOps rejects the parameters, confirm the `azure-naming` pipeline has been created from `azure-pipelines.yml`.
- Token rejected by the API: confirm the token audience/resource matches the API registration (usually `api://<AZURE_CLIENT_ID>`). If the function host is validating roles, ensure the account used has the assigned app role (Reader/Contributor/Admin).
- If the helper fails: run `python3 tools/get_access_token.py` without redirecting stderr so you can see any error details.

Security note

- Avoid committing bearer tokens to the repository or storing long-lived tokens as pipeline secrets. Prefer short-lived tokens for manual runs and local testing.