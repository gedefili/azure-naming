"""Tests for app.routes.names module."""

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

from app.routes import names as names_routes


def _fn(builder):
    """Extract the user function from an Azure Functions FunctionBuilder."""
    return builder._function.get_user_function()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _auth_error(msg="Auth failed", status=401):
    from app.dependencies import AuthError
    return AuthError(msg, status=status)


def _make_request(body=None, params=None, headers=None):
    class FakeReq:
        def __init__(self):
            self.params = params or {}
            self.headers = headers or {}
            self._body = body

        def get_json(self):
            if self._body is None:
                raise ValueError("No body")
            return self._body

    return FakeReq()


class FakeResult:
    def to_dict(self):
        return {"name": "wus2devstvm01", "slug": "vm"}


class FakeTable:
    def __init__(self, entities=None, raise_on_get=None, raise_on_update=None):
        self._entities = entities or {}
        self._raise_on_get = raise_on_get
        self._raise_on_update = raise_on_update
        self.updated = None

    def get_entity(self, partition_key, row_key):
        if self._raise_on_get:
            raise self._raise_on_get
        key = (partition_key, row_key)
        if key not in self._entities:
            raise RuntimeError("not found")
        return dict(self._entities[key])

    def update_entity(self, entity, mode=None, match_condition=None):
        if self._raise_on_update:
            raise self._raise_on_update
        self.updated = entity


# ---------------------------------------------------------------------------
# _handle_claim_request
# ---------------------------------------------------------------------------

class TestHandleClaimRequest:
    def test_auth_error(self, monkeypatch):
        monkeypatch.setattr(names_routes, "require_role", mock.Mock(side_effect=_auth_error()))
        resp = names_routes._handle_claim_request(_make_request(), log_prefix="test")
        assert resp.status_code == 401

    def test_invalid_json(self, monkeypatch):
        monkeypatch.setattr(names_routes, "require_role", lambda h, min_role: ("u1", ["contributor"]))
        resp = names_routes._handle_claim_request(_make_request(body=None), log_prefix="test")
        assert resp.status_code == 400

    def test_success(self, monkeypatch):
        monkeypatch.setattr(names_routes, "require_role", lambda h, min_role: ("u1", ["contributor"]))
        monkeypatch.setattr(names_routes, "generate_and_claim_name", lambda p, requested_by: FakeResult())
        monkeypatch.setattr(names_routes, "build_claim_response", lambda result, uid: SimpleNamespace(status_code=201))
        resp = names_routes._handle_claim_request(_make_request(body={"resource_type": "vm"}), log_prefix="test")
        assert resp.status_code == 201


# ---------------------------------------------------------------------------
# release_name
# ---------------------------------------------------------------------------

