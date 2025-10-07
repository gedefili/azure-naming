# File: utils/audit_logs.py
# Version: 1.0.0
# Created: 2025-07-24
# Last Modified: 2025-07-24
# Authors: ChatGPT & Geoff DeFilippi
# Summary: Helper for writing claim/release audit entries to Azure Table Storage.

import logging
from datetime import datetime
from typing import Any, Dict, Optional

try:
    from azure.core.exceptions import AzureError
except ImportError:  # pragma: no cover - allow tests without Azure SDK
    class AzureError(Exception):
        """Fallback exception when Azure SDK is unavailable."""

from uuid import uuid4

from .storage import get_table_client

AUDIT_TABLE_NAME = "AuditLogs"


def write_audit_log(
    name: str,
    user: str,
    action: str,
    note: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
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
    try:
        audit_table = get_table_client(AUDIT_TABLE_NAME)
    except RuntimeError:
        logging.error("[audit_logs] Audit table client not initialized")
        return

    entity = {
        "PartitionKey": name,
        "RowKey": str(uuid4()),
        "User": str(user).lower(),
        "Action": str(action).lower(),
        "Note": note,
        "EventTime": datetime.utcnow(),
    }

    if metadata:
        entity.update(metadata)

    try:
        audit_table.create_entity(entity=entity)
    except AzureError:
        logging.exception("[audit_logs] Failed to record audit entry")
