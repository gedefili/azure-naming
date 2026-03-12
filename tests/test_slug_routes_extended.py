"""Extended tests for app.routes.slug module."""

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

from app.routes import slug as slug_routes


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


class FakeTable:
    def __init__(self, entities=None, raise_on_get=None):
        self._entities = entities or {}
        self._raise_on_get = raise_on_get
        self.upserted = []
        self.updated = []

    def get_entity(self, partition_key, row_key):
        if self._raise_on_get:
            raise self._raise_on_get
        key = (partition_key, row_key)
        if key not in self._entities:
            from azure.core.exceptions import ResourceNotFoundError
            raise ResourceNotFoundError("nope")
        return dict(self._entities[key])

    def query_entities(self, query_filter=None):
        return list(self._entities.values())

    def update_entity(self, entity, mode=None):
        self.updated.append(entity)

    def upsert_entity(self, entity, mode=None):
        self.upserted.append(entity)


# ---------------------------------------------------------------------------
# _handle_slug_lookup
# ---------------------------------------------------------------------------

class TestHandleSlugLookup:
    def test_auth_error(self, monkeypatch):
        monkeypatch.setattr(slug_routes, "require_role", mock.Mock(side_effect=_auth_error()))
        resp = slug_routes._handle_slug_lookup(_make_request(params={"resource_type": "vm"}))
        assert resp.status_code == 401

    def test_missing_resource_type(self, monkeypatch):
        monkeypatch.setattr(slug_routes, "require_role", lambda h, min_role: ("u1", ["reader"]))
        resp = slug_routes._handle_slug_lookup(_make_request(params={}))
        assert resp.status_code == 400

    def test_server_error(self, monkeypatch):
        monkeypatch.setattr(slug_routes, "require_role", lambda h, min_role: ("u1", ["reader"]))
        monkeypatch.setattr(slug_routes, "_resolve_slug_payload", mock.Mock(side_effect=RuntimeError("boom")))
        resp = slug_routes._handle_slug_lookup(_make_request(params={"resource_type": "vm"}))
        assert resp.status_code == 500

    def test_resourceType_param_alias(self, monkeypatch):
        monkeypatch.setattr(slug_routes, "require_role", lambda h, min_role: ("u1", ["reader"]))
        monkeypatch.setattr(slug_routes, "_resolve_slug_payload", lambda rt: {"slug": "vm", "resourceType": rt})
        resp = slug_routes._handle_slug_lookup(_make_request(params={"resourceType": "virtual_machine"}))
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# _resolve_slug_payload
# ---------------------------------------------------------------------------

class TestResolveSlugPayload:
    def test_empty_resource_type(self):
        with pytest.raises(ValueError, match="empty"):
            slug_routes._resolve_slug_payload("   ")

    def test_fallback_query(self, monkeypatch):
        from azure.core.exceptions import ResourceNotFoundError

        class FallbackTable:
            def get_entity(self, partition_key, row_key):
                raise ResourceNotFoundError("not direct")

            def query_entities(self, query_filter=None):
                return [{"ResourceType": "virtual_machine", "Source": "github"}]

        monkeypatch.setattr(slug_routes, "get_slug", lambda rt: "vm")
        monkeypatch.setattr(slug_routes, "get_table_client", lambda name: FallbackTable())
        payload = slug_routes._resolve_slug_payload("virtual_machine")
        assert payload["slug"] == "vm"
        assert payload["source"] == "github"

    def test_pii_keys_filtered(self, monkeypatch):
        class PIITable:
            def get_entity(self, partition_key, row_key):
                return {
                    "PartitionKey": "slug", "RowKey": "vm",
                    "ResourceType": "virtual_machine",
                    "ClaimedBy": "secret_user",  # should be filtered
                    "Email": "x@y.com",  # should be filtered
                    "Source": "azure",
                }

        monkeypatch.setattr(slug_routes, "get_slug", lambda rt: "vm")
        monkeypatch.setattr(slug_routes, "get_table_client", lambda name: PIITable())
        payload = slug_routes._resolve_slug_payload("virtual_machine")
        assert "claimedBy" not in payload
        assert "email" not in payload
        assert payload["source"] == "azure"

    def test_table_exception_handled(self, monkeypatch):
        monkeypatch.setattr(slug_routes, "get_slug", lambda rt: "vm")
        monkeypatch.setattr(slug_routes, "get_table_client", mock.Mock(side_effect=RuntimeError("no storage")))
        payload = slug_routes._resolve_slug_payload("virtual_machine")
        # Should still return basic payload even when table fails
        assert payload["slug"] == "vm"
        assert payload["resourceType"] == "virtual_machine"


