#!/usr/bin/env bash
set -euo pipefail

# Automates creation of a public client application that can request tokens for the Azure Naming API.

if ! command -v az >/dev/null 2>&1; then
  echo "Azure CLI (az) is required." >&2
  exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "jq is required." >&2
  exit 1
fi

if [[ -z "${AZURE_CLIENT_ID:-}" ]]; then
  echo "Set AZURE_CLIENT_ID to the API (server) application ID created earlier." >&2
  exit 1
fi

CLIENT_APP_NAME=${CLIENT_APP_NAME:-AzureNamingClient}
REDIRECT_URI=${REDIRECT_URI:-http://localhost}
TENANT_ID=$(az account show --query tenantId -o tsv)

if [[ -z "${TENANT_ID}" ]]; then
  echo "Run 'az login' before executing this script." >&2
  exit 1
fi

SCOPE_VALUE=${SCOPE_VALUE:-user_access}

RESOURCE_SCOPE_ID=$(az ad app show --id "${AZURE_CLIENT_ID}" --query "api.oauth2PermissionScopes[?value=='${SCOPE_VALUE}'].id" -o tsv)
if [[ -z "${RESOURCE_SCOPE_ID}" ]]; then
  echo "Scope '${SCOPE_VALUE}' not found on API ${AZURE_CLIENT_ID}. Set SCOPE_VALUE if you chose a different scope name." >&2
  exit 1
fi

RESOURCE_APP_OBJECT_ID=$(az ad app show --id "${AZURE_CLIENT_ID}" --query id -o tsv)

if [[ -z "${RESOURCE_APP_OBJECT_ID}" ]]; then
  echo "Unable to resolve API object ID." >&2
  exit 1
fi

echo "Creating client app '${CLIENT_APP_NAME}'..."
CLIENT_APP_ID=$(az ad app create \
  --display-name "${CLIENT_APP_NAME}" \
  --sign-in-audience AzureADMyOrg \
  --enable-public-client true \
  --public-client-redirect-uris "${REDIRECT_URI}" \
  --query appId -o tsv)

CLIENT_OBJECT_ID=$(az ad app show --id "${CLIENT_APP_ID}" --query id -o tsv)

REQUIRED_ACCESS=$(cat <<EOF
[{"resourceAppId":"${AZURE_CLIENT_ID}","resourceAccess":[{"id":"${RESOURCE_SCOPE_ID}","type":"Scope"}]}]
EOF
)

REQUIRED_ACCESS=$(echo "${REQUIRED_ACCESS}" | jq -c '.')

echo "Assigning delegated permission to API ${AZURE_CLIENT_ID}..."
az ad app update --id "${CLIENT_APP_ID}" --set requiredResourceAccess="${REQUIRED_ACCESS}"

echo "Creating service principal for client..."
az ad sp create --id "${CLIENT_APP_ID}" >/dev/null

echo "Granting admin consent for delegated scope..."
az ad app permission admin-consent --id "${CLIENT_APP_ID}" >/dev/null

cat <<INFO

Client registration complete.

Tenant ID:        ${TENANT_ID}
Client ID:        ${CLIENT_APP_ID}
Object ID:        ${CLIENT_OBJECT_ID}
Redirect URI:     ${REDIRECT_URI}
Requested scope:  ${SCOPE_VALUE} (from API ${AZURE_CLIENT_ID})

To request tokens from Cloud Shell:
  az account get-access-token --tenant "${TENANT_ID}" \
    --client-id "${CLIENT_APP_ID}" \
    --resource "api://${AZURE_CLIENT_ID}" \
    --query accessToken -o tsv

For the helper script:
  python3 tools/get_access_token.py --client-id "${CLIENT_APP_ID}" --resource "api://${AZURE_CLIENT_ID}" --show-claims
INFO
