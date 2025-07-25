# File: sanmar_naming/slug_sync/__init__.py
# Version: 1.1.0
# Last Modified: 2025-07-24
# Authors: ChatGPT & Geoff DeFilippi
# Summary: Synchronizes slug mappings from GitHub to Azure Table Storage. Supports RBAC.

import logging
import azure.functions as func
from azure.data.tables import TableServiceClient, UpdateMode
import os
from datetime import datetime
from utils.slug_fetcher import get_all_remote_slugs
from utils.auth import require_role, AuthError

AZURE_STORAGE_CONN_STRING = os.environ["AzureWebJobsStorage"]
SLUG_TABLE_NAME = "SlugMappings"
_table_service = TableServiceClient.from_connection_string(AZURE_STORAGE_CONN_STRING)
_slug_table = _table_service.get_table_client(SLUG_TABLE_NAME)

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("[slug_sync] Starting slug synchronization from GitHub source.")

    # Enforce RBAC (any authenticated user or higher)
    try:
        _, _ = require_role(req.headers, min_role="user")
    except AuthError as e:
        return func.HttpResponse(str(e), status_code=e.status)

    try:
        remote_slugs = get_all_remote_slugs()
        updated_count = 0

        for slug, full_name in remote_slugs.items():
            partition_key = "slug"
            row_key = slug

            try:
                entity = _slug_table.get_entity(partition_key=partition_key, row_key=row_key)
                if entity.get("FullName") != full_name:
                    entity["FullName"] = full_name
                    entity["UpdatedAt"] = datetime.utcnow().isoformat()
                    _slug_table.update_entity(entity=entity, mode=UpdateMode.REPLACE)
                    updated_count += 1
            except:
                # New slug — insert it
                new_entity = {
                    "PartitionKey": partition_key,
                    "RowKey": row_key,
                    "Slug": slug,
                    "FullName": full_name,
                    "UpdatedAt": datetime.utcnow().isoformat()
                }
                _slug_table.create_entity(entity=new_entity)
                updated_count += 1

        logging.info(f"[slug_sync] Slug sync complete. Total updated/added: {updated_count}")
        return func.HttpResponse(f"Slug sync complete. {updated_count} entries updated/created.", status_code=200)

    except Exception as e:
        logging.exception("[slug_sync] Slug sync failed.")
        return func.HttpResponse("Slug sync failed.", status_code=500)
