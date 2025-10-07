# File: sanmar_naming/audit_name/__init__.py
# Version: 1.2.0
# Last Modified: 2025-07-24
# Authors: ChatGPT & Geoff DeFilippi
# Summary: Audits claimed/released Azure names with RBAC.

import json
import logging

import azure.functions as func
from azure.core.exceptions import ResourceNotFoundError

from utils.auth import AuthError, is_authorized, require_role
from utils.storage import get_table_client

NAMES_TABLE_NAME = "ClaimedNames"


def main(req: func.HttpRequest) -> func.HttpResponse:
    """Retrieve audit information for a single claimed name."""

    logging.info("[audit_name] Starting RBAC-secured audit check.")

    try:
        user_id, user_roles = require_role(req.headers, min_role="user")
    except AuthError as exc:
        return func.HttpResponse(str(exc), status_code=exc.status)

    region = (req.params.get("region") or "").lower()
    environment = (req.params.get("environment") or "").lower()
    name = (req.params.get("name") or "").lower()

    if not region or not environment or not name:
        return func.HttpResponse(
            "Missing query parameters: region, environment, name.", status_code=400
        )

    partition_key = f"{region}-{environment}"

    try:
        table = get_table_client(NAMES_TABLE_NAME)
        entity = table.get_entity(partition_key=partition_key, row_key=name)
    except ResourceNotFoundError:
        return func.HttpResponse("Audit entry not found.", status_code=404)
    except Exception:
        logging.exception("[audit_name] Failed to retrieve audit entity.")
        return func.HttpResponse("Error retrieving audit entry.", status_code=500)

    if not is_authorized(user_roles, user_id, entity.get("ClaimedBy"), entity.get("ReleasedBy")):
        return func.HttpResponse("Forbidden: not authorized to view this name.", status_code=403)

    audit_info = {
        "name": entity["RowKey"],
        "resource_type": entity.get("ResourceType", "unknown"),
        "in_use": entity.get("InUse", False),
        "claimed_by": entity.get("ClaimedBy"),
        "claimed_at": entity.get("ClaimedAt"),
        "released_by": entity.get("ReleasedBy"),
        "released_at": entity.get("ReleasedAt"),
        "release_reason": entity.get("ReleaseReason"),
        "region": region,
        "environment": environment,
        "slug": entity.get("Slug"),
        "project": entity.get("Project"),
        "purpose": entity.get("Purpose"),
        "system": entity.get("System"),
        "index": entity.get("Index"),
    }

    return func.HttpResponse(json.dumps(audit_info), status_code=200, mimetype="application/json")
