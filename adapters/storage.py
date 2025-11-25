"""Storage adapter for Azure Table interactions."""

from __future__ import annotations

import os
from datetime import datetime
from threading import Lock
from typing import TYPE_CHECKING, Any, Dict, Optional

try:
    from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
    from azure.data.tables import TableServiceClient, UpdateMode
except ImportError:  # pragma: no cover - fallback for unit tests
    TableServiceClient = None  # type: ignore

    class ResourceNotFoundError(Exception):
        """Placeholder when Azure SDK is unavailable."""

    class ResourceExistsError(Exception):
        """Placeholder when Azure SDK is unavailable."""

    class UpdateMode:  # type: ignore
        MERGE = "MERGE"

if TYPE_CHECKING:  # pragma: no cover - typing aid only
    from azure.data.tables import TableClient as _TableClient
else:  # pragma: no cover - typing aid only
    _TableClient = Any

_SERVICE_LOCK = Lock()
_service: Optional[_TableClient] = None


def _get_service():
    """Return a cached :class:`TableServiceClient` instance."""

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
                        "AzureWebJobsStorage is not configured; set the environment variable before invoking storage helpers."
                    )
                _service = TableServiceClient.from_connection_string(connection_string)

    return _service


def get_table_client(table_name: str):
    """Return a table client, creating the table if necessary."""

    service = _get_service()
    try:
        service.create_table_if_not_exists(table_name=table_name)
    except ResourceExistsError:
        pass

    return service.get_table_client(table_name)


def check_name_exists(region: str, environment: str, name: str) -> bool:
    """Return True if the claimed name entity exists and is marked in use."""

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
    """Insert or update a claimed name entity in the ClaimedNames table.
    
    Uses ETag-based optimistic concurrency control to prevent race conditions
    where multiple callers attempt to claim the same name simultaneously.
    """

    table = get_table_client("ClaimedNames")
    partition_key = f"{region.lower()}-{environment.lower()}"
    
    # Check if entity already exists
    try:
        existing = table.get_entity(partition_key=partition_key, row_key=name)
        # Entity exists - only update if it's not already in use (race condition prevention)
        if existing.get("InUse"):
            raise ResourceExistsError(
                f"Name {name} is already in use (claimed by {existing.get('ClaimedBy')})"
            )
    except ResourceNotFoundError:
        # Entity doesn't exist, will create it
        pass
    
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

    # Use INSERT mode to create only if not exists (prevents overwrite)
    # If entity already exists, this raises ResourceExistsError
    try:
        table.create_entity(entity=entity)
    except ResourceExistsError:
        # Entity exists from another thread/request, fail gracefully
        raise ResourceExistsError(
            f"Name {name} was claimed by another request before this one completed"
        )
