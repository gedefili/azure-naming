"""Tests for app.routes.audit module."""

from __future__ import annotations

import json
import pathlib
import sys
from datetime import datetime
from types import SimpleNamespace
from unittest import mock

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.routes import audit as audit_routes
from app.routes.audit import (
    _build_filter,
    _escape,
    _query_audit_entities,
    _validate_datetime,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class FakeAuditTable:
    def __init__(self, entities=None, raise_on_get=None):
        self.query_kwargs = None
        self.list_called = False
        self._entities = entities or {}
        self._raise_on_get = raise_on_get

    def get_entity(self, partition_key, row_key):
        if self._raise_on_get:
            raise self._raise_on_get
        key = (partition_key, row_key)
        if key not in self._entities:
            from app.dependencies import ResourceNotFoundError
            raise ResourceNotFoundError("not found")
        return dict(self._entities[key])

    def query_entities(self, **kwargs):
        self.query_kwargs = kwargs
        yield from self._entities.values()

    def list_entities(self):
        self.list_called = True
        yield from self._entities.values()


def _make_auth_error(msg="Auth failed", status=401):
    from app.dependencies import AuthError
    return AuthError(msg, status=status)


# ---------------------------------------------------------------------------
# Original tests (preserved)
# ---------------------------------------------------------------------------

def test_query_audit_entities_prefers_query_filter():
    table = FakeAuditTable()
    list(_query_audit_entities(table, "User eq 'someone'"))
    assert table.query_kwargs == {"query_filter": "User eq 'someone'"}
    assert table.list_called is False


def test_query_audit_entities_falls_back_to_list():
    table = FakeAuditTable()
    list(_query_audit_entities(table, ""))
    assert table.query_kwargs is None
    assert table.list_called is True


# ---------------------------------------------------------------------------
# _escape
# ---------------------------------------------------------------------------

class TestEscape:
    def test_basic(self):
        assert _escape("hello") == "hello"

    def test_single_quote(self):
        assert _escape("it's") == "it''s"


# ---------------------------------------------------------------------------
# _validate_datetime
# ---------------------------------------------------------------------------

class TestValidateDatetime:
    def test_valid_iso(self):
        result = _validate_datetime("2025-01-15T10:30:00")
        assert "2025-01-15" in result

    def test_valid_with_z(self):
        result = _validate_datetime("2025-01-15T10:30:00Z")
        assert "2025-01-15" in result

    def test_empty(self):
        with pytest.raises(ValueError, match="empty"):
            _validate_datetime("")

    def test_invalid(self):
        with pytest.raises(ValueError, match="ISO 8601"):
            _validate_datetime("not-a-date")


# ---------------------------------------------------------------------------
# _build_filter
# ---------------------------------------------------------------------------

class TestBuildFilter:
    def test_empty_params(self):
        assert _build_filter({}) == ""

    def test_user_filter(self):
        result = _build_filter({"user": "Alice"})
        assert "User eq 'alice'" in result

    def test_multiple_filters(self):
        result = _build_filter({"user": "alice", "action": "claimed"})
        assert " and " in result

    def test_all_simple_filters(self):
        params = {
            "user": "u1", "project": "p1", "purpose": "test",
            "region": "wus2", "environment": "dev", "action": "claimed",
        }
        result = _build_filter(params)
        assert result.count(" and ") == 5

    def test_start_datetime(self):
        result = _build_filter({"start": "2025-01-01T00:00:00Z"})
        assert "EventTime ge datetime'" in result

    def test_end_datetime(self):
        result = _build_filter({"end": "2025-12-31T23:59:59Z"})
        assert "EventTime le datetime'" in result

    def test_invalid_start(self):
        with pytest.raises(ValueError, match="start datetime"):
            _build_filter({"start": "bad"})

    def test_invalid_end(self):
        with pytest.raises(ValueError, match="end datetime"):
            _build_filter({"end": "bad"})


# ---------------------------------------------------------------------------
# audit_name
# ---------------------------------------------------------------------------

class TestAuditName:
    def _make_request(self, params=None, headers=None):
        return SimpleNamespace(params=params or {}, headers=headers or {})

    def test_auth_error(self, monkeypatch):
        monkeypatch.setattr(audit_routes, "require_role", mock.Mock(side_effect=_make_auth_error()))
        req = self._make_request(params={"region": "wus2", "environment": "dev", "name": "x"})
        resp = audit_routes.audit_name(req)
        assert resp.status_code == 401

    def test_missing_params(self, monkeypatch):
        monkeypatch.setattr(audit_routes, "require_role", lambda h, min_role: ("u1", ["reader"]))
        resp = audit_routes.audit_name(self._make_request(params={}))
        assert resp.status_code == 400

    def test_not_found(self, monkeypatch):
        from app.dependencies import ResourceNotFoundError
        monkeypatch.setattr(audit_routes, "require_role", lambda h, min_role: ("u1", ["reader"]))
        monkeypatch.setattr(audit_routes, "get_table_client", mock.Mock(side_effect=ResourceNotFoundError("nope")))
        req = self._make_request(params={"region": "wus2", "environment": "dev", "name": "gone"})
        resp = audit_routes.audit_name(req)
        assert resp.status_code == 404

    def test_storage_error(self, monkeypatch):
        monkeypatch.setattr(audit_routes, "require_role", lambda h, min_role: ("u1", ["reader"]))
        monkeypatch.setattr(audit_routes, "get_table_client", mock.Mock(side_effect=RuntimeError("boom")))
        req = self._make_request(params={"region": "wus2", "environment": "dev", "name": "x"})
        resp = audit_routes.audit_name(req)
        assert resp.status_code == 500

    def test_forbidden(self, monkeypatch):
        entity = {
            "PartitionKey": "wus2-dev", "RowKey": "res",
            "ClaimedBy": "other", "ReleasedBy": "",
            "ResourceType": "vm", "InUse": True,
        }
        table = FakeAuditTable({("wus2-dev", "res"): entity})
        monkeypatch.setattr(audit_routes, "require_role", lambda h, min_role: ("u1", ["reader"]))
        monkeypatch.setattr(audit_routes, "get_table_client", lambda name: table)
        monkeypatch.setattr(audit_routes, "is_authorized", lambda roles, uid, cb, rb: False)
        req = self._make_request(params={"region": "wus2", "environment": "dev", "name": "res"})
        resp = audit_routes.audit_name(req)
        assert resp.status_code == 403

    def test_success(self, monkeypatch):
        entity = {
            "PartitionKey": "wus2-dev", "RowKey": "res",
            "ClaimedBy": "u1", "ReleasedBy": "",
            "ResourceType": "vm", "InUse": True,
            "ClaimedAt": "2025-01-01", "ReleasedAt": None,
            "ReleaseReason": None, "Slug": "vm",
            "Project": "proj1", "Purpose": "test",
            "Subsystem": None, "System": None, "Index": None,
            "CustomField": "custom_value",
        }
        table = FakeAuditTable({("wus2-dev", "res"): entity})
        monkeypatch.setattr(audit_routes, "require_role", lambda h, min_role: ("u1", ["admin"]))
        monkeypatch.setattr(audit_routes, "get_table_client", lambda name: table)
        monkeypatch.setattr(audit_routes, "is_authorized", lambda roles, uid, cb, rb: True)
        req = self._make_request(params={"region": "wus2", "environment": "dev", "name": "res"})
        resp = audit_routes.audit_name(req)
        assert resp.status_code == 200
        body = json.loads(resp.get_body())
        assert body["name"] == "res"
        assert body["resource_type"] == "vm"
        assert "custom_field" in body


# ---------------------------------------------------------------------------
# audit_bulk
# ---------------------------------------------------------------------------

class TestAuditBulk:
    def _make_request(self, params=None, headers=None):
        return SimpleNamespace(params=params or {}, headers=headers or {})

    def test_auth_error(self, monkeypatch):
        monkeypatch.setattr(audit_routes, "require_role", mock.Mock(side_effect=_make_auth_error()))
        resp = audit_routes.audit_bulk(self._make_request())
        assert resp.status_code == 401

    def test_forbidden_non_elevated(self, monkeypatch):
        monkeypatch.setattr(audit_routes, "require_role", lambda h, min_role: ("u1", ["reader"]))
        resp = audit_routes.audit_bulk(self._make_request(params={"user": "other"}))
        assert resp.status_code == 403

    def test_elevated_can_query_other_users(self, monkeypatch):
        monkeypatch.setattr(audit_routes, "require_role", lambda h, min_role: ("u1", ["admin"]))
        monkeypatch.setattr(audit_routes, "get_table_client", lambda name: FakeAuditTable())
        resp = audit_routes.audit_bulk(self._make_request(params={"user": "other"}))
        assert resp.status_code == 200

    def test_self_query_allowed(self, monkeypatch):
        monkeypatch.setattr(audit_routes, "require_role", lambda h, min_role: ("alice", ["reader"]))
        monkeypatch.setattr(audit_routes, "get_table_client", lambda name: FakeAuditTable())
        resp = audit_routes.audit_bulk(self._make_request(params={"user": "alice"}))
        assert resp.status_code == 200

    def test_storage_error(self, monkeypatch):
        monkeypatch.setattr(audit_routes, "require_role", lambda h, min_role: ("u1", ["admin"]))
        monkeypatch.setattr(audit_routes, "get_table_client", mock.Mock(side_effect=RuntimeError("boom")))
        resp = audit_routes.audit_bulk(self._make_request(params={"user": "u1"}))
        assert resp.status_code == 500

    def test_success_with_entities(self, monkeypatch):
        entities = {
            ("name1", "row1"): {
                "PartitionKey": "name1", "RowKey": "row1",
                "User": "alice", "Action": "claimed", "Note": "",
                "EventTime": datetime(2025, 1, 15, 10, 0, 0),
            },
        }
        table = FakeAuditTable(entities)
        monkeypatch.setattr(audit_routes, "require_role", lambda h, min_role: ("alice", ["reader"]))
        monkeypatch.setattr(audit_routes, "get_table_client", lambda name: table)
        resp = audit_routes.audit_bulk(self._make_request(params={"user": "alice"}))
        assert resp.status_code == 200
        body = json.loads(resp.get_body())
        assert len(body["results"]) == 1
        assert body["results"][0]["user"] == "alice"

    def test_event_time_string(self, monkeypatch):
        entities = {
            ("n", "r"): {
                "PartitionKey": "n", "RowKey": "r",
                "User": "u1", "Action": "claimed", "Note": "",
                "EventTime": "2025-01-01T00:00:00",
            },
        }
        table = FakeAuditTable(entities)
        monkeypatch.setattr(audit_routes, "require_role", lambda h, min_role: ("u1", ["admin"]))
        monkeypatch.setattr(audit_routes, "get_table_client", lambda name: table)
        resp = audit_routes.audit_bulk(self._make_request(params={"user": "u1"}))
        assert resp.status_code == 200
        body = json.loads(resp.get_body())
        assert body["results"][0]["timestamp"] == "2025-01-01T00:00:00"
