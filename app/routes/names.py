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
from core.name_service import _sanitize_metadata_dict


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
    # Common regions: wus, wus2, eus, eus1 (2-4 chars)
    # Common environments: prd, stg, tst, uat, alt, dev (3 chars)
    if not region or not environment:
        # Try to extract from name by trying common patterns
        possible_regions = ["wus2", "wus", "eus1", "eus"]
        possible_envs = ["prd", "stg", "tst", "uat", "alt", "dev"]
        
        for poss_region in possible_regions:
            if name.startswith(poss_region):
                remainder = name[len(poss_region):]
                for poss_env in possible_envs:
                    if remainder.startswith(poss_env):
                        region = poss_region
                        environment = poss_env
                        break
                if region and environment:
                    break

    if not region or not environment:
        return func.HttpResponse(
            "Unable to determine partition key. Please provide region and environment, or use a name that starts with region (e.g., wus2prd...).",
            status_code=400
        )

    partition_key = f"{region}-{environment}"

    try:
        names_table = get_table_client(NAMES_TABLE_NAME)
        entity = names_table.get_entity(partition_key=partition_key, row_key=name)
    except Exception:
        logging.exception("[release_name] Name not found during release.")
        return func.HttpResponse("Name not found.", status_code=404)

    if not is_authorized(user_roles, user_id, entity.get("ClaimedBy"), entity.get("ReleasedBy")):
        return func.HttpResponse("Forbidden: not authorized to release this name.", status_code=403)

    # Use ETag for optimistic concurrency control to prevent rollback attacks
    # If entity was modified after we fetched it, this will fail
    etag = entity.get("odata.metadata", {}).get("etag")
    
    entity["InUse"] = False
    entity["ReleasedBy"] = user_id
    entity["ReleasedAt"] = datetime.utcnow().isoformat()
    entity["ReleaseReason"] = reason

    try:
        # Use REPLACE mode with ETag to ensure we only update if unmodified since read
        names_table.update_entity(entity=entity, mode=UpdateMode.REPLACE, match_condition="MatchIfNotModified")
    except Exception as exc:
        # If ETag mismatch, entity was modified - likely a concurrent release
        if "etag" in str(exc).lower() or "precondition" in str(exc).lower():
            logging.warning("[release_name] Concurrent modification detected (ETag mismatch).")
            return func.HttpResponse("Name was modified by another request. Please retrieve and try again.", status_code=409)
        logging.exception("[release_name] Failed to update storage during release.")
        return func.HttpResponse("Error releasing name.", status_code=500)

    metadata = {
        "Region": entity.get("PartitionKey", "").split("-")[0] if entity.get("PartitionKey") else None,
        "Environment": entity.get("PartitionKey", "").split("-")[1] if entity.get("PartitionKey") else None,
        "ResourceType": entity.get("ResourceType"),
        "Slug": entity.get("Slug"),
        "Project": entity.get("Project"),
        "Purpose": entity.get("Purpose"),
        "Subsystem": entity.get("Subsystem"),
        "System": entity.get("System"),
        "Index": entity.get("Index"),
    }
    metadata = {key: value for key, value in metadata.items() if value}
    
    # Capture all metadata stored with the entity during claim
    # Include any custom fields that may have been stored
    system_fields = {"PartitionKey", "RowKey", "Timestamp", "odata.metadata", "odata.type", "etag"}
    audit_specific = {"Region", "Environment", "ResourceType", "Slug", "Project", "Purpose", "Subsystem", "System", "Index", 
                      "InUse", "ClaimedBy", "ClaimedAt", "ReleasedBy", "ReleasedAt", "ReleaseReason", "RequestedBy"}
    for key, value in entity.items():
        if key not in system_fields and key not in audit_specific and value is not None:
            # Add any additional custom metadata that was stored
            metadata[key] = value

    # Sanitize metadata before audit logging
    metadata = _sanitize_metadata_dict(metadata)
    write_audit_log(name, user_id, "released", reason, metadata=metadata)

    return json_message("Name released successfully.", status_code=200)
