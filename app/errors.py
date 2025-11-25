"""Shared error helpers for HTTP routes."""

from __future__ import annotations

import logging

import azure.functions as func

from .responses import json_message
from .dependencies import InvalidRequestError, NameConflictError


def handle_name_generation_error(exc: Exception, *, log_prefix: str) -> func.HttpResponse:
    if isinstance(exc, InvalidRequestError):
        return func.HttpResponse(str(exc), status_code=400)
    if isinstance(exc, NameConflictError):
        return func.HttpResponse(str(exc), status_code=409)
    if isinstance(exc, ValueError):
        # Validation errors (e.g., name too long, invalid characters, etc.)
        return func.HttpResponse(str(exc), status_code=400)

    logging.exception("[%s] Unexpected error", log_prefix)
    return json_message("Error claiming name.", status_code=500)
