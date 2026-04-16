"""HTTP routes for claiming and releasing names."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Tuple

import azure.functions as func
from azure.core import MatchConditions
from azure.core.exceptions import ResourceModifiedError
from azure.data.tables import UpdateMode
from azure_functions_openapi.decorator import openapi as openapi_doc

from app import app
from app.constants import NAMES_TABLE_NAME
from app.errors import handle_name_generation_error
from app.models import (
    AdminNameStateRequest,
    MessageResponse,
    NameClaimRequest,
    NameClaimResponse,
    ReleaseRequest,
)
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

_SYSTEM_FIELDS = {"PartitionKey", "RowKey", "Timestamp", "odata.metadata", "odata.type", "etag"}
_AUDIT_RESERVED_FIELDS = {
    "Region", "Environment", "ResourceType", "Slug", "Project", "Purpose", "Subsystem", "System", "Index",
    "InUse", "ClaimedBy", "ClaimedAt", "ReleasedBy", "ReleasedAt", "ReleaseReason", "RequestedBy",
    "ClaimState", "StateChangedAt", "StateChangedBy", "StateVersion", "LastLifecycleAction",
    "OrphanedBy", "OrphanedAt", "OrphanReason",
}


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


def _resolve_partition_from_request(name: str, data: Dict[str, Any]) -> Tuple[str, str, str] | None:
    region = (data.get("region") or "").lower()
    environment = (data.get("environment") or "").lower()

    if not region or not environment:
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
        return None

    return region, environment, f"{region}-{environment}"


def _get_claim_state(entity: Dict[str, Any]) -> str:
    state = str(entity.get("ClaimState") or "").strip().lower()
    if state:
        return state
    return "claimed" if entity.get("InUse", False) else "released"


def _next_state_version(entity: Dict[str, Any]) -> int:
    try:
        return int(entity.get("StateVersion", 0)) + 1
    except (TypeError, ValueError):
        return 1


def _build_audit_metadata(entity: Dict[str, Any], *, state_before: str, state_after: str, reason: str) -> Dict[str, Any]:
    partition_key = str(entity.get("PartitionKey") or "")
    region, _, environment = partition_key.partition("-")

    metadata: Dict[str, Any] = {
        "Region": region or None,
        "Environment": environment or None,
        "ResourceType": entity.get("ResourceType"),
        "Slug": entity.get("Slug"),
        "Project": entity.get("Project"),
        "Purpose": entity.get("Purpose"),
        "Subsystem": entity.get("Subsystem"),
        "System": entity.get("System"),
        "Index": entity.get("Index"),
        "ClaimState": entity.get("ClaimState"),
        "StateChangedAt": entity.get("StateChangedAt"),
        "StateChangedBy": entity.get("StateChangedBy"),
        "StateVersion": entity.get("StateVersion"),
        "OrphanedBy": entity.get("OrphanedBy"),
        "OrphanedAt": entity.get("OrphanedAt"),
        "OrphanReason": entity.get("OrphanReason"),
        "ReleasedBy": entity.get("ReleasedBy"),
        "ReleasedAt": entity.get("ReleasedAt"),
        "ReleaseReason": entity.get("ReleaseReason"),
        "StateBefore": state_before,
        "StateAfter": state_after,
    }

    for key, value in entity.items():
        if key not in _SYSTEM_FIELDS and key not in _AUDIT_RESERVED_FIELDS and value is not None:
            metadata[key] = value

    metadata["Reason"] = reason
    return _sanitize_metadata_dict({key: value for key, value in metadata.items() if value is not None})


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

    partition_details = _resolve_partition_from_request(name, data)
    if partition_details is None:
        return func.HttpResponse(
            "Unable to determine partition key. Please provide region and environment, or use a name that starts with region (e.g., wus2prd...).",
            status_code=400
        )

    _region, _environment, partition_key = partition_details

    try:
        names_table = get_table_client(NAMES_TABLE_NAME)
        entity = names_table.get_entity(partition_key=partition_key, row_key=name)
    except Exception:
        logging.exception("[release_name] Name not found during release.")
        return func.HttpResponse("Name not found.", status_code=404)

    if not is_authorized(user_roles, user_id, entity.get("ClaimedBy"), entity.get("ReleasedBy")):
        return func.HttpResponse("Forbidden: not authorized to release this name.", status_code=403)

    state_before = _get_claim_state(entity)
    released_at = datetime.now(tz=timezone.utc).isoformat()
    entity["InUse"] = False
    entity["ClaimState"] = "released"
    entity["StateChangedBy"] = user_id
    entity["StateChangedAt"] = released_at
    entity["StateVersion"] = _next_state_version(entity)
    entity["LastLifecycleAction"] = "released"
    entity["ReleasedBy"] = user_id
    entity["ReleasedAt"] = released_at
    entity["ReleaseReason"] = reason
    entity.pop("OrphanedBy", None)
    entity.pop("OrphanedAt", None)
    entity.pop("OrphanReason", None)

    try:
        # Use REPLACE mode with MatchIfNotModified to ensure we only update if unmodified since read
        names_table.update_entity(entity=entity, mode=UpdateMode.REPLACE, match_condition=MatchConditions.IfNotModified)
    except ResourceModifiedError:
        # Entity was modified after we fetched it - likely a concurrent release
        logging.warning("[release_name] Concurrent modification detected (ETag mismatch).")
        return func.HttpResponse("Name was modified by another request. Please retrieve and try again.", status_code=409)
    except Exception as exc:
        logging.exception("[release_name] Failed to update storage during release.")
        return func.HttpResponse("Error releasing name.", status_code=500)

    metadata = _build_audit_metadata(entity, state_before=state_before, state_after="released", reason=reason)
    write_audit_log(name, user_id, "released", reason, metadata=metadata)

    return json_message("Name released successfully.", status_code=200)


@app.function_name(name="admin_remediate_name")
@app.route(route="claims/remediate", methods=[func.HttpMethod.POST])
@openapi_doc(
    summary="Admin remediation for claim lifecycle state",
    description="Allows an admin operator to mark a claim as orphaned and reusable or to purge it entirely.",
    tags=["Names"],
    request_model=AdminNameStateRequest,
    response_model=MessageResponse,
    operation_id="adminRemediateName",
    route="/claims/remediate",
    method="post",
)
def admin_remediate_name(req: func.HttpRequest) -> func.HttpResponse:
    """Allow an admin operator to orphan or purge an existing claim."""

    logging.info("[admin_remediate_name] Processing admin lifecycle remediation request.")

    try:
        user_id, _roles = require_role(req.headers, min_role="admin")
    except AuthError as exc:
        return func.HttpResponse(str(exc), status_code=exc.status)

    try:
        data = req.get_json()
    except ValueError:
        return func.HttpResponse("Invalid JSON payload.", status_code=400)

    name = (data.get("name") or "").lower()
    action = (data.get("action") or "").strip().lower()
    reason = (data.get("reason") or "").strip()

    if not name:
        return func.HttpResponse("Missing required field: name.", status_code=400)
    if action not in {"orphan", "purge"}:
        return func.HttpResponse("Field 'action' must be either 'orphan' or 'purge'.", status_code=400)
    if not reason:
        return func.HttpResponse("Missing required field: reason.", status_code=400)

    partition_details = _resolve_partition_from_request(name, data)
    if partition_details is None:
        return func.HttpResponse(
            "Unable to determine partition key. Please provide region and environment, or use a name that starts with region (e.g., wus2prd...).",
            status_code=400,
        )

    _region, _environment, partition_key = partition_details

    try:
        names_table = get_table_client(NAMES_TABLE_NAME)
        entity = names_table.get_entity(partition_key=partition_key, row_key=name)
    except Exception:
        logging.exception("[admin_remediate_name] Name not found during remediation.")
        return func.HttpResponse("Name not found.", status_code=404)

    state_before = _get_claim_state(entity)

    if action == "orphan":
        orphaned_at = datetime.now(tz=timezone.utc).isoformat()
        entity["InUse"] = False
        entity["ClaimState"] = "orphaned"
        entity["StateChangedBy"] = user_id
        entity["StateChangedAt"] = orphaned_at
        entity["StateVersion"] = _next_state_version(entity)
        entity["LastLifecycleAction"] = "orphaned"
        entity["OrphanedBy"] = user_id
        entity["OrphanedAt"] = orphaned_at
        entity["OrphanReason"] = reason
        entity.pop("ReleasedBy", None)
        entity.pop("ReleasedAt", None)
        entity.pop("ReleaseReason", None)

        try:
            names_table.update_entity(entity=entity, mode=UpdateMode.REPLACE, match_condition=MatchConditions.IfNotModified)
        except ResourceModifiedError:
            logging.warning("[admin_remediate_name] Concurrent modification detected while orphaning claim.")
            return func.HttpResponse("Name was modified by another request. Please retrieve and try again.", status_code=409)
        except Exception:
            logging.exception("[admin_remediate_name] Failed to persist orphaned state.")
            return func.HttpResponse("Error updating name state.", status_code=500)

        metadata = _build_audit_metadata(entity, state_before=state_before, state_after="orphaned", reason=reason)
        write_audit_log(name, user_id, "orphaned", reason, metadata=metadata)
        return json_message("Name claim marked as orphaned and reusable.", status_code=200)

    metadata = _build_audit_metadata(entity, state_before=state_before, state_after="purged", reason=reason)

    try:
        names_table.delete_entity(partition_key=partition_key, row_key=name)
    except Exception:
        logging.exception("[admin_remediate_name] Failed to purge claim.")
        return func.HttpResponse("Error purging name claim.", status_code=500)

    write_audit_log(name, user_id, "purged", reason, metadata=metadata)
    return json_message("Name claim purged successfully.", status_code=200)