class TestReleaseName:
    def test_auth_error(self, monkeypatch):
        monkeypatch.setattr(names_routes, "require_role", mock.Mock(side_effect=_auth_error()))
        resp = _fn(names_routes.release_name)(_make_request(body={}))
        assert resp.status_code == 401

    def test_invalid_json(self, monkeypatch):
        monkeypatch.setattr(names_routes, "require_role", lambda h, min_role: ("u1", ["contributor"]))
        resp = _fn(names_routes.release_name)(_make_request(body=None))
        assert resp.status_code == 400

    def test_missing_name(self, monkeypatch):
        monkeypatch.setattr(names_routes, "require_role", lambda h, min_role: ("u1", ["contributor"]))
        resp = _fn(names_routes.release_name)(_make_request(body={"name": ""}))
        assert resp.status_code == 400

    def test_region_env_from_data(self, monkeypatch):
        entity = {
            "PartitionKey": "wus2-dev", "RowKey": "myresource",
            "ClaimedBy": "u1", "ReleasedBy": "", "InUse": True,
            "ResourceType": "vm", "Slug": "vm",
        }
        table = FakeTable({("wus2-dev", "myresource"): entity})
        monkeypatch.setattr(names_routes, "require_role", lambda h, min_role: ("u1", ["contributor"]))
        monkeypatch.setattr(names_routes, "get_table_client", lambda name: table)
        monkeypatch.setattr(names_routes, "is_authorized", lambda roles, uid, cb, rb: True)
        monkeypatch.setattr(names_routes, "write_audit_log", lambda *a, **kw: None)
        resp = _fn(names_routes.release_name)(_make_request(body={"name": "myresource", "region": "wus2", "environment": "dev"}))
        assert resp.status_code == 200
        assert table.updated is not None

    def test_region_env_extracted_from_name(self, monkeypatch):
        entity = {
            "PartitionKey": "wus2-prd", "RowKey": "wus2prdvm01",
            "ClaimedBy": "u1", "ReleasedBy": "", "InUse": True,
            "ResourceType": "vm", "Slug": "vm",
        }
        table = FakeTable({("wus2-prd", "wus2prdvm01"): entity})
        monkeypatch.setattr(names_routes, "require_role", lambda h, min_role: ("u1", ["contributor"]))
        monkeypatch.setattr(names_routes, "get_table_client", lambda name: table)
        monkeypatch.setattr(names_routes, "is_authorized", lambda roles, uid, cb, rb: True)
        monkeypatch.setattr(names_routes, "write_audit_log", lambda *a, **kw: None)
        resp = _fn(names_routes.release_name)(_make_request(body={"name": "wus2prdvm01"}))
        assert resp.status_code == 200

    def test_cannot_determine_partition(self, monkeypatch):
        monkeypatch.setattr(names_routes, "require_role", lambda h, min_role: ("u1", ["contributor"]))
        resp = _fn(names_routes.release_name)(_make_request(body={"name": "unknownformat"}))
        assert resp.status_code == 400

    def test_not_found(self, monkeypatch):
        monkeypatch.setattr(names_routes, "require_role", lambda h, min_role: ("u1", ["contributor"]))
        monkeypatch.setattr(names_routes, "get_table_client", lambda name: FakeTable(raise_on_get=RuntimeError("nope")))
        resp = _fn(names_routes.release_name)(_make_request(body={"name": "myname", "region": "wus2", "environment": "dev"}))
        assert resp.status_code == 404

    def test_forbidden(self, monkeypatch):
        entity = {
            "PartitionKey": "wus2-dev", "RowKey": "myname",
            "ClaimedBy": "other", "ReleasedBy": "", "InUse": True,
        }
        table = FakeTable({("wus2-dev", "myname"): entity})
        monkeypatch.setattr(names_routes, "require_role", lambda h, min_role: ("u1", ["reader"]))
        monkeypatch.setattr(names_routes, "get_table_client", lambda name: table)
        monkeypatch.setattr(names_routes, "is_authorized", lambda roles, uid, cb, rb: False)
        resp = _fn(names_routes.release_name)(_make_request(body={"name": "myname", "region": "wus2", "environment": "dev"}))
        assert resp.status_code == 403

    def test_concurrent_conflict(self, monkeypatch):
        from azure.core.exceptions import ResourceModifiedError
        entity = {
            "PartitionKey": "wus2-dev", "RowKey": "myname",
            "ClaimedBy": "u1", "ReleasedBy": "", "InUse": True,
        }
        table = FakeTable(
            {("wus2-dev", "myname"): entity},
            raise_on_update=ResourceModifiedError("conflict"),
        )
        monkeypatch.setattr(names_routes, "require_role", lambda h, min_role: ("u1", ["contributor"]))
        monkeypatch.setattr(names_routes, "get_table_client", lambda name: table)
        monkeypatch.setattr(names_routes, "is_authorized", lambda roles, uid, cb, rb: True)
        resp = _fn(names_routes.release_name)(_make_request(body={"name": "myname", "region": "wus2", "environment": "dev"}))
        assert resp.status_code == 409

    def test_update_error(self, monkeypatch):
        entity = {
            "PartitionKey": "wus2-dev", "RowKey": "myname",
            "ClaimedBy": "u1", "ReleasedBy": "", "InUse": True,
        }
        table = FakeTable(
            {("wus2-dev", "myname"): entity},
            raise_on_update=Exception("storage error"),
        )
        monkeypatch.setattr(names_routes, "require_role", lambda h, min_role: ("u1", ["contributor"]))
        monkeypatch.setattr(names_routes, "get_table_client", lambda name: table)
        monkeypatch.setattr(names_routes, "is_authorized", lambda roles, uid, cb, rb: True)
        resp = _fn(names_routes.release_name)(_make_request(body={"name": "myname", "region": "wus2", "environment": "dev"}))
        assert resp.status_code == 500

    def test_custom_metadata_in_audit(self, monkeypatch):
        entity = {
            "PartitionKey": "wus2-dev", "RowKey": "myname",
            "ClaimedBy": "u1", "ReleasedBy": "", "InUse": True,
            "ResourceType": "vm", "Slug": "vm", "Project": "proj",
            "CustomField": "val",
        }
        table = FakeTable({("wus2-dev", "myname"): entity})
        captured = {}
        def capture_audit(*a, **kw):
            captured["metadata"] = kw.get("metadata")
        monkeypatch.setattr(names_routes, "require_role", lambda h, min_role: ("u1", ["contributor"]))
        monkeypatch.setattr(names_routes, "get_table_client", lambda name: table)
        monkeypatch.setattr(names_routes, "is_authorized", lambda roles, uid, cb, rb: True)
        monkeypatch.setattr(names_routes, "write_audit_log", capture_audit)
        resp = _fn(names_routes.release_name)(_make_request(body={"name": "myname", "region": "wus2", "environment": "dev"}))
        assert resp.status_code == 200
        assert "CustomField" in captured["metadata"]
