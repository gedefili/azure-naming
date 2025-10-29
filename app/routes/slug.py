"""HTTP and timer routes for slug synchronization."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, Optional, Tuple

import azure.functions as func
from azure_functions_openapi.decorator import openapi as openapi_doc

from app import app
from app.constants import SLUG_PARTITION_KEY, SLUG_TABLE_NAME
from app.models import MessageResponse, SlugLookupResponse
from app.responses import json_message, json_payload
from app.dependencies import (
    AuthError,
    AzureError,
    SlugSourceError,
    UpdateMode,
    get_all_remote_slugs,
    get_table_client,
    ResourceNotFoundError,
    require_role,
)
from core.slug_service import get_slug


def _resolve_slug_payload(resource_type: str) -> Dict[str, str]:
    cleaned = resource_type.strip()
    if not cleaned:
        raise ValueError("resource_type cannot be empty")
    slug_value = get_slug(cleaned)
    resource_metadata: Dict[str, Optional[str]] = {}
    resolved_resource_type = cleaned

    try:
        table = get_table_client(SLUG_TABLE_NAME)
        entity: Optional[Dict[str, object]] = None

        try:
            entity = table.get_entity(partition_key=SLUG_PARTITION_KEY, row_key=slug_value)
        except ResourceNotFoundError:
            escaped_resource = cleaned.lower().replace("'", "''")
            filter_query = f"ResourceType eq '{escaped_resource}'"
            entities = list(table.query_entities(query_filter=filter_query))
            entity = entities[0] if entities else None

        if entity:
            resolved_resource_type = str(entity.get("ResourceType") or resolved_resource_type)
            # Include all non-personal metadata fields present on the entity.
            for key, val in entity.items():
                if key in {"PartitionKey", "RowKey"}:
                    continue
                # Avoid returning anything that looks like a person identifier
                if isinstance(key, str) and key.lower() in {"claimedby", "releasedby", "user", "email", "upn"}:
                    continue
                # Normalize keys to camelCase in the response
                normalized_key = key[0].lower() + key[1:] if key else key
                resource_metadata[normalized_key] = val
    except Exception:
        logging.exception("[slug_lookup] Failed to hydrate slug metadata.")

    payload: Dict[str, str] = {
        "resourceType": resolved_resource_type.strip().lower(),
        "slug": slug_value,
    }

    for key, value in resource_metadata.items():
        if value:
            payload[key] = str(value)

    return payload


@app.function_name(name="get_slug_mapping")
@app.route(route="slug", methods=[func.HttpMethod.GET], auth_level=func.AuthLevel.ANONYMOUS)
@openapi_doc(
    summary="Resolve a slug for a resource type",
    description="Returns the short slug used when generating names for the requested resource type.",
    tags=["Slugs"],
    parameters=[
        {
            "name": "resource_type",
            "in": "query",
            "required": True,
            "schema": {"type": "string"},
            "description": "Canonical resource type identifier (for example, storage_account).",
        }
    ],
    response_model=SlugLookupResponse,
    operation_id="getSlug",
    route="/slug",
    method="get",
)
def slug_lookup(req: func.HttpRequest) -> func.HttpResponse:
    """Resolve the slug for a given resource type."""

    return _handle_slug_lookup(req)


def _handle_slug_lookup(req: func.HttpRequest) -> func.HttpResponse:
    """Core implementation shared with tests for slug lookup."""

    logging.info("[slug_lookup] Resolving slug for resource type query.")

    try:
        require_role(req.headers, min_role="reader")
    except AuthError as exc:
        return func.HttpResponse(str(exc), status_code=exc.status)

    resource_type = (req.params.get("resource_type") or req.params.get("resourceType") or "").strip()
    if not resource_type:
        return func.HttpResponse("Query parameter 'resource_type' is required.", status_code=400)

    normalised = resource_type.lower()

    try:
        payload = _resolve_slug_payload(resource_type)
        return json_payload(payload)
    except ValueError:
        logging.info("[slug_lookup] No slug mapping found for resource type '%s'.", normalised)
        return json_message(f"Slug not found for resource type '{normalised}'.", status_code=404)
    except Exception:
        logging.exception("[slug_lookup] Unexpected error while resolving slug.")
        return json_message("Slug lookup failed.", status_code=500)


def _perform_slug_sync() -> Tuple[int, str]:
    remote_slugs = get_all_remote_slugs()
    if not remote_slugs:
        return 502, "Slug sync failed: upstream returned no data."

    slug_table = get_table_client(SLUG_TABLE_NAME)
    created_count = 0
    updated_count = 0
    existing_count = 0

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
            else:
                existing_count += 1
        except Exception:
            new_entity = {
                "PartitionKey": partition_key,
                "RowKey": row_key,
                "Slug": slug,
                "FullName": full_name,
                "UpdatedAt": datetime.utcnow().isoformat(),
            }
            slug_table.upsert_entity(entity=new_entity, mode=UpdateMode.MERGE)
            created_count += 1

    total = created_count + updated_count + existing_count
    message = (
        f"Slug sync complete. {created_count} created, {updated_count} updated, "
        f"{existing_count} existing ({total} total)."
    )
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
