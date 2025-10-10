"""HTTP and timer routes for slug synchronization."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Tuple

import azure.functions as func
from azure_functions_openapi.decorator import openapi as openapi_doc

from app import app
from app.constants import SLUG_PARTITION_KEY, SLUG_TABLE_NAME
from app.models import MessageResponse
from app.responses import json_message
from app.dependencies import (
    AuthError,
    AzureError,
    SlugSourceError,
    UpdateMode,
    get_all_remote_slugs,
    get_table_client,
    require_role,
)


def _perform_slug_sync() -> Tuple[int, str]:
    remote_slugs = get_all_remote_slugs()
    if not remote_slugs:
        return 502, "Slug sync failed: upstream returned no data."

    slug_table = get_table_client(SLUG_TABLE_NAME)
    updated_count = 0

    for slug, full_name in remote_slugs.items():
        partition_key = SLUG_PARTITION_KEY
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
            slug_table.upsert_entity(entity=new_entity, mode=UpdateMode.MERGE)
            updated_count += 1

    message = f"Slug sync complete. {updated_count} entries updated/created."
    logging.info("[slug_sync] %s", message)
    return 200, message


@app.function_name(name="slug_sync")
@app.route(route="slug_sync", methods=[func.HttpMethod.POST])
@openapi_doc(
    summary="Synchronize slug mappings",
    description="Triggers a refresh of slug metadata from the upstream GitHub source.",
    tags=["Maintenance"],
    response_model=MessageResponse,
    operation_id="slugSync",
    route="/slug_sync",
    method="post",
)
def slug_sync(req: func.HttpRequest) -> func.HttpResponse:
    """Synchronize slug mappings via HTTP trigger."""

    logging.info("[slug_sync] Starting slug synchronization from GitHub source.")

    try:
        require_role(req.headers, min_role="admin")
    except AuthError as exc:
        return func.HttpResponse(str(exc), status_code=exc.status)

    try:
        status_code, message = _perform_slug_sync()
        return json_message(message, status_code=status_code)
    except SlugSourceError as exc:
        logging.warning("[slug_sync] Upstream slug source unavailable: %s", exc)
        return json_message("Slug sync failed: upstream source unavailable.", status_code=503)
    except (AzureError, RuntimeError):
        logging.exception("[slug_sync] Failed to connect to storage.")
        return json_message("Slug sync failed: storage unavailable.", status_code=500)
    except Exception:
        logging.exception("[slug_sync] Slug sync failed.")
        return json_message("Slug sync failed.", status_code=500)


@app.function_name(name="slug_sync_timer")
@app.schedule(schedule="0 0 4 * * Sun", arg_name="mytimer", run_on_startup=False, use_monitor=True)
def slug_sync_timer(mytimer: func.TimerRequest) -> None:  # pragma: no cover - timer integration
    """Timer triggered slug synchronization."""

    logging.info("[slug_sync_timer] Scheduled slug sync triggered.")

    try:
        _perform_slug_sync()
    except SlugSourceError as exc:
        logging.warning("[slug_sync_timer] Upstream slug source unavailable: %s", exc)
    except (AzureError, RuntimeError):
        logging.exception("[slug_sync_timer] Storage unavailable during sync.")
    except Exception:
        logging.exception("[slug_sync_timer] Sync failed.")
