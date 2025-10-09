"""Helper utilities for building HTTP responses."""

from __future__ import annotations

import json
from typing import Mapping

import azure.functions as func

from utils.name_service import NameGenerationResult


def build_claim_response(result: NameGenerationResult, user_id: str) -> func.HttpResponse:
    body = result.to_dict()
    body["claimedBy"] = user_id
    body.setdefault("display", [])
    return func.HttpResponse(
        json.dumps(body),
        mimetype="application/json",
        status_code=201,
    )


def json_message(message: str, *, status_code: int) -> func.HttpResponse:
    return func.HttpResponse(
        json.dumps({"message": message}),
        mimetype="application/json",
        status_code=status_code,
    )


def json_payload(payload: Mapping[str, object], *, status_code: int = 200) -> func.HttpResponse:
    return func.HttpResponse(
        json.dumps(payload),
        mimetype="application/json",
        status_code=status_code,
    )
