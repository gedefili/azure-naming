# File: utils/storage.py
# Version: 1.0.0
# Last Modified: 2025-07-24
# Authors: ChatGPT & Geoff DeFilippi
# Summary: Helpers for interacting with Azure Table Storage for name claims.

import os
from datetime import datetime
from threading import Lock
from typing import Any, Dict, Optional

try:
    from azure.data.tables import TableServiceClient, UpdateMode
    from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
except ImportError:  # pragma: no cover - fallback for local testing without Azure SDK
    TableServiceClient = None  # type: ignore

    class ResourceNotFoundError(Exception):
        """Placeholder exception used when the Azure SDK is unavailable."""

    class ResourceExistsError(Exception):
        """Placeholder exception used when the Azure SDK is unavailable."""

    class UpdateMode:  # type: ignore
        MERGE = "MERGE"

_SERVICE_LOCK = Lock()
_service: Optional[TableServiceClient] = None


def _get_service() -> TableServiceClient:
    """Return a cached TableServiceClient instance, creating it on demand."""

    global _service

    if _service is None:
        with _SERVICE_LOCK:
            if _service is None:
                if TableServiceClient is None:
                    raise RuntimeError(
                        "azure-data-tables is not installed; install dependencies to access storage"
                    )

                connection_string = os.environ.get("AzureWebJobsStorage")
                if not connection_string:
                    raise RuntimeError(
                        "AzureWebJobsStorage is not configured; set the environment variable "
                        "before invoking storage helpers."
                    )
                _service = TableServiceClient.from_connection_string(connection_string)

    return _service


def get_table_client(table_name: str):
    """Return a TableClient for the given table name, creating it if missing."""

    service = _get_service()
    try:
        service.create_table_if_not_exists(table_name=table_name)
    except ResourceExistsError:
        pass

    return service.get_table_client(table_name)


def check_name_exists(region: str, environment: str, name: str) -> bool:
    """Return True if the name entity exists and is marked in use."""
    table = get_table_client("ClaimedNames")
    partition_key = f"{region.lower()}-{environment.lower()}"
    try:
        entity = table.get_entity(partition_key=partition_key, row_key=name)
        return bool(entity.get("InUse", False))
    except ResourceNotFoundError:
        return False


def claim_name(
    region: str,
    environment: str,
    name: str,
    resource_type: str,
    claimed_by: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Insert or update a claimed name entity in the ClaimedNames table."""

    table = get_table_client("ClaimedNames")
    partition_key = f"{region.lower()}-{environment.lower()}"
    entity = {
        "PartitionKey": partition_key,
        "RowKey": name,
        "InUse": True,
        "ResourceType": resource_type,
        "ClaimedBy": claimed_by,
        "ClaimedAt": datetime.utcnow().isoformat(),
    }

    if metadata:
        entity.update(metadata)

    table.upsert_entity(entity=entity, mode=UpdateMode.MERGE)
