# File: sanmar_naming/release_name/__init__.py
# Version: 1.1.0
# Last Modified: 2025-07-24
# Authors: ChatGPT & Geoff DeFilippi
# Summary: Releases a name back into the pool with RBAC and auditing support.

import logging
import azure.functions as func
from azure.data.tables import TableServiceClient
import json
import os
from datetime import datetime
from utils.auth import require_role, AuthError
from utils.audit_logs import write_audit_log

AZURE_STORAGE_CONN_STRING = os.environ["AzureWebJobsStorage"]
NAMES_TABLE_NAME = "GeneratedNames"
_table_service = TableServiceClient.from_connection_string(AZURE_STORAGE_CONN_STRING)
_names_table = _table_service.get_table_client(NAMES_TABLE_NAME)

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("[release_name] Processing release request with RBAC.")

    try:
        user_id, user_roles = require_role(req.headers, min_role="user")
    except AuthError as e:
        return func.HttpResponse(str(e), status_code=e.status)

    try:
        data = req.get_json()
        region = data.get("region")
        environment = data.get("environment")
        name = data.get("name")
        reason = data.get("reason", "not specified")

        if not region or not environment or not name:
            return func.HttpResponse("Missing required fields.", status_code=400)

        partition_key = f"{region.lower()}-{environment.lower()}"
        entity = _names_table.get_entity(partition_key=partition_key, row_key=name)

        entity["InUse"] = False
        entity["ReleasedBy"] = user_id
        entity["ReleasedAt"] = datetime.utcnow().isoformat()
        entity["ReleaseReason"] = reason
        entity["PreviousUse"] = entity.get("ClaimedBy")

        _names_table.update_entity(entity=entity, mode="Replace")
        write_audit_log(name, user_id, "released", reason)

        return func.HttpResponse("Name released successfully.", status_code=200)

    except Exception as e:
        logging.exception("[release_name] Failed to release name.")
        return func.HttpResponse("Error releasing name.", status_code=500)
