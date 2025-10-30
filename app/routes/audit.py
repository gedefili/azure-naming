"""HTTP routes for audit lookups."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Dict, List

import azure.functions as func
from azure_functions_openapi.decorator import openapi as openapi_doc

from app import app
from app.constants import AUDIT_TABLE_NAME, ELEVATED_ROLES, NAMES_TABLE_NAME
from app.models import AuditBulkResponse, AuditRecordResponse
from app.responses import json_payload
from app.dependencies import (
    AuthError,
    ResourceNotFoundError,
    get_table_client,
    require_role,
    is_authorized,
)


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


def _query_audit_entities(table, filter_query: str | None):
    if filter_query:
        return list(table.query_entities(query_filter=filter_query))
    return list(table.list_entities())


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
        "subsystem": entity.get("Subsystem"),
        "system": entity.get("System"),
        "index": entity.get("Index"),
    }
    
    # Include any additional custom metadata that was stored
    # Exclude system fields and standard naming fields already in audit_info
    system_fields = {"PartitionKey", "RowKey", "Timestamp", "odata.metadata", "odata.type", "etag"}
    standard_fields = {"ResourceType", "InUse", "ClaimedBy", "ClaimedAt", "ReleasedBy", "ReleasedAt", 
                       "ReleaseReason", "Slug", "Project", "Purpose", "Subsystem", "System", "Index", "RequestedBy"}
    for key, value in entity.items():
        if key not in system_fields and key not in standard_fields and value is not None:
            # Convert key to snake_case for consistency in JSON response
            snake_case_key = ''.join(['_' + c.lower() if c.isupper() else c for c in key]).lstrip('_')
            audit_info[snake_case_key] = value

    return json_payload(audit_info)


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

    if (
        (not target_user or target_user.lower() != user_id.lower())
        and not ELEVATED_ROLES.intersection(roles)
    ):
        return func.HttpResponse(
            "Forbidden: elevated role required to query other users.", status_code=403
        )

    filter_query = _build_filter(filters)

    try:
        table = get_table_client(AUDIT_TABLE_NAME)
        entities = _query_audit_entities(table, filter_query)
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

    return json_payload({"results": records})
