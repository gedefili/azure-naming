"""Azure Functions v2 programming model entry points."""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Dict, List, Tuple

import azure.functions as func
from azure.core.exceptions import ResourceNotFoundError
try:  # pragma: no cover - optional dependency during docs builds
    from azure.data.tables import UpdateMode
except ImportError:  # pragma: no cover
    class UpdateMode:  # type: ignore[override]
        MERGE = "MERGE"
from azure_functions_openapi.decorator import openapi as openapi_doc
from azure_functions_openapi.openapi import get_openapi_json
from azure_functions_openapi.swagger_ui import render_swagger_ui
from pydantic import BaseModel, ConfigDict, Field

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


app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

NAMES_TABLE_NAME = "ClaimedNames"
AUDIT_TABLE_NAME = "AuditLogs"
SLUG_TABLE_NAME = "SlugMappings"
SLUG_PARTITION_KEY = "slug"
_ELEVATED_ROLES = {"admin"}
API_TITLE = "Azure Naming Service API"
API_VERSION = "1.0.0"


class NameClaimRequest(BaseModel):
    """Schema describing the payload used to generate and claim a name."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    resource_type: str = Field(..., description="Azure resource type (e.g. storage_account).")
    region: str = Field(..., description="Azure region short code (e.g. wus2).")
    environment: str = Field(..., description="Deployment environment (e.g. dev, prod).")
    project: str | None = Field(default=None, description="Optional project or domain segment.")
    purpose: str | None = Field(default=None, description="Optional purpose or subdomain segment.")
    system: str | None = Field(default=None, description="Optional system identifier.")
    index: str | None = Field(default=None, description="Optional numeric tie breaker.")
    session_id: str | None = Field(
        default=None,
        description="Optional session identifier to apply user defaults.",
        alias="sessionId",
    )


class DisplayFieldEntry(BaseModel):
    key: str
    label: str
    value: str | None = None
    description: str | None = None


class NameClaimResponse(BaseModel):
    """Successful response when a name is generated and claimed."""

    name: str
    resourceType: str
    region: str
    environment: str
    slug: str
    claimedBy: str
    project: str | None = None
    purpose: str | None = None
    system: str | None = None
    index: str | None = None
    display: List[DisplayFieldEntry] = Field(default_factory=list)


class ReleaseRequest(BaseModel):
    """Schema describing a release request."""

    name: str = Field(..., description="Fully qualified name to release.")
    region: str = Field(..., description="Region where the name was registered.")
    environment: str = Field(..., description="Environment where the name was registered.")
    reason: str | None = Field(
        default="not specified",
        description="Optional note describing why the name is being released.",
    )


class MessageResponse(BaseModel):
    message: str


class AuditRecordResponse(BaseModel):
    name: str
    resource_type: str
    in_use: bool
    claimed_by: str | None = None
    claimed_at: str | None = None
    released_by: str | None = None
    released_at: str | None = None
    release_reason: str | None = None
    region: str
    environment: str
    slug: str | None = None
    project: str | None = None
    purpose: str | None = None
    system: str | None = None
    index: str | None = None


class AuditLogEntry(BaseModel):
    name: str
    event_id: str
    user: str | None = None
    action: str | None = None
    note: str | None = None
    timestamp: str
    region: str | None = None
    environment: str | None = None
    project: str | None = None
    purpose: str | None = None
    resource_type: str | None = None


class AuditBulkResponse(BaseModel):
    results: List[AuditLogEntry]


def _build_claim_response(result: NameGenerationResult, user_id: str) -> func.HttpResponse:
    body = result.to_dict()
    body["claimedBy"] = user_id
    body.setdefault("display", [])
    return func.HttpResponse(
        json.dumps(body),
        mimetype="application/json",
        status_code=201,
    )


def _json_message(message: str, *, status_code: int) -> func.HttpResponse:
    return func.HttpResponse(
        json.dumps({"message": message}),
        mimetype="application/json",
        status_code=status_code,
    )


def _handle_claim_request(req: func.HttpRequest, *, log_prefix: str) -> func.HttpResponse:
    logging.info("[%s] Processing claim request with RBAC.", log_prefix)

    try:
        user_id, _roles = require_role(req.headers, min_role="contributor")
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
@openapi_doc(
    summary="Generate and claim a compliant resource name",
    description=(
        "Generates an Azure-compliant name based on resource type, region, and environment, "
        "then marks it as claimed for the caller. Optional metadata segments can be supplied "
        "to influence slug composition."
    ),
    tags=["Names"],
    request_model=NameClaimRequest,
    response_model=NameClaimResponse,
    operation_id="claimName",
    route="/claim",
    method="post",
)
def claim_name(req: func.HttpRequest) -> func.HttpResponse:
    """Generate and claim a compliant name."""

    return _handle_claim_request(req, log_prefix="claim_name")


@app.function_name(name="generate_name")
@app.route(route="generate", methods=[func.HttpMethod.POST])
@openapi_doc(
    summary="Legacy alias for claim endpoint",
    description="Backwards compatible alias that behaves identically to /claim.",
    tags=["Names"],
    request_model=NameClaimRequest,
    response_model=NameClaimResponse,
    operation_id="generateName",
    route="/generate",
    method="post",
)
def generate_name(req: func.HttpRequest) -> func.HttpResponse:
    """Alias route for backwards compatibility with legacy clients."""

    return _handle_claim_request(req, log_prefix="generate_names")


@app.function_name(name="release_name")
@app.route(route="release", methods=[func.HttpMethod.POST])
@openapi_doc(
    summary="Release a previously claimed name",
    description="Marks a claimed name as available again once authorization checks pass.",
    tags=["Names"],
    request_model=ReleaseRequest,
    response_model=MessageResponse,
    operation_id="releaseName",
    route="/release",
    method="post",
)
def release_name(req: func.HttpRequest) -> func.HttpResponse:
    """Release a previously claimed name."""

    logging.info("[release_name] Processing release request with RBAC.")

    try:
        user_id, user_roles = require_role(req.headers, min_role="contributor")
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

    return _json_message("Name released successfully.", status_code=200)


@app.function_name(name="audit_name")
@app.route(route="audit", methods=[func.HttpMethod.GET])
@openapi_doc(
    summary="Retrieve audit details for a claimed name",
    description="Returns the audit record for a single resource name if the caller is authorized.",
    tags=["Audit"],
    parameters=[
        {
            "name": "region",
            "in": "query",
            "required": True,
            "schema": {"type": "string"},
            "description": "Region code where the name was registered.",
        },
        {
            "name": "environment",
            "in": "query",
            "required": True,
            "schema": {"type": "string"},
            "description": "Environment where the name was registered (dev/test/prod).",
        },
        {
            "name": "name",
            "in": "query",
            "required": True,
            "schema": {"type": "string"},
            "description": "Fully qualified name to inspect.",
        },
    ],
    response_model=AuditRecordResponse,
    operation_id="auditName",
    route="/audit",
    method="get",
)
def audit_name(req: func.HttpRequest) -> func.HttpResponse:
    """Retrieve audit information for a single claimed name."""

    logging.info("[audit_name] Starting RBAC-secured audit check.")

    try:
        user_id, user_roles = require_role(req.headers, min_role="reader")
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
@openapi_doc(
    summary="List audit records with optional filters",
    description=(
        "Returns audit history optionally filtered by user, project, purpose, region, environment, "
        "action, or time range. Non-elevated users can only view their own records."
    ),
    tags=["Audit"],
    parameters=[
        {"name": "user", "in": "query", "required": False, "schema": {"type": "string"}},
        {"name": "project", "in": "query", "required": False, "schema": {"type": "string"}},
        {"name": "purpose", "in": "query", "required": False, "schema": {"type": "string"}},
        {"name": "region", "in": "query", "required": False, "schema": {"type": "string"}},
        {"name": "environment", "in": "query", "required": False, "schema": {"type": "string"}},
        {"name": "action", "in": "query", "required": False, "schema": {"type": "string"}},
        {
            "name": "start",
            "in": "query",
            "required": False,
            "schema": {"type": "string", "format": "date-time"},
            "description": "Filter events occurring on or after this timestamp (ISO 8601).",
        },
        {
            "name": "end",
            "in": "query",
            "required": False,
            "schema": {"type": "string", "format": "date-time"},
            "description": "Filter events occurring on or before this timestamp (ISO 8601).",
        },
    ],
    response_model=AuditBulkResponse,
    operation_id="auditBulk",
    route="/audit_bulk",
    method="get",
)
def audit_bulk(req: func.HttpRequest) -> func.HttpResponse:
    """List audit records with optional filters."""

    logging.info("[audit_bulk] Processing bulk audit request.")

    try:
        user_id, roles = require_role(req.headers, min_role="reader")
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
        return _json_message(message, status_code=status_code)
    except SlugSourceError as exc:
        logging.warning("[slug_sync] Upstream slug source unavailable: %s", exc)
        return _json_message("Slug sync failed: upstream source unavailable.", status_code=503)
    except (AzureError, RuntimeError):
        logging.exception("[slug_sync] Failed to connect to storage.")
        return _json_message("Slug sync failed: storage unavailable.", status_code=500)
    except Exception:
        logging.exception("[slug_sync] Slug sync failed.")
        return _json_message("Slug sync failed.", status_code=500)


@app.function_name(name="openapi_spec")
@app.route(
    route="openapi.json",
    methods=[func.HttpMethod.GET],
    auth_level=func.AuthLevel.ANONYMOUS,
)
def openapi_spec(req: func.HttpRequest) -> func.HttpResponse:
    """Serve the generated OpenAPI specification for the HTTP API."""

    try:
        require_role(req.headers, min_role="reader")
    except AuthError as exc:
        return func.HttpResponse(str(exc), status_code=exc.status)
    spec_json = get_openapi_json(title=API_TITLE, version=API_VERSION)
    return func.HttpResponse(spec_json, mimetype="application/json", status_code=200)


@app.function_name(name="swagger_ui")
@app.route(route="docs", methods=[func.HttpMethod.GET], auth_level=func.AuthLevel.ANONYMOUS)
def swagger_ui(req: func.HttpRequest) -> func.HttpResponse:
    """Serve an interactive Swagger UI backed by the generated OpenAPI spec."""

    try:
        require_role(req.headers, min_role="reader")
    except AuthError as exc:
        return func.HttpResponse(str(exc), status_code=exc.status)
    return render_swagger_ui(title=f"{API_TITLE} – Swagger", openapi_url="/api/openapi.json")


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