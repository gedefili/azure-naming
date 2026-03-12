"""Tests for app.errors and app.responses modules."""

from __future__ import annotations

import json
import pathlib
import sys
from dataclasses import dataclass

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.errors import handle_name_generation_error
from app.responses import build_claim_response, json_message, json_payload
from core.name_service import InvalidRequestError, NameConflictError, NameGenerationResult


# ---------------------------------------------------------------------------
# handle_name_generation_error
# ---------------------------------------------------------------------------

class TestHandleNameGenerationError:
    def test_invalid_request_error(self):
        exc = InvalidRequestError("missing field")
        resp = handle_name_generation_error(exc, log_prefix="test")
        assert resp.status_code == 400
        assert b"missing field" in resp.get_body()

    def test_name_conflict_error(self):
        exc = NameConflictError("name taken")
        resp = handle_name_generation_error(exc, log_prefix="test")
        assert resp.status_code == 409

    def test_value_error(self):
        exc = ValueError("validation failed")
        resp = handle_name_generation_error(exc, log_prefix="test")
        assert resp.status_code == 400

    def test_unexpected_error(self):
        exc = RuntimeError("boom")
        resp = handle_name_generation_error(exc, log_prefix="test")
        assert resp.status_code == 500
        body = json.loads(resp.get_body())
        assert body["message"] == "Error claiming name."


# ---------------------------------------------------------------------------
# build_claim_response
# ---------------------------------------------------------------------------

class TestBuildClaimResponse:
    def test_returns_201(self):
        result = NameGenerationResult(
            name="wus2devstvm01",
            slug="vm",
            resource_type="virtual_machine",
            region="wus2",
            environment="dev",
        )
        resp = build_claim_response(result, "user1")
        assert resp.status_code == 201
        body = json.loads(resp.get_body())
        assert body["claimedBy"] == "user1"
        assert body["name"] == "wus2devstvm01"
        assert "display" in body


# ---------------------------------------------------------------------------
# json_message
# ---------------------------------------------------------------------------

class TestJsonMessage:
    def test_returns_correct_status(self):
        resp = json_message("ok", status_code=200)
        assert resp.status_code == 200
        body = json.loads(resp.get_body())
        assert body["message"] == "ok"

    def test_error_status(self):
        resp = json_message("fail", status_code=500)
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# json_payload
# ---------------------------------------------------------------------------

class TestJsonPayload:
    def test_default_status(self):
        resp = json_payload({"key": "val"})
        assert resp.status_code == 200
        body = json.loads(resp.get_body())
        assert body["key"] == "val"

    def test_custom_status(self):
        resp = json_payload({"a": 1}, status_code=201)
        assert resp.status_code == 201
