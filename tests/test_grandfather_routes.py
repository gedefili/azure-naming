"""Tests for the grandfathered claim and claims report endpoints."""

from __future__ import annotations

import json
import pathlib
import sys
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


class FakeTable:
    def __init__(self, entities=None, raise_on_get=None, raise_on_create=None):
        self._entities = entities or {}
        self._raise_on_get = raise_on_get
        self._raise_on_create = raise_on_create
        self.created = None

    def get_entity(self, partition_key, row_key):
        if self._raise_on_get:
            raise self._raise_on_get
        key = (partition_key, row_key)
        if key not in self._entities:
            raise RuntimeError("not found")
        return dict(self._entities[key])

    def create_entity(self, entity):
        if self._raise_on_create:
            raise self._raise_on_create
        self.created = entity

    def query_entities(self, query_filter=None):
        return list(self._entities.values())

    def list_entities(self):
        return list(self._entities.values())


def _valid_grandfather_body(**overrides):
    """Return a valid grandfathered claim request body with optional overrides."""
    base = {
        "name": "wus2-prd-rg-aznaming",
        "resource_type": "resource_group",
        "region": "wus2",
        "environment": "prd",
        "ownership_status": "identified",
        "import_source": "terraform_state",
        "reason": "Adopting existing deployed resource for naming registry.",
        "claimed_by": "geoffdefilippi@sanmar.com",
        "system": "aznaming",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# POST /api/claims/grandfather
# ---------------------------------------------------------------------------

class TestAdminGrandfatherClaim:
    def test_auth_error(self, monkeypatch):
        monkeypatch.setattr(names_routes, "require_role", mock.Mock(side_effect=_auth_error()))
        resp = _fn(names_routes.admin_grandfather_claim)(_make_request(body={}))
        assert resp.status_code == 401

    def test_auth_forbidden(self, monkeypatch):
        monkeypatch.setattr(names_routes, "require_role", mock.Mock(side_effect=_auth_error("Forbidden", 403)))
        resp = _fn(names_routes.admin_grandfather_claim)(_make_request(body={}))
        assert resp.status_code == 403

    def test_invalid_json(self, monkeypatch):
        monkeypatch.setattr(names_routes, "require_role", lambda h, min_role: ("admin1", ["admin"]))
        resp = _fn(names_routes.admin_grandfather_claim)(_make_request(body=None))
        assert resp.status_code == 400

    def test_missing_name(self, monkeypatch):
        monkeypatch.setattr(names_routes, "require_role", lambda h, min_role: ("admin1", ["admin"]))
        resp = _fn(names_routes.admin_grandfather_claim)(
            _make_request(body=_valid_grandfather_body(name=""))
        )
        assert resp.status_code == 400
        assert "name" in resp.get_body().decode().lower()

    def test_missing_resource_type(self, monkeypatch):
        monkeypatch.setattr(names_routes, "require_role", lambda h, min_role: ("admin1", ["admin"]))
        resp = _fn(names_routes.admin_grandfather_claim)(
            _make_request(body=_valid_grandfather_body(resource_type=""))
        )
        assert resp.status_code == 400
        assert "resource_type" in resp.get_body().decode().lower()

    def test_missing_region(self, monkeypatch):
        monkeypatch.setattr(names_routes, "require_role", lambda h, min_role: ("admin1", ["admin"]))
        resp = _fn(names_routes.admin_grandfather_claim)(
            _make_request(body=_valid_grandfather_body(region=""))
        )
        assert resp.status_code == 400
        assert "region" in resp.get_body().decode().lower()

    def test_missing_environment(self, monkeypatch):
        monkeypatch.setattr(names_routes, "require_role", lambda h, min_role: ("admin1", ["admin"]))
        resp = _fn(names_routes.admin_grandfather_claim)(
            _make_request(body=_valid_grandfather_body(environment=""))
        )
        assert resp.status_code == 400
        assert "environment" in resp.get_body().decode().lower()

    def test_invalid_ownership_status(self, monkeypatch):
        monkeypatch.setattr(names_routes, "require_role", lambda h, min_role: ("admin1", ["admin"]))
        resp = _fn(names_routes.admin_grandfather_claim)(
            _make_request(body=_valid_grandfather_body(ownership_status="maybe"))
        )
        assert resp.status_code == 400
        assert "ownership_status" in resp.get_body().decode().lower()

    def test_invalid_import_source(self, monkeypatch):
        monkeypatch.setattr(names_routes, "require_role", lambda h, min_role: ("admin1", ["admin"]))
        resp = _fn(names_routes.admin_grandfather_claim)(
            _make_request(body=_valid_grandfather_body(import_source="guessed"))
        )
        assert resp.status_code == 400
        assert "import_source" in resp.get_body().decode().lower()

    def test_missing_reason(self, monkeypatch):
        monkeypatch.setattr(names_routes, "require_role", lambda h, min_role: ("admin1", ["admin"]))
        resp = _fn(names_routes.admin_grandfather_claim)(
            _make_request(body=_valid_grandfather_body(reason=""))
        )
        assert resp.status_code == 400
        assert "reason" in resp.get_body().decode().lower()

    def test_success_new_claim(self, monkeypatch):
        table = FakeTable(raise_on_get=RuntimeError("not found"))
        captured_audit = {}
        monkeypatch.setattr(names_routes, "require_role", lambda h, min_role: ("admin1", ["admin"]))
        monkeypatch.setattr(names_routes, "get_table_client", lambda name: table)
        monkeypatch.setattr(names_routes, "write_audit_log", lambda *a, **kw: captured_audit.update({"action": a[2], "metadata": kw.get("metadata")}))
        # Bypass compliance check since naming rules may not exist in test
        monkeypatch.setattr(names_routes, "load_naming_rule", mock.Mock(side_effect=KeyError("no rule")), raising=False)

        resp = _fn(names_routes.admin_grandfather_claim)(
            _make_request(body=_valid_grandfather_body())
        )
        assert resp.status_code == 201
        body = json.loads(resp.get_body())
        assert body["name"] == "wus2-prd-rg-aznaming"
        assert body["grandfathered"] is True
        assert body["resourceType"] == "resource_group"
        assert body["message"] == "Name adopted as a grandfathered claim."
        assert table.created is not None
        assert table.created["Grandfathered"] is True
        assert table.created["InUse"] is True
        assert table.created["ClaimState"] == "claimed"
        assert table.created["LastLifecycleAction"] == "grandfathered"
        assert table.created["OwnershipStatus"] == "identified"
        assert table.created["ImportSource"] == "terraform_state"
        assert captured_audit["action"] == "grandfathered"

    def test_success_with_camelcase_aliases(self, monkeypatch):
        table = FakeTable(raise_on_get=RuntimeError("not found"))
        monkeypatch.setattr(names_routes, "require_role", lambda h, min_role: ("admin1", ["admin"]))
        monkeypatch.setattr(names_routes, "get_table_client", lambda name: table)
        monkeypatch.setattr(names_routes, "write_audit_log", lambda *a, **kw: None)

        body = {
            "name": "wus2prdstsanmaraznaming",
            "resourceType": "storage_account",
            "region": "wus2",
            "environment": "prd",
            "ownershipStatus": "identified",
            "importSource": "manifest",
            "claimedBy": "admin@sanmar.com",
            "reason": "Adopting storage account.",
        }
        resp = _fn(names_routes.admin_grandfather_claim)(_make_request(body=body))
        assert resp.status_code == 201
        assert table.created["ResourceType"] == "storage_account"

    def test_idempotent_existing_grandfathered(self, monkeypatch):
        existing = {
            "PartitionKey": "wus2-prd", "RowKey": "wus2-prd-rg-aznaming",
            "ResourceType": "resource_group", "Grandfathered": True,
            "ComplianceStatus": "compliant", "OwnershipStatus": "identified",
            "ClaimedBy": "admin1", "ImportSource": "terraform_state",
        }
        table = FakeTable({("wus2-prd", "wus2-prd-rg-aznaming"): existing})
        monkeypatch.setattr(names_routes, "require_role", lambda h, min_role: ("admin1", ["admin"]))
        monkeypatch.setattr(names_routes, "get_table_client", lambda name: table)

        resp = _fn(names_routes.admin_grandfather_claim)(
            _make_request(body=_valid_grandfather_body())
        )
        assert resp.status_code == 200
        body = json.loads(resp.get_body())
        assert body["message"] == "Name is already registered as a grandfathered claim."

    def test_conflict_different_resource_type(self, monkeypatch):
        existing = {
            "PartitionKey": "wus2-prd", "RowKey": "wus2-prd-rg-aznaming",
            "ResourceType": "virtual_network", "Grandfathered": False,
            "InUse": True, "ClaimState": "claimed",
        }
        table = FakeTable({("wus2-prd", "wus2-prd-rg-aznaming"): existing})
        monkeypatch.setattr(names_routes, "require_role", lambda h, min_role: ("admin1", ["admin"]))
        monkeypatch.setattr(names_routes, "get_table_client", lambda name: table)

        resp = _fn(names_routes.admin_grandfather_claim)(
            _make_request(body=_valid_grandfather_body())
        )
        assert resp.status_code == 409

    def test_storage_error(self, monkeypatch):
        table = FakeTable(raise_on_get=RuntimeError("not found"), raise_on_create=RuntimeError("storage down"))
        monkeypatch.setattr(names_routes, "require_role", lambda h, min_role: ("admin1", ["admin"]))
        monkeypatch.setattr(names_routes, "get_table_client", lambda name: table)
        monkeypatch.setattr(names_routes, "write_audit_log", lambda *a, **kw: None)

        resp = _fn(names_routes.admin_grandfather_claim)(
            _make_request(body=_valid_grandfather_body())
        )
        assert resp.status_code == 500

    def test_optional_fields_persisted(self, monkeypatch):
        table = FakeTable(raise_on_get=RuntimeError("not found"))
        monkeypatch.setattr(names_routes, "require_role", lambda h, min_role: ("admin1", ["admin"]))
        monkeypatch.setattr(names_routes, "get_table_client", lambda name: table)
        monkeypatch.setattr(names_routes, "write_audit_log", lambda *a, **kw: None)

        body = _valid_grandfather_body(
            project="naming",
            purpose="service",
            subsystem="api",
            import_reference="/subscriptions/xxx/resourceGroups/wus2-prd-rg-aznaming",
        )
        resp = _fn(names_routes.admin_grandfather_claim)(_make_request(body=body))
        assert resp.status_code == 201
        assert table.created["Project"] == "naming"
        assert table.created["Purpose"] == "service"
        assert table.created["Subsystem"] == "api"
        assert table.created["ImportReference"] == "/subscriptions/xxx/resourceGroups/wus2-prd-rg-aznaming"


# ---------------------------------------------------------------------------
# GET /api/claims/report
# ---------------------------------------------------------------------------

class TestAdminClaimsReport:
    def test_auth_error(self, monkeypatch):
        monkeypatch.setattr(names_routes, "require_role", mock.Mock(side_effect=_auth_error()))
        resp = _fn(names_routes.admin_claims_report)(_make_request(params={}))
        assert resp.status_code == 401

    def test_unfiltered_report(self, monkeypatch):
        entities = {
            ("wus2-prd", "wus2-prd-rg-aznaming"): {
                "PartitionKey": "wus2-prd", "RowKey": "wus2-prd-rg-aznaming",
                "ResourceType": "resource_group", "ClaimState": "claimed",
                "Grandfathered": True, "ComplianceStatus": "compliant",
                "OwnershipStatus": "identified", "ClaimedBy": "admin1",
                "InUse": True,
            },
            ("wus2-prd", "wus2prdstsanmaraznaming"): {
                "PartitionKey": "wus2-prd", "RowKey": "wus2prdstsanmaraznaming",
                "ResourceType": "storage_account", "ClaimState": "claimed",
                "Grandfathered": True, "ComplianceStatus": "noncompliant",
                "OwnershipStatus": "identified", "ClaimedBy": "admin1",
                "InUse": True,
            },
        }
        table = FakeTable(entities)
        monkeypatch.setattr(names_routes, "require_role", lambda h, min_role: ("admin1", ["admin"]))
        monkeypatch.setattr(names_routes, "get_table_client", lambda name: table)

        resp = _fn(names_routes.admin_claims_report)(_make_request(params={}))
        assert resp.status_code == 200
        body = json.loads(resp.get_body())
        assert body["total"] == 2
        assert len(body["results"]) == 2

    def test_filtered_grandfathered(self, monkeypatch):
        entities = {
            ("wus2-prd", "test"): {
                "PartitionKey": "wus2-prd", "RowKey": "test",
                "ResourceType": "vm", "ClaimState": "claimed",
                "Grandfathered": True, "InUse": True,
            },
        }
        table = FakeTable(entities)
        monkeypatch.setattr(names_routes, "require_role", lambda h, min_role: ("admin1", ["admin"]))
        monkeypatch.setattr(names_routes, "get_table_client", lambda name: table)

        resp = _fn(names_routes.admin_claims_report)(
            _make_request(params={"grandfathered": "true"})
        )
        assert resp.status_code == 200
        body = json.loads(resp.get_body())
        assert body["total"] == 1

    def test_filtered_compliance(self, monkeypatch):
        entities = {
            ("wus2-prd", "test"): {
                "PartitionKey": "wus2-prd", "RowKey": "test",
                "ResourceType": "vm", "ComplianceStatus": "noncompliant",
                "InUse": True,
            },
        }
        table = FakeTable(entities)
        monkeypatch.setattr(names_routes, "require_role", lambda h, min_role: ("admin1", ["admin"]))
        monkeypatch.setattr(names_routes, "get_table_client", lambda name: table)

        resp = _fn(names_routes.admin_claims_report)(
            _make_request(params={"compliance_status": "noncompliant"})
        )
        assert resp.status_code == 200

    def test_storage_error(self, monkeypatch):
        monkeypatch.setattr(names_routes, "require_role", lambda h, min_role: ("admin1", ["admin"]))
        monkeypatch.setattr(names_routes, "get_table_client", mock.Mock(side_effect=RuntimeError("down")))

        resp = _fn(names_routes.admin_claims_report)(_make_request(params={}))
        assert resp.status_code == 500

    def test_result_shape(self, monkeypatch):
        entities = {
            ("wus2-dev", "myvm"): {
                "PartitionKey": "wus2-dev", "RowKey": "myvm",
                "ResourceType": "vm", "ClaimState": "claimed",
                "Grandfathered": False, "ComplianceStatus": "compliant",
                "OwnershipStatus": "identified", "ClaimedBy": "u1",
                "InUse": True,
            },
        }
        table = FakeTable(entities)
        monkeypatch.setattr(names_routes, "require_role", lambda h, min_role: ("admin1", ["admin"]))
        monkeypatch.setattr(names_routes, "get_table_client", lambda name: table)

        resp = _fn(names_routes.admin_claims_report)(_make_request(params={}))
        body = json.loads(resp.get_body())
        entry = body["results"][0]
        assert entry["name"] == "myvm"
        assert entry["region"] == "wus2"
        assert entry["environment"] == "dev"
        assert entry["resourceType"] == "vm"
        assert entry["claimState"] == "claimed"
        assert entry["grandfathered"] is False
        assert entry["inUse"] is True
