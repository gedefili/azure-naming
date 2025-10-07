# File: sanmar_naming/release_name/__init__.py
# Version: 1.2.0
# Last Modified: 2025-07-24
# Authors: ChatGPT & Geoff DeFilippi
# Summary: Releases a name back into the pool with RBAC and auditing support.

import json
import logging
from datetime import datetime

import azure.functions as func

from utils.auth import AuthError, is_authorized, require_role
from utils.audit_logs import write_audit_log
from utils.storage import get_table_client

NAMES_TABLE_NAME = "ClaimedNames"


def main(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint to release a previously claimed name."""

    logging.info("[release_name] Processing release request with RBAC.")

    try:
        user_id, user_roles = require_role(req.headers, min_role="user")
    except AuthError as exc:
        return func.HttpResponse(str(exc), status_code=exc.status)

    try:
        data = req.get_json()
    except ValueError:
        return func.HttpResponse("Invalid JSON payload.", status_code=400)

    region = (data.get("region") or "").lower()
    environment = (data.get("environment") or "").lower()
    name = (data.get("name") or "").lower()
    reason = data.get("reason", "not specified")

    if not region or not environment or not name:
        return func.HttpResponse("Missing required fields.", status_code=400)

    partition_key = f"{region}-{environment}"

    try:
        names_table = get_table_client(NAMES_TABLE_NAME)
        entity = names_table.get_entity(partition_key=partition_key, row_key=name)
    except Exception:
        logging.exception("[release_name] Name not found during release.")
        return func.HttpResponse("Name not found.", status_code=404)

    if not is_authorized(user_roles, user_id, entity.get("ClaimedBy"), entity.get("ReleasedBy")):
        return func.HttpResponse("Forbidden: not authorized to release this name.", status_code=403)

    entity["InUse"] = False
    entity["ReleasedBy"] = user_id
    entity["ReleasedAt"] = datetime.utcnow().isoformat()
    entity["ReleaseReason"] = reason

    try:
        names_table.update_entity(entity=entity, mode="Replace")
    except Exception:
        logging.exception("[release_name] Failed to update storage during release.")
        return func.HttpResponse("Error releasing name.", status_code=500)

    metadata = {
        "Region": region,
        "Environment": environment,
        "ResourceType": entity.get("ResourceType"),
        "Slug": entity.get("Slug"),
        "Project": entity.get("Project"),
        "Purpose": entity.get("Purpose"),
        "System": entity.get("System"),
        "Index": entity.get("Index"),
    }
    metadata = {k: v for k, v in metadata.items() if v}

    write_audit_log(name, user_id, "released", reason, metadata=metadata)

    return func.HttpResponse(json.dumps({"message": "Name released successfully."}), status_code=200)
