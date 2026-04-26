"""HTTP routes for listing claimed names.

Phase 1 API addition for the Azure Naming web UX and Confluence extension.

The existing /api/audit endpoint returns one record by name. For the web and
Confluence experiences we need to enumerate claims with pagination and
filtering. This module owns that surface so audit semantics stay focused on
single-record retrieval.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List, Optional

import azure.functions as func
from azure_functions_openapi.decorator import openapi as openapi_doc

from app import app
from app.constants import ELEVATED_ROLES, NAMES_TABLE_NAME
from app.responses import json_payload
from app.dependencies import (
    AuthError,
    get_table_client,
    require_role,
)


_DEFAULT_PAGE_SIZE = 50
_MAX_PAGE_SIZE = 200

_FIELD_MAP = {
    "name": "RowKey",
    "resource_type": "ResourceType",
    "claimed_by": "ClaimedBy",
    "claimed_at": "ClaimedAt",
    "in_use": "InUse",
    "claim_state": "ClaimState",
    "state_changed_at": "StateChangedAt",
    "state_changed_by": "StateChangedBy",
    "released_by": "ReleasedBy",
    "released_at": "ReleasedAt",
    "release_reason": "ReleaseReason",
    "orphaned_by": "OrphanedBy",
    "orphaned_at": "OrphanedAt",
    "orphan_reason": "OrphanReason",
    "slug": "Slug",
    "project": "Project",
    "purpose": "Purpose",
    "subsystem": "Subsystem",
    "system": "System",
    "index": "Index",
}


def _escape(value: str) -> str:
    """Escape single quotes for safe OData string literals."""
    return value.replace("'", "''")


def _normalize_state(value: Any) -> str:
    state = str(value or "").strip().lower()
    if state:
        return state
    return "released"


def _entity_to_claim(entity: Dict[str, Any]) -> Dict[str, Any]:
    partition_key = str(entity.get("PartitionKey") or "")
    region, _, environment = partition_key.partition("-")

    claim = {
        "name": entity.get("RowKey"),
        "resource_type": entity.get("ResourceType"),
        "region": region,
        "environment": environment,
        "in_use": bool(entity.get("InUse", False)),
        "claim_state": _normalize_state(entity.get("ClaimState") or ("claimed" if entity.get("InUse") else "released")),
        "claimed_by": entity.get("ClaimedBy"),
        "claimed_at": entity.get("ClaimedAt"),
        "released_by": entity.get("ReleasedBy"),
        "released_at": entity.get("ReleasedAt"),
        "release_reason": entity.get("ReleaseReason"),
        "state_changed_by": entity.get("StateChangedBy"),
        "state_changed_at": entity.get("StateChangedAt"),
        "state_version": entity.get("StateVersion"),
        "orphaned_by": entity.get("OrphanedBy"),
        "orphaned_at": entity.get("OrphanedAt"),
        "orphan_reason": entity.get("OrphanReason"),
        "slug": entity.get("Slug"),
        "project": entity.get("Project"),
        "purpose": entity.get("Purpose"),
        "subsystem": entity.get("Subsystem"),
        "system": entity.get("System"),
        "index": entity.get("Index"),
    }
    return {k: v for k, v in claim.items() if v is not None}


def _parse_int(raw: Optional[str], *, default: int, minimum: int, maximum: int) -> int:
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise ValueError(f"value '{raw}' is not a valid integer")
    if value < minimum:
        return minimum
    if value > maximum:
        return maximum
    return value


def _parse_bool(raw: Optional[str]) -> Optional[bool]:
    if raw is None or raw == "":
        return None
    lowered = raw.strip().lower()
    if lowered in {"true", "1", "yes", "y"}:
        return True
    if lowered in {"false", "0", "no", "n"}:
        return False
    raise ValueError(f"value '{raw}' is not a valid boolean")


def _build_filter(params: Dict[str, str], *, scope_user_id: Optional[str]) -> Optional[str]:
    """Build an OData filter for the ClaimedNames table.

    Owner scoping is mandatory for non-admin callers and is applied here when
    `scope_user_id` is provided. Passing scope_user_id=None means the caller
    is admin and may see every claim.
    """
    filters: List[str] = []

    if scope_user_id:
        filters.append(f"ClaimedBy eq '{_escape(scope_user_id.lower())}'")

    region = params.get("region")
    if region:
        environment = params.get("environment")
        if environment:
            partition_key = f"{_escape(region.lower())}-{_escape(environment.lower())}"
            filters.append(f"PartitionKey eq '{partition_key}'")
        else:
            filters.append(f"PartitionKey ge '{_escape(region.lower())}-' and PartitionKey lt '{_escape(region.lower())}-~'")
    elif params.get("environment"):
        environment = params.get("environment", "").lower()
        # No simple OData index for env-only when partition is region-env;
        # rely on post-filter for env-only queries.

    resource_type = params.get("resource_type")
    if resource_type:
        filters.append(f"ResourceType eq '{_escape(resource_type.lower())}'")

    project = params.get("project")
    if project:
        filters.append(f"Project eq '{_escape(project.lower())}'")

    state = params.get("state")
    if state:
        filters.append(f"ClaimState eq '{_escape(state.lower())}'")

    in_use = _parse_bool(params.get("in_use"))
    if in_use is not None:
        filters.append(f"InUse eq {'true' if in_use else 'false'}")

    return " and ".join(filters) if filters else None


def _matches_query(claim: Dict[str, Any], query: str) -> bool:
    needle = query.strip().lower()
    if not needle:
        return True
    haystacks: Iterable[Any] = (
        claim.get("name"),
        claim.get("resource_type"),
        claim.get("project"),
        claim.get("purpose"),
        claim.get("subsystem"),
        claim.get("system"),
        claim.get("claimed_by"),
        claim.get("slug"),
    )
    for value in haystacks:
        if value and needle in str(value).lower():
            return True
    return False


@app.function_name(name="list_claims")
@app.route(route="claims", methods=[func.HttpMethod.GET])
@openapi_doc(
    summary="List claimed names with optional filters and pagination",
    description=(
        "Returns a paginated list of claimed names. Non-admin callers are "
        "automatically scoped to their own claims. Admin callers see all "
        "claims and may pass `owner` to filter by another user. Supports "
        "filtering by region, environment, resource_type, project, state, "
        "in_use, and free-text query."
    ),
    tags=["Claims"],
    parameters=[
        {"name": "owner", "in": "query", "required": False, "schema": {"type": "string"}, "description": "Filter by claim owner. 'me' or omitted = caller; admin only may pass another user."},
        {"name": "region", "in": "query", "required": False, "schema": {"type": "string"}},
        {"name": "environment", "in": "query", "required": False, "schema": {"type": "string"}},
        {"name": "resource_type", "in": "query", "required": False, "schema": {"type": "string"}},
        {"name": "project", "in": "query", "required": False, "schema": {"type": "string"}},
        {"name": "state", "in": "query", "required": False, "schema": {"type": "string", "enum": ["claimed", "released", "orphaned"]}},
        {"name": "in_use", "in": "query", "required": False, "schema": {"type": "boolean"}},
        {"name": "query", "in": "query", "required": False, "schema": {"type": "string"}, "description": "Free-text substring search across name, resource_type, project, purpose, owner, slug."},
        {"name": "limit", "in": "query", "required": False, "schema": {"type": "integer", "default": _DEFAULT_PAGE_SIZE, "maximum": _MAX_PAGE_SIZE}},
        {"name": "continuation", "in": "query", "required": False, "schema": {"type": "string"}, "description": "Opaque continuation token from a previous response."},
    ],
    operation_id="listClaims",
    route="/claims",
    method="get",
)
def list_claims(req: func.HttpRequest) -> func.HttpResponse:
    """List claimed names with filtering and pagination."""

    logging.info("[list_claims] Processing list request with RBAC.")

    try:
        user_id, user_roles = require_role(req.headers, min_role="reader")
    except AuthError as exc:
        return func.HttpResponse(str(exc), status_code=exc.status)

    is_admin = bool(ELEVATED_ROLES.intersection(user_roles))

    params: Dict[str, str] = {k: v for k, v in req.params.items()}

    requested_owner = (params.get("owner") or "").strip().lower()
    if requested_owner in {"", "me"}:
        scope_user_id: Optional[str] = user_id.lower()
    elif is_admin:
        scope_user_id = None if requested_owner == "all" else requested_owner
    else:
        return func.HttpResponse("Forbidden: only admins may list other users' claims.", status_code=403)

    try:
        limit = _parse_int(params.get("limit"), default=_DEFAULT_PAGE_SIZE, minimum=1, maximum=_MAX_PAGE_SIZE)
    except ValueError as exc:
        return func.HttpResponse(f"Invalid limit: {exc}", status_code=400)

    try:
        filter_query = _build_filter(params, scope_user_id=scope_user_id)
    except ValueError as exc:
        return func.HttpResponse(f"Invalid filter: {exc}", status_code=400)

    free_text = params.get("query") or ""

    try:
        table = get_table_client(NAMES_TABLE_NAME)
        if filter_query:
            entities = table.query_entities(query_filter=filter_query, results_per_page=limit)
        else:
            entities = table.list_entities(results_per_page=limit)
    except Exception:  # pragma: no cover - centralised in table client
        logging.exception("[list_claims] Failed to query ClaimedNames table.")
        return func.HttpResponse("Error listing claims.", status_code=500)

    items: List[Dict[str, Any]] = []
    continuation_token: Optional[str] = None
    try:
        page_iter = entities.by_page(continuation_token=params.get("continuation") or None)
        page = next(page_iter, None)
        if page is not None:
            for entity in page:
                claim = _entity_to_claim(entity)
                if free_text and not _matches_query(claim, free_text):
                    continue
                items.append(claim)
                if len(items) >= limit:
                    break
            continuation_token = getattr(entities, "continuation_token", None)
    except StopIteration:
        continuation_token = None
    except Exception:  # pragma: no cover - safety net
        logging.exception("[list_claims] Failed iterating claims pages.")
        return func.HttpResponse("Error iterating claims.", status_code=500)

    payload: Dict[str, Any] = {
        "items": items,
        "count": len(items),
        "scope": "all" if scope_user_id is None else scope_user_id,
        "is_admin": is_admin,
    }
    if continuation_token:
        payload["continuation"] = continuation_token

    return json_payload(payload)
