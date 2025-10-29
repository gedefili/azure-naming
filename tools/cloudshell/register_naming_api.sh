#!/usr/bin/env bash
set -euo pipefail

# Automates creation of the Azure Naming API app registration with roles and scope.

if ! command -v az >/dev/null 2>&1; then
  echo "Azure CLI (az) is required." >&2
  exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "jq is required." >&2
  exit 1
fi

API_APP_NAME=${API_APP_NAME:-AzureNamingService}
SCOPE_NAME=${SCOPE_NAME:-user_access}
TENANT_ID=$(az account show --query tenantId -o tsv)

if [[ -z "${TENANT_ID}" ]]; then
  echo "Run 'az login' before executing this script." >&2
  exit 1
fi

echo "Creating app registration '${API_APP_NAME}' in tenant ${TENANT_ID}..."
API_APP_ID=$(az ad app create \
  --display-name "${API_APP_NAME}" \
  --sign-in-audience AzureADMyOrg \
  --query appId -o tsv)

API_OBJECT_ID=$(az ad app show --id "${API_APP_ID}" --query id -o tsv)

echo "Configuring application ID URI..."
az ad app update --id "${API_APP_ID}" --set identifierUris="['api://${API_APP_ID}']"

READER_ROLE_ID=$(uuidgen)
CONTRIBUTOR_ROLE_ID=$(uuidgen)
ADMIN_ROLE_ID=$(uuidgen)

APP_ROLES=$(cat <<EOF
[
  {"allowedMemberTypes":["User"],"description":"View docs and own audit history","displayName":"Sanmar Naming Reader","id":"${READER_ROLE_ID}","isEnabled":true,"value":"reader","origin":"Application"},
  {"allowedMemberTypes":["User"],"description":"Generate and release names","displayName":"Sanmar Naming Contributor","id":"${CONTRIBUTOR_ROLE_ID}","isEnabled":true,"value":"contributor","origin":"Application"},
  {"allowedMemberTypes":["User"],"description":"Administrative access including slug sync","displayName":"Sanmar Naming Admin","id":"${ADMIN_ROLE_ID}","isEnabled":true,"value":"admin","origin":"Application"}
]
EOF
)

APP_ROLES=$(echo "${APP_ROLES}" | jq -c '.')

echo "Applying app roles..."
az ad app update --id "${API_APP_ID}" --set appRoles="${APP_ROLES}"

SCOPE_ID=$(uuidgen)
OAUTH_SCOPES=$(cat <<EOF
[{"adminConsentDescription":"Allows access to Azure Naming endpoints.","adminConsentDisplayName":"Access Azure Naming API","id":"${SCOPE_ID}","isEnabled":true,"type":"User","userConsentDescription":"Allows the app to call the Azure Naming API on your behalf.","userConsentDisplayName":"Access Azure Naming API","value":"${SCOPE_NAME}"}]
EOF
)

OAUTH_SCOPES=$(echo "${OAUTH_SCOPES}" | jq -c '.')

echo "Setting delegated scope '${SCOPE_NAME}'..."
az ad app update --id "${API_APP_ID}" --set api.oauth2PermissionScopes="${OAUTH_SCOPES}"

echo "Ensuring service principal exists..."
az ad sp create --id "${API_APP_ID}" >/dev/null

cat <<INFO

API registration complete.

Tenant ID:        ${TENANT_ID}
Client ID:        ${API_APP_ID}
Object ID:        ${API_OBJECT_ID}
Identifier URI:   api://${API_APP_ID}
Roles:            reader, contributor, admin
Scope:            ${SCOPE_NAME}
Scope ID:         ${SCOPE_ID}

Export these values for local development:
  export AZURE_TENANT_ID="${TENANT_ID}"
  export AZURE_CLIENT_ID="${API_APP_ID}"

Use 'az ad app owner add' and 'az ad app role assignment create' to assign roles to users or groups.
INFO
