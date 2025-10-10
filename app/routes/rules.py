"""Routes exposing naming rule specifications as JSON."""

from __future__ import annotations

import azure.functions as func
from azure_functions_openapi.decorator import openapi as openapi_doc

from app import app
from app.dependencies import AuthError, require_role
from app.responses import json_payload
from core import naming_rules


@app.function_name(name="list_naming_rules")
@app.route(route="rules", methods=[func.HttpMethod.GET], auth_level=func.AuthLevel.ANONYMOUS)
@openapi_doc(
    summary="List available naming rules",
    description="Returns the known resource types with explicitly defined naming rules.",
    tags=["Naming Rules"],
    operation_id="listNamingRules",
    route="/rules",
    method="get",
)
def list_naming_rules(req: func.HttpRequest) -> func.HttpResponse:
    """Return the collection of known naming rules."""

    try:
        require_role(req.headers, min_role="reader")
    except AuthError as exc:
        return func.HttpResponse(str(exc), status_code=exc.status)

    expand = (req.params.get("expand") or "").lower()
    resource_types = naming_rules.list_resource_types()

    if expand in {"details", "full"}:
        details = [naming_rules.describe_rule(resource_type) for resource_type in resource_types]
        return json_payload({"rules": details})

    return json_payload({"resourceTypes": resource_types})


@app.function_name(name="get_naming_rule")
@app.route(route="rules/{resource_type}", methods=[func.HttpMethod.GET], auth_level=func.AuthLevel.ANONYMOUS)
@openapi_doc(
    summary="Retrieve a naming rule specification",
    description="Returns the name template, display metadata, and segment mappings for a resource type.",
    tags=["Naming Rules"],
    operation_id="getNamingRule",
    route="/rules/{resource_type}",
    method="get",
)
def get_naming_rule(req: func.HttpRequest) -> func.HttpResponse:
    """Return the rule details for a single resource type."""

    try:
        require_role(req.headers, min_role="reader")
    except AuthError as exc:
        return func.HttpResponse(str(exc), status_code=exc.status)

    resource_type = (req.route_params.get("resource_type") or "").strip()
    if not resource_type:
        return func.HttpResponse("Resource type is required.", status_code=400)

    try:
        rule_description = naming_rules.describe_rule(resource_type)
    except KeyError as exc:
        return func.HttpResponse(str(exc), status_code=404)

    return json_payload(rule_description)
