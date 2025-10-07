# File: sanmar_naming/claim_name/__init__.py
# Version: 1.2.0
# Last Modified: 2025-07-24
# Authors: ChatGPT & Geoff DeFilippi
# Summary: Claims a unique Azure name, updates audit, and enforces Entra ID-based RBAC.

import json
import logging

import azure.functions as func

from utils.auth import AuthError, require_role
from utils.name_service import (
    InvalidRequestError,
    NameConflictError,
    generate_and_claim_name,
)


def main(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint to generate and claim a compliant name."""

    logging.info("[claim_name] Processing claim request with RBAC.")

    try:
        user_id, _ = require_role(req.headers, min_role="user")
    except AuthError as exc:
        return func.HttpResponse(str(exc), status_code=exc.status)

    try:
        payload = req.get_json()
    except ValueError:
        return func.HttpResponse("Invalid JSON payload.", status_code=400)

    try:
        result = generate_and_claim_name(payload, requested_by=user_id)
        response_body = result.to_dict()
        response_body["claimedBy"] = user_id
        return func.HttpResponse(
            json.dumps(response_body),
            mimetype="application/json",
            status_code=201,
        )
    except InvalidRequestError as exc:
        return func.HttpResponse(str(exc), status_code=400)
    except NameConflictError as exc:
        return func.HttpResponse(str(exc), status_code=409)
    except Exception:
        logging.exception("[claim_name] Failed to claim name.")
        return func.HttpResponse("Error claiming name.", status_code=500)
