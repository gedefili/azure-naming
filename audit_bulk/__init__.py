# File: sanmar_naming/audit_bulk/__init__.py
# Version: 1.2.0
# Last Modified: 2025-07-24
# Authors: ChatGPT & Geoff DeFilippi
# Summary: Audits claimed/released Azure names. Enforces RBAC via Entra ID roles and group membership.

import logging
import json
import azure.functions as func
from azure.data.tables import TableServiceClient
import os
from utils.auth import require_role, is_authorized, AuthError

AZURE_STORAGE_CONN_STRING = os.environ["AzureWebJobsStorage"]
NAMES_TABLE_NAME = "GeneratedNames"
_table_service = TableServiceClient.from_connection_string(AZURE_STORAGE_CONN_STRING)
_names_table = _table_service.get_table_client(NAMES_TABLE_NAME)

def main(req: func.HttpRequest) -> func.HttpResponse:
    """List audit information for a specific name.

    Enforces role-based access control before returning claim and
    release metadata stored in Table Storage.
    """
    logging.info("[audit_name] Starting RBAC-secured audit check.")

    try:
        # 'user' role grants access to audit names that the user claimed or released.
        # Elevated roles like 'manager' and 'admin' bypass this restriction.
        user_id, user_roles = require_role(req.headers, min_role="user")
    except AuthError as e:
        return func.HttpResponse(str(e), status_code=e.status)

    region = req.params.get("region")
    environment = req.params.get("environment")
    name = req.params.get("name")

    if not region or not environment or not name:
        return func.HttpResponse(
            "Missing query parameters: region, environment, name.", status_code=400)

    partition_key = f"{region.lower()}-{environment.lower()}"
    try:
        entity = _names_table.get_entity(partition_key=partition_key, row_key=name)

        # RBAC check: verify caller has access
        if not is_authorized(user_roles, user_id, entity.get("ClaimedBy"), entity.get("ReleasedBy")):
            logging.warning(f"Access denied: user {user_id} lacks permission for name '{name}' in {partition_key}.")
            return func.HttpResponse("Forbidden: not authorized to view this name.", status_code=403)

        audit_info = {
            "name": entity["RowKey"],
            "resource_type": entity.get("ResourceType", "unknown"),
            "in_use": entity.get("InUse", False),
            "claimed_by": entity.get("ClaimedBy", None),
            "claimed_at": entity.get("ClaimedAt", None),
            "released_by": entity.get("ReleasedBy", None),
            "released_at": entity.get("ReleasedAt", None),
            "release_reason": entity.get("ReleaseReason", None),
            "previous_use": entity.get("PreviousUse", None)
        }
        return func.HttpResponse(json.dumps(audit_info), status_code=200, mimetype="application/json")

    except Exception:
        logging.exception("Failed to retrieve or authorize audit data.")
        return func.HttpResponse(f"Audit entry not found or access denied.", status_code=404)
