"""Synchronise slug definitions into Azure Table Storage."""

from __future__ import annotations

import logging
from typing import Optional

try:
    from azure.core.exceptions import AzureError
    from azure.data.tables import TableServiceClient, UpdateMode
except ImportError:  # pragma: no cover - used during unit tests without Azure SDK
    class AzureError(Exception):
        """Fallback AzureError when the Azure SDK is unavailable."""

    class UpdateMode:  # type: ignore
        MERGE = "MERGE"

        @staticmethod
        def __getattr__(name):  # pragma: no cover - compatibility shim
            return "MERGE"

    TableServiceClient = None  # type: ignore

from adapters.slug_fetcher import get_all_remote_slugs
from adapters.storage import get_table_client

TABLE_NAME = "SlugMappings"
PARTITION_KEY = "slug"


def sync_slug_definitions(connection_string: Optional[str] = None) -> int:
    """Fetch latest slug definitions and update Azure Table Storage."""

    slugs = get_all_remote_slugs()

    if connection_string:
        if TableServiceClient is None:
            raise RuntimeError("azure-data-tables must be installed to use a custom connection string")
        table = TableServiceClient.from_connection_string(conn_str=connection_string).get_table_client(TABLE_NAME)
    else:
        table = get_table_client(TABLE_NAME)

    updated = 0

    for slug, resource_type in slugs.items():
        canonical_name = str(resource_type).lower()
        human_readable = canonical_name.replace("_", " ")
        entity = {
            "PartitionKey": PARTITION_KEY,
            "RowKey": slug,
            "Slug": slug,
            "ResourceType": canonical_name,
            "FullName": human_readable,
            "Source": "azure_defined_specs",
        }
        try:
            table.upsert_entity(mode=UpdateMode.MERGE, entity=entity)
            updated += 1
        except AzureError as exc:  # pragma: no cover - defensive logging
            logging.warning("Failed to upsert slug %s: %s", slug, exc)

    logging.info("Slug sync completed. %s slugs updated.", updated)
    return updated
