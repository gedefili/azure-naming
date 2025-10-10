"""Adapter for marking claimed names as released."""

from __future__ import annotations

from datetime import datetime

try:
    from azure.core.exceptions import ResourceNotFoundError
except ImportError:  # pragma: no cover - fallback when Azure SDK unavailable
    class ResourceNotFoundError(Exception):
        """Placeholder exception used when the Azure SDK is unavailable."""

from adapters.storage import get_table_client

NAME_TABLE = "ClaimedNames"


def release_name(region: str, environment: str, name: str, released_by: str) -> bool:
    """Mark a claimed name as released in Azure Table Storage."""

    table = get_table_client(NAME_TABLE)
    partition_key = f"{region}_{environment}"
    row_key = name

    try:
        entity = table.get_entity(partition_key=partition_key, row_key=row_key)
    except ResourceNotFoundError:
        return False

    entity["InUse"] = False
    entity["ReleasedBy"] = released_by
    entity["ReleasedOn"] = datetime.utcnow().isoformat()
    table.update_entity(entity, mode="MERGE")
    return True
