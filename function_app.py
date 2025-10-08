"""Azure Functions v2 programming model entry points."""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Dict, List, Tuple

import azure.functions as func
from azure.core.exceptions import ResourceNotFoundError

from utils.audit_logs import write_audit_log
from utils.auth import AuthError, is_authorized, require_role
from utils.name_service import (
    InvalidRequestError,
    NameConflictError,
    NameGenerationResult,
    generate_and_claim_name,
)
from utils.slug_fetcher import SlugSourceError, get_all_remote_slugs
from utils.storage import get_table_client

try:  # pragma: no cover - dependency may be optional in some environments
    from azure.core.exceptions import AzureError
except ImportError:  # pragma: no cover - fallback when Azure SDK extras absent
    class AzureError(Exception):
        """Fallback AzureError when the Azure SDK is unavailable."""


app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

NAMES_TABLE_NAME = "ClaimedNames"
AUDIT_TABLE_NAME = "AuditLogs"
SLUG_TABLE_NAME = "SlugMappings"
SLUG_PARTITION_KEY = "slug"
_ELEVATED_ROLES = {"manager", "admin"}


def _build_claim_response(result: NameGenerationResult, user_id: str) -> func.HttpResponse:
    body = result.to_dict()
    body["claimedBy"] = user_id
    return func.HttpResponse(
        json.dumps(body),
        mimetype="application/json",
        status_code=201,
    )


def _handle_claim_request(req: func.HttpRequest, *, log_prefix: str) -> func.HttpResponse:
    logging.info("[%s] Processing claim request with RBAC.", log_prefix)

    try:
        user_id, _roles = require_role(req.headers, min_role="user")
    except AuthError as exc:
        return func.HttpResponse(str(exc), status_code=exc.status)

    try:
        payload = req.get_json()
    except ValueError:
        return func.HttpResponse("Invalid JSON payload.", status_code=400)

    try:
        result = generate_and_claim_name(payload, requested_by=user_id)
        return _build_claim_response(result, user_id)
    except InvalidRequestError as exc:
        return func.HttpResponse(str(exc), status_code=400)
    except NameConflictError as exc:
        return func.HttpResponse(str(exc), status_code=409)
    except Exception:  # pragma: no cover - defensive logging
        logging.exception("[%s] Failed to claim name.", log_prefix)
        return func.HttpResponse("Error claiming name.", status_code=500)


@app.function_name(name="claim_name")
@app.route(route="claim", methods=[func.HttpMethod.POST])
def claim_name(req: func.HttpRequest) -> func.HttpResponse:
    """Generate and claim a compliant name."""

    return _handle_claim_request(req, log_prefix="claim_name")


@app.function_name(name="generate_name")
@app.route(route="generate", methods=[func.HttpMethod.POST])
def generate_name(req: func.HttpRequest) -> func.HttpResponse:
    """Alias route for backwards compatibility with legacy clients."""

    return _handle_claim_request(req, log_prefix="generate_names")


