# File: sanmar_naming/audit_bulk/__init__.py
# Version: 1.2.0
# Last Modified: 2025-07-24
# Authors: ChatGPT & Geoff DeFilippi
# Summary: Provides filtered bulk audit access for name history.

import json
import logging
from datetime import datetime
from typing import List

import azure.functions as func

from utils.auth import AuthError, require_role
from utils.storage import get_table_client

AUDIT_TABLE_NAME = "AuditLogs"
_ELEVATED_ROLES = {"manager", "admin"}


def _escape(value: str) -> str:
    return value.replace("'", "''")


def _build_filter(params: dict) -> str:
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


def main(req: func.HttpRequest) -> func.HttpResponse:
    """List audit information with optional filters."""

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

    # Sort newest first based on EventTime if present
    entities.sort(key=lambda e: e.get("EventTime") or datetime.min, reverse=True)

    records = []
    for entity in entities:
        records.append(
            {
                "name": entity.get("PartitionKey"),
                "event_id": entity.get("RowKey"),
                "user": entity.get("User"),
                "action": entity.get("Action"),
                "note": entity.get("Note"),
                "timestamp": (entity.get("EventTime") or datetime.min).isoformat(),
                "region": entity.get("Region"),
                "environment": entity.get("Environment"),
                "project": entity.get("Project"),
                "purpose": entity.get("Purpose"),
                "resource_type": entity.get("ResourceType"),
            }
        )

    return func.HttpResponse(json.dumps({"results": records}), status_code=200, mimetype="application/json")
