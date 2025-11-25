"""Adapter responsible for persisting audit log entries."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import uuid4

try:
    from azure.core.exceptions import AzureError
except ImportError:  # pragma: no cover - allow tests without Azure SDK
    class AzureError(Exception):
        """Fallback exception when Azure SDK is unavailable."""

from adapters.storage import get_table_client

AUDIT_TABLE_NAME = "AuditLogs"


def write_audit_log(
    name: str,
    user: str,
    action: str,
    note: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Persist an audit entry describing a claim/release event."""

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
