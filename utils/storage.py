import os
from datetime import datetime
from typing import Any

from azure.data.tables import TableServiceClient
from azure.core.exceptions import ResourceNotFoundError

# Connection string expected in environment
_CONN_STR = os.environ.get("AzureWebJobsStorage", "")
_service = TableServiceClient.from_connection_string(_CONN_STR)


def get_table_client(table_name: str):
    """Return a TableClient for the given table name."""
    return _service.get_table_client(table_name)


def check_name_exists(region: str, environment: str, name: str) -> bool:
    """Return True if the name entity exists and is marked in use."""
    table = get_table_client("GeneratedNames")
    partition_key = f"{region.lower()}-{environment.lower()}"
    try:
        entity = table.get_entity(partition_key=partition_key, row_key=name)
        return bool(entity.get("InUse", False))
    except ResourceNotFoundError:
        return False


def claim_name(region: str, environment: str, name: str, resource_type: str, claimed_by: str) -> None:
    """Insert or update a claimed name entity in the GeneratedNames table."""
    table = get_table_client("GeneratedNames")
    partition_key = f"{region.lower()}-{environment.lower()}"
    entity = {
        "PartitionKey": partition_key,
        "RowKey": name,
        "InUse": True,
        "ResourceType": resource_type,
        "ClaimedBy": claimed_by,
        "ClaimedAt": datetime.utcnow().isoformat(),
    }
    table.upsert_entity(entity=entity, mode="Merge")
