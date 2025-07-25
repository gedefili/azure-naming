# File: utils/slug_loader.py
# Version: 1.0.0
# Created: 2025-07-24
# Last Modified: 2025-07-24
# Authors: ChatGPT & Geoff DeFilippi
# Summary: Loads and reconciles slug mappings into Azure Table Storage from the Azure naming HCL file.

import logging
from azure.data.tables import TableServiceClient
from azure.core.exceptions import ResourceExistsError
from utils.slug_fetcher import get_all_remote_slugs

TABLE_NAME = "SlugMappings"
PARTITION_KEY = "slug"


def sync_slug_definitions(connection_string: str) -> int:
    """
    Fetches latest slug definitions and updates Table Storage accordingly.

    Parameters:
    - connection_string: Azure Storage connection string

    Returns:
    - Number of new or updated slugs applied
    """
    slugs = get_all_remote_slugs()
    client = TableServiceClient.from_connection_string(conn_str=connection_string)
    table = client.get_table_client(TABLE_NAME)

    updated = 0

    for slug, resource_type in slugs.items():
        entity = {
            "PartitionKey": PARTITION_KEY,
            "RowKey": slug,
            "resourceType": resource_type,
            "source": "azure_defined_specs"
        }
        try:
            table.upsert_entity(mode="merge", entity=entity)
            updated += 1
        except Exception as e:
            logging.warning(f"Failed to upsert slug {slug}: {e}")

    logging.info(f"Slug sync completed. {updated} slugs updated.")
    return updated