@app.function_name(name="release_name")
@app.route(route="release", methods=[func.HttpMethod.POST])
def release_name(req: func.HttpRequest) -> func.HttpResponse:
    """Release a previously claimed name."""

    logging.info("[release_name] Processing release request with RBAC.")

    try:
        user_id, user_roles = require_role(req.headers, min_role="user")
    except AuthError as exc:
        return func.HttpResponse(str(exc), status_code=exc.status)

    try:
        data = req.get_json()
    except ValueError:
        return func.HttpResponse("Invalid JSON payload.", status_code=400)

    region = (data.get("region") or "").lower()
    environment = (data.get("environment") or "").lower()
    name = (data.get("name") or "").lower()
    reason = data.get("reason", "not specified")

    if not region or not environment or not name:
        return func.HttpResponse("Missing required fields.", status_code=400)

    partition_key = f"{region}-{environment}"

    try:
        names_table = get_table_client(NAMES_TABLE_NAME)
        entity = names_table.get_entity(partition_key=partition_key, row_key=name)
    except Exception:
        logging.exception("[release_name] Name not found during release.")
        return func.HttpResponse("Name not found.", status_code=404)

    if not is_authorized(user_roles, user_id, entity.get("ClaimedBy"), entity.get("ReleasedBy")):
        return func.HttpResponse("Forbidden: not authorized to release this name.", status_code=403)

    entity["InUse"] = False
    entity["ReleasedBy"] = user_id
    entity["ReleasedAt"] = datetime.utcnow().isoformat()
    entity["ReleaseReason"] = reason

    try:
        names_table.update_entity(entity=entity, mode="Replace")
    except Exception:
        logging.exception("[release_name] Failed to update storage during release.")
        return func.HttpResponse("Error releasing name.", status_code=500)

    metadata = {
        "Region": region,
        "Environment": environment,
        "ResourceType": entity.get("ResourceType"),
        "Slug": entity.get("Slug"),
        "Project": entity.get("Project"),
        "Purpose": entity.get("Purpose"),
        "System": entity.get("System"),
        "Index": entity.get("Index"),
    }
    metadata = {key: value for key, value in metadata.items() if value}

    write_audit_log(name, user_id, "released", reason, metadata=metadata)

    return func.HttpResponse(json.dumps({"message": "Name released successfully."}), status_code=200)


@app.function_name(name="audit_name")
@app.route(route="audit", methods=[func.HttpMethod.GET])
def audit_name(req: func.HttpRequest) -> func.HttpResponse:
    """Retrieve audit information for a single claimed name."""

    logging.info("[audit_name] Starting RBAC-secured audit check.")

    try:
        user_id, user_roles = require_role(req.headers, min_role="user")
    except AuthError as exc:
        return func.HttpResponse(str(exc), status_code=exc.status)

    region = (req.params.get("region") or "").lower()
    environment = (req.params.get("environment") or "").lower()
    name = (req.params.get("name") or "").lower()

    if not region or not environment or not name:
        return func.HttpResponse(
            "Missing query parameters: region, environment, name.", status_code=400
        )

    partition_key = f"{region}-{environment}"

    try:
        table = get_table_client(NAMES_TABLE_NAME)
        entity = table.get_entity(partition_key=partition_key, row_key=name)
    except ResourceNotFoundError:
        return func.HttpResponse("Audit entry not found.", status_code=404)
    except Exception:
        logging.exception("[audit_name] Failed to retrieve audit entity.")
        return func.HttpResponse("Error retrieving audit entry.", status_code=500)

    if not is_authorized(user_roles, user_id, entity.get("ClaimedBy"), entity.get("ReleasedBy")):
        return func.HttpResponse("Forbidden: not authorized to view this name.", status_code=403)

    audit_info = {
        "name": entity["RowKey"],
        "resource_type": entity.get("ResourceType", "unknown"),
        "in_use": entity.get("InUse", False),
        "claimed_by": entity.get("ClaimedBy"),
        "claimed_at": entity.get("ClaimedAt"),
        "released_by": entity.get("ReleasedBy"),
        "released_at": entity.get("ReleasedAt"),
        "release_reason": entity.get("ReleaseReason"),
        "region": region,
        "environment": environment,
        "slug": entity.get("Slug"),
        "project": entity.get("Project"),
        "purpose": entity.get("Purpose"),
        "system": entity.get("System"),
        "index": entity.get("Index"),
    }

    return func.HttpResponse(json.dumps(audit_info), status_code=200, mimetype="application/json")


def _escape(value: str) -> str:
    return value.replace("'", "''")