# ---------------------------------------------------------------------------
# _perform_slug_sync
# ---------------------------------------------------------------------------

class TestPerformSlugSync:
    def test_empty_upstream(self, monkeypatch):
        monkeypatch.setattr(slug_routes, "get_all_remote_slugs", lambda: {})
        status, msg = slug_routes._perform_slug_sync()
        assert status == 502

    def test_creates_new(self, monkeypatch):
        from azure.core.exceptions import ResourceNotFoundError
        table = FakeTable(raise_on_get=ResourceNotFoundError("missing"))
        monkeypatch.setattr(slug_routes, "get_all_remote_slugs", lambda: {"st": "storage_account"})
        monkeypatch.setattr(slug_routes, "get_table_client", lambda name: table)
        status, msg = slug_routes._perform_slug_sync()
        assert status == 200
        assert "1 created" in msg
        assert len(table.upserted) == 1

    def test_updates_existing(self, monkeypatch):
        table = FakeTable({
            ("slug", "st"): {"PartitionKey": "slug", "RowKey": "st", "FullName": "old_name"},
        })
        monkeypatch.setattr(slug_routes, "get_all_remote_slugs", lambda: {"st": "storage_account"})
        monkeypatch.setattr(slug_routes, "get_table_client", lambda name: table)
        status, msg = slug_routes._perform_slug_sync()
        assert status == 200
        assert "1 updated" in msg

    def test_existing_unchanged(self, monkeypatch):
        table = FakeTable({
            ("slug", "st"): {"PartitionKey": "slug", "RowKey": "st", "FullName": "storage_account"},
        })
        monkeypatch.setattr(slug_routes, "get_all_remote_slugs", lambda: {"st": "storage_account"})
        monkeypatch.setattr(slug_routes, "get_table_client", lambda name: table)
        status, msg = slug_routes._perform_slug_sync()
        assert status == 200
        assert "1 existing" in msg


# ---------------------------------------------------------------------------
# slug_sync
# ---------------------------------------------------------------------------

class TestSlugSync:
    def test_auth_error(self, monkeypatch):
        monkeypatch.setattr(slug_routes, "require_role", mock.Mock(side_effect=_auth_error()))
        resp = _fn(slug_routes.slug_sync)(_make_request())
        assert resp.status_code == 401

    def test_slug_source_error(self, monkeypatch):
        from app.dependencies import SlugSourceError
        monkeypatch.setattr(slug_routes, "require_role", lambda h, min_role: ("u1", ["admin"]))
        monkeypatch.setattr(slug_routes, "_perform_slug_sync", mock.Mock(side_effect=SlugSourceError("network")))
        resp = _fn(slug_routes.slug_sync)(_make_request())
        assert resp.status_code == 503

    def test_azure_error(self, monkeypatch):
        from azure.core.exceptions import AzureError
        monkeypatch.setattr(slug_routes, "require_role", lambda h, min_role: ("u1", ["admin"]))
        monkeypatch.setattr(slug_routes, "_perform_slug_sync", mock.Mock(side_effect=AzureError("fail")))
        resp = _fn(slug_routes.slug_sync)(_make_request())
        assert resp.status_code == 500

    def test_runtime_error(self, monkeypatch):
        monkeypatch.setattr(slug_routes, "require_role", lambda h, min_role: ("u1", ["admin"]))
        monkeypatch.setattr(slug_routes, "_perform_slug_sync", mock.Mock(side_effect=RuntimeError("boom")))
        resp = _fn(slug_routes.slug_sync)(_make_request())
        assert resp.status_code == 500

    def test_unexpected_error(self, monkeypatch):
        monkeypatch.setattr(slug_routes, "require_role", lambda h, min_role: ("u1", ["admin"]))
        monkeypatch.setattr(slug_routes, "_perform_slug_sync", mock.Mock(side_effect=TypeError("weird")))
        resp = _fn(slug_routes.slug_sync)(_make_request())
        assert resp.status_code == 500

    def test_success(self, monkeypatch):
        monkeypatch.setattr(slug_routes, "require_role", lambda h, min_role: ("u1", ["admin"]))
        monkeypatch.setattr(slug_routes, "_perform_slug_sync", lambda: (200, "done"))
        resp = _fn(slug_routes.slug_sync)(_make_request())
        assert resp.status_code == 200
        body = json.loads(resp.get_body())
        assert body["message"] == "done"
