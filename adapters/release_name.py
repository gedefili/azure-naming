"""Adapter for marking claimed names as released."""

from __future__ import annotations

from datetime import datetime, timezone

try:
    from azure.core.exceptions import ResourceNotFoundError
except ImportError:  # pragma: no cover - fallback when Azure SDK unavailable
    class ResourceNotFoundError(Exception):
        """Placeholder exception used when the Azure SDK is unavailable."""

from adapters.storage import get_table_client

NAME_TABLE = "ClaimedNames"


def release_name(
    region: str,
    environment: str,
    name: str,
    released_by: str,
    reason: str = "not specified",
) -> bool:
    """Mark a claimed name as released in Azure Table Storage."""

    table = get_table_client(NAME_TABLE)
    partition_key = f"{region.lower()}-{environment.lower()}"
    row_key = name

    try:
        entity = table.get_entity(partition_key=partition_key, row_key=row_key)
    except ResourceNotFoundError:
        return False

    try:
        state_version = int(entity.get("StateVersion", 0)) + 1
    except (TypeError, ValueError):
        state_version = 1

    released_at = datetime.now(tz=timezone.utc).isoformat()
    entity["InUse"] = False
    entity["ClaimState"] = "released"
    entity["StateChangedBy"] = released_by
    entity["StateChangedAt"] = released_at
    entity["StateVersion"] = state_version
    entity["LastLifecycleAction"] = "released"
    entity["ReleasedBy"] = released_by
    entity["ReleasedAt"] = released_at
    entity["ReleaseReason"] = reason
    entity.pop("OrphanedBy", None)
    entity.pop("OrphanedAt", None)
    entity.pop("OrphanReason", None)
    table.update_entity(entity, mode="MERGE")
    return True
