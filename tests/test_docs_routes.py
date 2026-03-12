"""Tests for app.routes.docs module."""

from __future__ import annotations

import json
import pathlib
import sys
from types import SimpleNamespace
from unittest import mock

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.routes import docs as docs_routes
from app.routes.docs import _hoist_defs, _normalise_openapi_spec


def _fn(builder):
    """Extract the user function from an Azure Functions FunctionBuilder."""
    return builder._function.get_user_function()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _auth_error(msg="Auth failed", status=401):
    from app.dependencies import AuthError
    return AuthError(msg, status=status)


def _make_request(params=None, headers=None):
    return SimpleNamespace(params=params or {}, headers=headers or {})


# ---------------------------------------------------------------------------
# _hoist_defs
# ---------------------------------------------------------------------------

class TestHoistDefs:
    def test_no_defs(self):
        node = {"properties": {"a": {"type": "string"}}}
        components: dict = {}
        _hoist_defs(node, components)
        assert components == {}

    def test_defs_moved_to_components(self):
        node = {
            "$defs": {"MyModel": {"type": "object"}},
            "properties": {"item": {"$ref": "#/$defs/MyModel"}},
        }
        components: dict = {}
        _hoist_defs(node, components)
        assert "MyModel" in components
        assert node["properties"]["item"]["$ref"] == "#/components/schemas/MyModel"

    def test_nested_list(self):
        node = [{"$defs": {"X": {"type": "string"}}, "items": {"$ref": "#/$defs/X"}}]
        components: dict = {}
        _hoist_defs(node, components)
        assert "X" in components


# ---------------------------------------------------------------------------
# _normalise_openapi_spec
# ---------------------------------------------------------------------------

class TestNormaliseOpenapiSpec:
    def test_adds_server_url(self):
        raw = json.dumps({"openapi": "3.0.0", "paths": {}})
        result = json.loads(_normalise_openapi_spec(raw))
        assert {"url": "/api"} in result["servers"]

    def test_does_not_duplicate_server_url(self):
        raw = json.dumps({"openapi": "3.0.0", "paths": {}, "servers": [{"url": "/api"}]})
        result = json.loads(_normalise_openapi_spec(raw))
        count = sum(1 for s in result["servers"] if s.get("url") == "/api")
        assert count == 1


# ---------------------------------------------------------------------------
# openapi_spec
# ---------------------------------------------------------------------------

class TestOpenapiSpec:
    def test_auth_error(self, monkeypatch):
        monkeypatch.setattr(docs_routes, "require_role", mock.Mock(side_effect=_auth_error()))
        resp = _fn(docs_routes.openapi_spec)(_make_request())
        assert resp.status_code == 401

    def test_success(self, monkeypatch):
        monkeypatch.setattr(docs_routes, "require_role", lambda h, min_role: ("u1", ["reader"]))
        fake_spec = json.dumps({"openapi": "3.0.0", "paths": {}})
        monkeypatch.setattr(docs_routes, "get_openapi_json", lambda title, version: fake_spec)
        resp = _fn(docs_routes.openapi_spec)(_make_request())
        assert resp.status_code == 200
        body = json.loads(resp.get_body())
        assert body["openapi"] == "3.0.0"


# ---------------------------------------------------------------------------
# swagger_ui
# ---------------------------------------------------------------------------

class TestSwaggerUi:
    def test_auth_error(self, monkeypatch):
        monkeypatch.setattr(docs_routes, "require_role", mock.Mock(side_effect=_auth_error()))
        resp = _fn(docs_routes.swagger_ui)(_make_request())
        assert resp.status_code == 401

    def test_success(self, monkeypatch):
        monkeypatch.setattr(docs_routes, "require_role", lambda h, min_role: ("u1", ["reader"]))
        monkeypatch.setattr(docs_routes, "render_swagger_ui", lambda title, openapi_url: SimpleNamespace(status_code=200, get_body=lambda: b"<html>"))
        resp = _fn(docs_routes.swagger_ui)(_make_request())
        assert resp.status_code == 200
