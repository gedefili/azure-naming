"""Routes serving OpenAPI metadata and Swagger UI."""

from __future__ import annotations

import json
from typing import Any

import azure.functions as func
from azure_functions_openapi.openapi import get_openapi_json
from azure_functions_openapi.swagger_ui import render_swagger_ui

from app import app
from app.constants import API_TITLE, API_VERSION
from app.dependencies import AuthError, require_role


def _hoist_defs(node: Any, components: dict[str, Any]) -> None:
    if isinstance(node, dict):
        defs = node.pop("$defs", None)
        if defs:
            for name, schema in defs.items():
                components.setdefault(name, schema)
        for key, value in node.items():
            if key == "$ref" and isinstance(value, str) and value.startswith("#/$defs/"):
                node[key] = value.replace("#/$defs/", "#/components/schemas/")
            else:
                _hoist_defs(value, components)
    elif isinstance(node, list):
        for item in node:
            _hoist_defs(item, components)


def _normalise_openapi_spec(raw_json: str) -> str:
    spec = json.loads(raw_json)
    components = spec.setdefault("components", {}).setdefault("schemas", {})
    _hoist_defs(spec, components)
    servers = spec.setdefault("servers", [])
    if not any(server.get("url") == "/api" for server in servers):
        # Use a relative server URL so the Swagger UI issues requests with the Azure Functions route prefix.
        servers.append({"url": "/api"})
    return json.dumps(spec)


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
    normalised = _normalise_openapi_spec(spec_json)
    return func.HttpResponse(normalised, mimetype="application/json", status_code=200)


@app.function_name(name="swagger_ui")
@app.route(route="docs", methods=[func.HttpMethod.GET], auth_level=func.AuthLevel.ANONYMOUS)
def swagger_ui(req: func.HttpRequest) -> func.HttpResponse:
    """Serve an interactive Swagger UI backed by the generated OpenAPI spec."""

    try:
        require_role(req.headers, min_role="reader")
    except AuthError as exc:
        return func.HttpResponse(str(exc), status_code=exc.status)
    return render_swagger_ui(title=f"{API_TITLE} – Swagger", openapi_url="/api/openapi.json")