def _build_filter(params: Dict[str, str]) -> str:
    filters: List[str] = []

    user = params.get("user")
    if user:
        filters.append(f"User eq '{_escape(user.lower())}'")

    project = params.get("project")
    if project:
        filters.append(f"Project eq '{_escape(project.lower())}'")

    purpose = params.get("purpose")
    if purpose:
        filters.append(f"Purpose eq '{_escape(purpose.lower())}'")

    region = params.get("region")
    if region:
        filters.append(f"Region eq '{_escape(region.lower())}'")

    environment = params.get("environment")
    if environment:
        filters.append(f"Environment eq '{_escape(environment.lower())}'")

    action = params.get("action")
    if action:
        filters.append(f"Action eq '{_escape(action.lower())}'")

    start = params.get("start")
    if start:
        filters.append(f"EventTime ge datetime'{start}'")

    end = params.get("end")
    if end:
        filters.append(f"EventTime le datetime'{end}'")

    return " and ".join(filters)


@app.function_name(name="audit_bulk")
@app.route(route="audit_bulk", methods=[func.HttpMethod.GET])
def audit_bulk(req: func.HttpRequest) -> func.HttpResponse:
    """List audit records with optional filters."""

    logging.info("[audit_bulk] Processing bulk audit request.")

    try:
        user_id, roles = require_role(req.headers, min_role="user")
    except AuthError as exc:
        return func.HttpResponse(str(exc), status_code=exc.status)

    filters = req.params
    target_user = filters.get("user")

    if (not target_user or target_user.lower() != user_id.lower()) and not _ELEVATED_ROLES.intersection(roles):
        return func.HttpResponse(
            "Forbidden: elevated role required to query other users.", status_code=403
        )

    filter_query = _build_filter(filters)

    try:
        table = get_table_client(AUDIT_TABLE_NAME)
        entities = list(table.query_entities(filter=filter_query) if filter_query else table.list_entities())
    except Exception:
        logging.exception("[audit_bulk] Failed to query audit logs.")
        return func.HttpResponse("Error retrieving audit logs.", status_code=500)

    entities.sort(key=lambda e: e.get("EventTime") or datetime.min, reverse=True)

    records: List[Dict[str, object]] = []
    for entity in entities:
        event_time = entity.get("EventTime") or datetime.min
        if isinstance(event_time, datetime):
            timestamp = event_time.isoformat()
        else:
            timestamp = str(event_time)
        records.append(
            {
                "name": entity.get("PartitionKey"),
                "event_id": entity.get("RowKey"),
                "user": entity.get("User"),
                "action": entity.get("Action"),
                "note": entity.get("Note"),
                "timestamp": timestamp,
                "region": entity.get("Region"),
                "environment": entity.get("Environment"),
                "project": entity.get("Project"),
                "purpose": entity.get("Purpose"),
                "resource_type": entity.get("ResourceType"),
            }
        )

    return func.HttpResponse(json.dumps({"results": records}), status_code=200, mimetype="application/json")


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
            slug_table.upsert_entity(entity=new_entity, mode="Replace")
            updated_count += 1

    message = f"Slug sync complete. {updated_count} entries updated/created."
    logging.info("[slug_sync] %s", message)
    return 200, message


@app.function_name(name="slug_sync")
@app.route(route="slug_sync", methods=[func.HttpMethod.POST])
def slug_sync(req: func.HttpRequest) -> func.HttpResponse:
    """Synchronize slug mappings via HTTP trigger."""

    logging.info("[slug_sync] Starting slug synchronization from GitHub source.")

    try:
        require_role(req.headers, min_role="user")
    except AuthError as exc:
        return func.HttpResponse(str(exc), status_code=exc.status)

    try:
        status_code, message = _perform_slug_sync()
        return func.HttpResponse(message, status_code=status_code)
    except SlugSourceError as exc:
        logging.warning("[slug_sync] Upstream slug source unavailable: %s", exc)
        return func.HttpResponse("Slug sync failed: upstream source unavailable.", status_code=503)
    except (AzureError, RuntimeError):
        logging.exception("[slug_sync] Failed to connect to storage.")
        return func.HttpResponse("Slug sync failed: storage unavailable.", status_code=500)
    except Exception:
        logging.exception("[slug_sync] Slug sync failed.")
        return func.HttpResponse("Slug sync failed.", status_code=500)


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

```}