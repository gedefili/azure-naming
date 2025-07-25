# File: utils/audit_logs.py
# Version: 1.0.0
# Created: 2025-07-24
# Last Modified: 2025-07-24
# Authors: ChatGPT & Geoff DeFilippi
# Summary: Helper for writing claim/release audit entries to Azure Table Storage.

from azure.data.tables import TableServiceClient
from uuid import uuid4
from datetime import datetime
import os
import logging

AZURE_STORAGE_CONN_STRING = os.environ.get("AzureWebJobsStorage")
AUDIT_TABLE_NAME = "AuditLogs"

_table_service = None
_audit_table = None

if AZURE_STORAGE_CONN_STRING:
    try:
        _table_service = TableServiceClient.from_connection_string(AZURE_STORAGE_CONN_STRING)
        _audit_table = _table_service.get_table_client(AUDIT_TABLE_NAME)
    except Exception:
        logging.exception("[audit_logs] Failed to connect to AuditLogs table")
else:
    logging.error("[audit_logs] AzureWebJobsStorage not set")


def write_audit_log(name: str, user: str, action: str, note: str = "") -> None:
    """Write an entry to the AuditLogs table.

    Parameters
    ----------
    name : str
        The claimed resource name (PartitionKey)
    user : str
        The user performing the action
    action : str
        Either "claimed" or "released"
    note : str, optional
        Additional context message
    """
    if _audit_table is None:
        logging.error("[audit_logs] Audit table client not initialized")
        return

    entity = {
        "PartitionKey": name,
        "RowKey": str(uuid4()),
        "User": user,
        "Action": action,
        "Timestamp": datetime.utcnow().isoformat(),
        "Note": note,
    }

    try:
        _audit_table.create_entity(entity=entity)
    except Exception:
        logging.exception("[audit_logs] Failed to record audit entry")
