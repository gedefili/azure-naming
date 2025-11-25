import json
from types import SimpleNamespace

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.routes import slug as slug_routes


def test_resolve_slug_payload_includes_table_metadata(monkeypatch):
    class FakeTable:
        def get_entity(self, partition_key, row_key):
            assert partition_key == slug_routes.SLUG_PARTITION_KEY
            assert row_key == "st"
            return {
                "ResourceType": "storage_account",
                "FullName": "Storage Account",
                "Source": "azure_defined_specs",
                "UpdatedAt": "2024-01-01T00:00:00Z",
            }

    monkeypatch.setattr(slug_routes, "get_slug", lambda resource_type: "st")
    monkeypatch.setattr(slug_routes, "get_table_client", lambda table_name: FakeTable())

    payload = slug_routes._resolve_slug_payload("  Storage_Account  ")

    assert payload == {
        "resourceType": "storage_account",
        "slug": "st",
        "fullName": "Storage Account",
        "source": "azure_defined_specs",
        "updatedAt": "2024-01-01T00:00:00Z",
    }


def test_resolve_slug_payload_handles_missing_metadata(monkeypatch):
    class FakeTable:
        def get_entity(self, partition_key, row_key):
            raise slug_routes.ResourceNotFoundError("missing")

        def query_entities(self, **kwargs):
            return []

    monkeypatch.setattr(slug_routes, "get_slug", lambda resource_type: "vm")
    monkeypatch.setattr(slug_routes, "get_table_client", lambda table_name: FakeTable())

    payload = slug_routes._resolve_slug_payload(" virtual_machine ")

    assert payload == {"resourceType": "virtual_machine", "slug": "vm"}


def test_slug_lookup_returns_json_response(monkeypatch):
    request = SimpleNamespace(params={"resource_type": "storage_account"}, headers={})

    monkeypatch.setattr(slug_routes, "require_role", lambda headers, min_role: ("user", ["reader"]))
    monkeypatch.setattr(slug_routes, "_resolve_slug_payload", lambda resource_type: {"resourceType": "storage_account", "slug": "st"})

    response = slug_routes._handle_slug_lookup(request)

    assert response.status_code == 200
    body = json.loads(response.get_body())
    assert body == {"resourceType": "storage_account", "slug": "st"}


def test_slug_lookup_returns_404_when_missing(monkeypatch):
    request = SimpleNamespace(params={"resource_type": "missing"}, headers={})

    monkeypatch.setattr(slug_routes, "require_role", lambda headers, min_role: ("user", ["reader"]))

    def raise_value_error(_resource_type: str):
        raise ValueError("not found")

    monkeypatch.setattr(slug_routes, "_resolve_slug_payload", raise_value_error)

    response = slug_routes._handle_slug_lookup(request)

    assert response.status_code == 404
    body = json.loads(response.get_body())
    assert body["message"].startswith("Slug not found")
