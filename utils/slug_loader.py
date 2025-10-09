# File: utils/slug_loader.py
# Version: 1.2.0
# Created: 2025-07-24
# Last Modified: 2025-10-08
# Authors: ChatGPT & Geoff DeFilippi
# Summary: Loads and reconciles slug mappings into Azure Table Storage from the Azure naming HCL file.

import logging
from typing import Optional

try:
    from azure.core.exceptions import AzureError
    from azure.data.tables import UpdateMode
except ImportError:  # pragma: no cover - used during unit tests without Azure SDK
    class AzureError(Exception):
        """Fallback AzureError when the Azure SDK is unavailable."""

    class UpdateMode:  # type: ignore
        MERGE = "MERGE"

from .slug_fetcher import get_all_remote_slugs
from .storage import get_table_client

TABLE_NAME = "SlugMappings"
PARTITION_KEY = "slug"


def sync_slug_definitions(connection_string: Optional[str] = None) -> int:
    """Fetch latest slug definitions and update Azure Table Storage."""

    slugs = get_all_remote_slugs()

    if connection_string:
        from azure.data.tables import TableServiceClient  # Local import to delay dependency loading

        table = TableServiceClient.from_connection_string(conn_str=connection_string).get_table_client(
            TABLE_NAME
        )
    else:
        table = get_table_client(TABLE_NAME)

    updated = 0

    for slug, resource_type in slugs.items():
        entity = {
            "PartitionKey": PARTITION_KEY,
            "RowKey": slug,
            "Slug": slug,
            "ResourceType": resource_type,
            "Source": "azure_defined_specs",
        }
        try:
            table.upsert_entity(mode=UpdateMode.MERGE, entity=entity)
            updated += 1
        except AzureError as exc:
            logging.warning("Failed to upsert slug %s: %s", slug, exc)

    logging.info("Slug sync completed. %s slugs updated.", updated)
    return updated
