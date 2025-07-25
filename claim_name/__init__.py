# File: sanmar_naming/claim_name/__init__.py
# Version: 1.1.0
# Last Modified: 2025-07-24
# Authors: ChatGPT & Geoff DeFilippi
# Summary: Claims a unique Azure name, updates audit, and enforces Entra ID-based RBAC.

import logging
import azure.functions as func
from azure.data.tables import TableServiceClient
import json
import os
from datetime import datetime
from utils.auth import require_role, AuthError
from utils.audit_logs import write_audit_log

AZURE_STORAGE_CONN_STRING = os.environ["AzureWebJobsStorage"]
NAMES_TABLE_NAME = "ClaimedNames"
_table_service = TableServiceClient.from_connection_string(AZURE_STORAGE_CONN_STRING)
_names_table = _table_service.get_table_client(NAMES_TABLE_NAME)

def main(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint to claim a name.

    Validates the caller's role using Entra ID claims and then
    records the name as claimed in Table Storage. An audit entry is
    created so administrators can track who claimed the name and when.
    """
    logging.info("[claim_name] Processing claim request with RBAC.")

    try:
        user_id, user_roles = require_role(req.headers, min_role="user")
    except AuthError as e:
        return func.HttpResponse(str(e), status_code=e.status)

    try:
        data = req.get_json()
        region = data.get("region")
        environment = data.get("environment")
        name = data.get("name")
        resource_type = data.get("resource_type", "unknown")

        if not region or not environment or not name:
            return func.HttpResponse("Missing required fields.", status_code=400)

        partition_key = f"{region.lower()}-{environment.lower()}"

        # Check if the name already exists and is in use
        try:
            existing = _names_table.get_entity(partition_key=partition_key, row_key=name)
            if existing.get("InUse", False):
                return func.HttpResponse("Name already in use.", status_code=409)
        except:
            existing = None

        entity = {
            "PartitionKey": partition_key,
            "RowKey": name,
            "InUse": True,
            "ClaimedBy": user_id,
            "ClaimedAt": datetime.utcnow().isoformat(),
            "ResourceType": resource_type,
        }

        _names_table.upsert_entity(mode="Merge", entity=entity)
        write_audit_log(name, user_id, "claimed", f"{region}-{environment}")

        return func.HttpResponse("Name claimed successfully.", status_code=200)

    except Exception as e:
        logging.exception("[claim_name] Failed to claim name.")
        return func.HttpResponse("Error claiming name.", status_code=500)
