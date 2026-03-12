"""Tests for app.routes.rules module."""

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

from app.routes import rules as rules_routes


def _fn(builder):
    """Extract the user function from an Azure Functions FunctionBuilder."""
    return builder._function.get_user_function()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _auth_error(msg="Auth failed", status=401):
    from app.dependencies import AuthError
    return AuthError(msg, status=status)


def _make_request(params=None, headers=None, route_params=None):
    req = SimpleNamespace(
        params=params or {},
        headers=headers or {},
        route_params=route_params or {},
    )
    return req


# ---------------------------------------------------------------------------
# list_naming_rules
# ---------------------------------------------------------------------------

class TestListNamingRules:
    def test_auth_error(self, monkeypatch):
        monkeypatch.setattr(rules_routes, "require_role", mock.Mock(side_effect=_auth_error()))
        resp = _fn(rules_routes.list_naming_rules)(_make_request())
        assert resp.status_code == 401

    def test_basic_list(self, monkeypatch):
        monkeypatch.setattr(rules_routes, "require_role", lambda h, min_role: ("u1", ["reader"]))
        monkeypatch.setattr(rules_routes.naming_rules, "list_resource_types", lambda: ["vm", "st"])
        resp = _fn(rules_routes.list_naming_rules)(_make_request())
        assert resp.status_code == 200
        body = json.loads(resp.get_body())
        assert body["resourceTypes"] == ["vm", "st"]

    def test_expanded_list(self, monkeypatch):
        monkeypatch.setattr(rules_routes, "require_role", lambda h, min_role: ("u1", ["reader"]))
        monkeypatch.setattr(rules_routes.naming_rules, "list_resource_types", lambda: ["vm"])
        monkeypatch.setattr(rules_routes.naming_rules, "describe_rule", lambda rt: {"type": rt, "max_length": 50})
        resp = _fn(rules_routes.list_naming_rules)(_make_request(params={"expand": "details"}))
        assert resp.status_code == 200
        body = json.loads(resp.get_body())
        assert len(body["rules"]) == 1
        assert body["rules"][0]["type"] == "vm"

    def test_full_expand(self, monkeypatch):
        monkeypatch.setattr(rules_routes, "require_role", lambda h, min_role: ("u1", ["reader"]))
        monkeypatch.setattr(rules_routes.naming_rules, "list_resource_types", lambda: ["vm"])
        monkeypatch.setattr(rules_routes.naming_rules, "describe_rule", lambda rt: {"type": rt})
        resp = _fn(rules_routes.list_naming_rules)(_make_request(params={"expand": "full"}))
        assert resp.status_code == 200
        body = json.loads(resp.get_body())
        assert "rules" in body


# ---------------------------------------------------------------------------
# get_naming_rule
# ---------------------------------------------------------------------------

class TestGetNamingRule:
    def test_auth_error(self, monkeypatch):
        monkeypatch.setattr(rules_routes, "require_role", mock.Mock(side_effect=_auth_error()))
        resp = _fn(rules_routes.get_naming_rule)(_make_request(route_params={"resource_type": "vm"}))
        assert resp.status_code == 401

    def test_missing_resource_type(self, monkeypatch):
        monkeypatch.setattr(rules_routes, "require_role", lambda h, min_role: ("u1", ["reader"]))
        resp = _fn(rules_routes.get_naming_rule)(_make_request(route_params={"resource_type": ""}))
        assert resp.status_code == 400

    def test_not_found(self, monkeypatch):
        monkeypatch.setattr(rules_routes, "require_role", lambda h, min_role: ("u1", ["reader"]))
        monkeypatch.setattr(rules_routes.naming_rules, "describe_rule", mock.Mock(side_effect=KeyError("unknown")))
        resp = _fn(rules_routes.get_naming_rule)(_make_request(route_params={"resource_type": "unknown"}))
        assert resp.status_code == 404

    def test_success(self, monkeypatch):
        monkeypatch.setattr(rules_routes, "require_role", lambda h, min_role: ("u1", ["reader"]))
        monkeypatch.setattr(rules_routes.naming_rules, "describe_rule", lambda rt: {"type": rt, "max": 50})
        resp = _fn(rules_routes.get_naming_rule)(_make_request(route_params={"resource_type": "vm"}))
        assert resp.status_code == 200
        body = json.loads(resp.get_body())
        assert body["type"] == "vm"
