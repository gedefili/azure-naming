# File: utils/release_name.py
# Version: 1.0.0
# Last Modified: 2025-07-24
# Authors: ChatGPT & Geoff DeFilippi
# Summary: Provides logic to mark a claimed Azure resource name as released in Azure Table Storage.

from utils.storage import get_table_client
from datetime import datetime
from azure.core.exceptions import ResourceNotFoundError

NAME_TABLE = "AuditLogs"

def release_name(region: str, environment: str, name: str, released_by: str) -> bool:
    """
    Marks a claimed name as released in Azure Table Storage.
    If the name does not exist, returns False.
    Args:
        region (str): Azure region
        environment (str): Environment (e.g., dev, prod)
        name (str): Name to release
        released_by (str): Username performing the release
    Returns:
        bool: True if successful, False if not found
    """
    table = get_table_client(NAME_TABLE)
    partition_key = f"{region}_{environment}"
    row_key = name

    try:
        entity = table.get_entity(partition_key=partition_key, row_key=row_key)
        entity["InUse"] = False
        entity["ReleasedBy"] = released_by
        entity["ReleasedOn"] = datetime.utcnow().isoformat()
        table.update_entity(entity, mode="MERGE")
        return True
    except ResourceNotFoundError:
        return False
