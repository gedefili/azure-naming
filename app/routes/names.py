"""HTTP routes for claiming and releasing names."""

from __future__ import annotations

import logging
from datetime import datetime

import azure.functions as func
from azure.data.tables import UpdateMode
from azure_functions_openapi.decorator import openapi as openapi_doc

from app import app
from app.constants import NAMES_TABLE_NAME
from app.errors import handle_name_generation_error
from app.models import MessageResponse, NameClaimRequest, NameClaimResponse, ReleaseRequest
from app.responses import build_claim_response, json_message
from app.dependencies import (
    AuthError,
    generate_and_claim_name,
    get_table_client,
    is_authorized,
    require_role,
    write_audit_log,
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
        return build_claim_response(result, user_id)
    except Exception as exc:  # pragma: no cover - centralised error handling
        return handle_name_generation_error(exc, log_prefix=log_prefix)


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

    name = (data.get("name") or "").lower()
    reason = data.get("reason", "not specified")

    if not name:
        return func.HttpResponse("Missing required field: name.", status_code=400)

    # Try to extract region and environment from provided fields first
    region = (data.get("region") or "").lower()
    environment = (data.get("environment") or "").lower()

    # If not provided, attempt to extract from the name
    # Names follow pattern: {region}{environment}{prefix}{slug}... or similar
    # Try common region/env patterns to deduce partition key
    # For now, we'll search across all partitions if region/env not provided
    partition_key = None
    if region and environment:
        partition_key = f"{region}-{environment}"

    try:
        names_table = get_table_client(NAMES_TABLE_NAME)
        
        # If we have partition key, use it directly
        if partition_key:
            entity = names_table.get_entity(partition_key=partition_key, row_key=name)
        else:
            # If no partition key, we need to search - for now require region/environment
            # In a real scenario, you might query across all partitions or require them
            return func.HttpResponse(
                "Unable to determine partition key. Please provide region and environment.",
                status_code=400
            )
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
        names_table.update_entity(entity=entity, mode=UpdateMode.REPLACE)
    except Exception:
        logging.exception("[release_name] Failed to update storage during release.")
        return func.HttpResponse("Error releasing name.", status_code=500)

    metadata = {
        "Region": entity.get("PartitionKey", "").split("-")[0] if entity.get("PartitionKey") else None,
        "Environment": entity.get("PartitionKey", "").split("-")[1] if entity.get("PartitionKey") else None,
        "ResourceType": entity.get("ResourceType"),
        "Slug": entity.get("Slug"),
        "Project": entity.get("Project"),
        "Purpose": entity.get("Purpose"),
        "System": entity.get("System"),
        "Index": entity.get("Index"),
    }
    metadata = {key: value for key, value in metadata.items() if value}

    write_audit_log(name, user_id, "released", reason, metadata=metadata)

    return json_message("Name released successfully.", status_code=200)
