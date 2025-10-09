"""Routes serving OpenAPI metadata and Swagger UI."""

from __future__ import annotations

import azure.functions as func
from azure_functions_openapi.openapi import get_openapi_json
from azure_functions_openapi.swagger_ui import render_swagger_ui

from app import app
from app.constants import API_TITLE, API_VERSION
from app.dependencies import AuthError, require_role


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
