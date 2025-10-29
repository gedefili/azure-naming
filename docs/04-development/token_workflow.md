# Obtaining a bearer token and dispatching the Postman workflow

This document collects the exact commands and short instructions to:

- obtain a short-lived Entra ID bearer token for local testing,
- export it into an environment variable, and
- dispatch the `postman.yml` workflow with the token as the `bearer_token` input.

Prerequisites

- Azure CLI (`az`) installed and you are logged in (`az login`).
- `python3` available and able to run `tools/get_access_token.py` in this repo (optional but recommended).
- `jq` installed for safe JSON handling.
- Either `gh` (GitHub CLI, recommended) configured or a GitHub PAT with `repo` + `workflow` scopes for the REST dispatch method.

Set these repo-specific values before running the examples below (replace with your values):

```bash
export GITHUB_OWNER="gedefili"
export GITHUB_REPO="azure-naming"
export WORKFLOW_FILE="postman.yml"   # file under .github/workflows/
export REF="main"                    # branch to dispatch on
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

Section C — Dispatch the Postman workflow

C1. Using GitHub CLI (recommended)

```bash
# ensure gh is logged in (gh auth login)
gh workflow run $WORKFLOW_FILE -f bearer_token="$BEARER_TOKEN" --repo $GITHUB_OWNER/$GITHUB_REPO --ref $REF
```

C2. Using REST API + curl (requires a PAT in $GITHUB_PAT)

```bash
export GITHUB_PAT="<YOUR_PAT>"

jq -n --arg ref "$REF" --arg bt "$BEARER_TOKEN" '{ref:$ref, inputs:{bearer_token:$bt}}' > /tmp/dispatch_payload.json

curl -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: token $GITHUB_PAT" \
  "https://api.github.com/repos/$GITHUB_OWNER/$GITHUB_REPO/actions/workflows/$WORKFLOW_FILE/dispatches" \
  --data @/tmp/dispatch_payload.json -v
```

C3. Dispatch via the GitHub Actions UI

- Go to the repository → Actions → select **Postman collection** → **Run workflow**.
- Choose branch and paste the token into the `bearer_token` field and click **Run workflow**.

Section D — Troubleshooting

- 204 No Content from the dispatch endpoint: success; check Actions → workflow runs for the started run.
- 403 from the REST API: your PAT does not have the required scopes (add `repo` and `workflow`) or token is invalid.
- Token rejected by the API: confirm the token audience/resource matches the API registration (usually `api://<AZURE_CLIENT_ID>`). If the function host is validating roles, ensure the account used has the assigned app role (Reader/Contributor/Admin).
- If the helper fails: run `python3 tools/get_access_token.py` without redirecting stderr so you can see any error details.

Security note

- Avoid committing bearer tokens to the repository or storing long-lived tokens as repository secrets. Prefer short-lived tokens for manual dispatches and local runs.

---

If you want, I can also add a tiny convenience script `scripts/dispatch_postman.sh` that: extracts the token via the helper and dispatches the workflow with `gh`. Say the word and I will add it (and include a one-line dry-run option).