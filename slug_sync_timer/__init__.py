# File: sanmar_naming/slug_sync_timer/__init__.py
# Version: 1.1.0
# Last Modified: 2025-07-24
# Authors: ChatGPT & Geoff DeFilippi
# Summary: Timer-triggered slug synchronization from GitHub to Azure Table Storage.

import logging
from datetime import datetime

try:
    from azure.core.exceptions import AzureError
except ImportError:  # pragma: no cover - allows tests without Azure SDK
    class AzureError(Exception):
        """Fallback AzureError when Azure SDK is unavailable."""

from utils.slug_fetcher import SlugSourceError, get_all_remote_slugs
from utils.storage import get_table_client

SLUG_TABLE_NAME = "SlugMappings"
PARTITION_KEY = "slug"


def main(mytimer) -> None:
    """Timer triggered function to sync slug mappings weekly."""

    logging.info("[slug_sync_timer] Scheduled slug sync triggered.")

    try:
        remote_slugs = get_all_remote_slugs()
        if not remote_slugs:
            logging.warning("[slug_sync_timer] Upstream returned no slug data; aborting sync.")
            return

        slug_table = get_table_client(SLUG_TABLE_NAME)
        updated_count = 0

        for slug, full_name in remote_slugs.items():
            partition_key = PARTITION_KEY
            row_key = slug

            try:
                entity = slug_table.get_entity(partition_key=partition_key, row_key=row_key)
                if entity.get("FullName") != full_name:
                    entity["FullName"] = full_name
                    entity["UpdatedAt"] = datetime.utcnow().isoformat()
                    slug_table.update_entity(entity=entity, mode="Replace")
                    updated_count += 1
            except Exception:
                new_entity = {
                    "PartitionKey": partition_key,
                    "RowKey": row_key,
                    "Slug": slug,
                    "FullName": full_name,
                    "UpdatedAt": datetime.utcnow().isoformat(),
                }
                slug_table.upsert_entity(entity=new_entity, mode="Replace")
                updated_count += 1

        logging.info("[slug_sync_timer] Sync complete. %s slugs updated/added.", updated_count)

    except SlugSourceError as exc:
        logging.warning("[slug_sync_timer] Upstream slug source unavailable: %s", exc)
    except (AzureError, RuntimeError):
        logging.exception("[slug_sync_timer] Storage unavailable during sync.")
    except Exception:
        logging.exception("[slug_sync_timer] Sync failed.")
