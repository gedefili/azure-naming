# File: sanmar_naming/slug_sync/__init__.py
# Version: 1.2.0
# Last Modified: 2025-07-24
# Authors: ChatGPT & Geoff DeFilippi
# Summary: Synchronizes slug mappings from GitHub to Azure Table Storage. Supports RBAC.

import logging
from datetime import datetime

import azure.functions as func

try:
    from azure.core.exceptions import AzureError
except ImportError:  # pragma: no cover - allows lint/test without Azure SDK
    class AzureError(Exception):
        """Fallback AzureError when Azure SDK is missing."""

from utils.auth import AuthError, require_role
from utils.slug_fetcher import SlugSourceError, get_all_remote_slugs
from utils.storage import get_table_client

SLUG_TABLE_NAME = "SlugMappings"
PARTITION_KEY = "slug"


def main(req: func.HttpRequest) -> func.HttpResponse:
    """Synchronize slug mappings via an authenticated HTTP call."""

    logging.info("[slug_sync] Starting slug synchronization from GitHub source.")

    try:
        require_role(req.headers, min_role="user")
    except AuthError as exc:
        return func.HttpResponse(str(exc), status_code=exc.status)

    try:
        remote_slugs = get_all_remote_slugs()
        if not remote_slugs:
            return func.HttpResponse(
                "Slug sync failed: upstream returned no data.", status_code=502
            )

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

        logging.info("[slug_sync] Slug sync complete. Total updated/added: %s", updated_count)
        return func.HttpResponse(
            f"Slug sync complete. {updated_count} entries updated/created.", status_code=200
        )

    except SlugSourceError as exc:
        logging.warning("[slug_sync] Upstream slug source unavailable: %s", exc)
        return func.HttpResponse("Slug sync failed: upstream source unavailable.", status_code=503)
    except (AzureError, RuntimeError):
        logging.exception("[slug_sync] Failed to connect to storage.")
        return func.HttpResponse("Slug sync failed: storage unavailable.", status_code=500)
    except Exception:
        logging.exception("[slug_sync] Slug sync failed.")
        return func.HttpResponse("Slug sync failed.", status_code=500)
