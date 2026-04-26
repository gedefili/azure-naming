"""Tests for app.routes.claims module."""

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

from app.routes import claims as claims_routes


def _fn(builder):
    return builder._function.get_user_function()


def _auth_error(msg="Auth failed", status=401):
    from app.dependencies import AuthError
    return AuthError(msg, status=status)


def _make_request(params=None, headers=None):
    class FakeReq:
        def __init__(self):
            self.params = params or {}
            self.headers = headers or {}

    return FakeReq()


class FakeIter:
    """Minimal iterable that implements `by_page` and `continuation_token`."""

    def __init__(self, entities, *, continuation_token=None):
        self._entities = entities
        self.continuation_token = continuation_token

    def by_page(self, continuation_token=None):
        # Single-page iteration for tests
        yield list(self._entities)


class FakeTable:
    def __init__(self, entities):
        self.entities = entities
        self.last_filter = None

    def query_entities(self, query_filter=None, results_per_page=None):
        self.last_filter = query_filter
        return FakeIter(self.entities)

    def list_entities(self, results_per_page=None):
        return FakeIter(self.entities)


SAMPLE_ENTITIES = [
    {
        "PartitionKey": "wus2-prd",
        "RowKey": "wus2prdstvm01",
        "ResourceType": "storage_account",
        "ClaimedBy": "alice@sanmar.com",
        "ClaimedAt": "2026-04-25T10:00:00Z",
        "InUse": True,
        "ClaimState": "claimed",
        "Slug": "st",
        "Project": "wms",
    },
    {
        "PartitionKey": "wus2-prd",
        "RowKey": "wus2prdkvprj01",
        "ResourceType": "key_vault",
        "ClaimedBy": "bob@sanmar.com",
        "ClaimedAt": "2026-04-26T11:00:00Z",
        "InUse": True,
        "ClaimState": "claimed",
        "Slug": "kv",
        "Project": "marketing",
    },
]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

class TestParsing:
    def test_parse_int_default(self):
        assert claims_routes._parse_int(None, default=50, minimum=1, maximum=200) == 50

    def test_parse_int_clamped(self):
        assert claims_routes._parse_int("999", default=50, minimum=1, maximum=200) == 200
        assert claims_routes._parse_int("-5", default=50, minimum=1, maximum=200) == 1

    def test_parse_int_invalid(self):
        with pytest.raises(ValueError):
            claims_routes._parse_int("abc", default=50, minimum=1, maximum=200)

    def test_parse_bool(self):
        assert claims_routes._parse_bool("true") is True
        assert claims_routes._parse_bool("false") is False
        assert claims_routes._parse_bool(None) is None
        with pytest.raises(ValueError):
            claims_routes._parse_bool("maybe")

    def test_entity_to_claim_strips_nones(self):
        claim = claims_routes._entity_to_claim(SAMPLE_ENTITIES[0])
        assert claim["name"] == "wus2prdstvm01"
        assert claim["region"] == "wus2"
        assert claim["environment"] == "prd"
        assert "released_by" not in claim

    def test_matches_query(self):
        claim = claims_routes._entity_to_claim(SAMPLE_ENTITIES[0])
        assert claims_routes._matches_query(claim, "alice")
        assert claims_routes._matches_query(claim, "wms")
        assert not claims_routes._matches_query(claim, "marketing")
        assert claims_routes._matches_query(claim, "")


# ---------------------------------------------------------------------------
# list_claims
# ---------------------------------------------------------------------------

class TestListClaims:
    def test_auth_error(self, monkeypatch):
        monkeypatch.setattr(claims_routes, "require_role", mock.Mock(side_effect=_auth_error()))
        resp = _fn(claims_routes.list_claims)(_make_request())
        assert resp.status_code == 401

    def test_non_admin_scoped_to_self(self, monkeypatch):
        monkeypatch.setattr(claims_routes, "require_role", lambda h, min_role: ("alice@sanmar.com", ["contributor"]))
        fake = FakeTable(SAMPLE_ENTITIES[:1])
        monkeypatch.setattr(claims_routes, "get_table_client", lambda _: fake)

        resp = _fn(claims_routes.list_claims)(_make_request())
        assert resp.status_code == 200
        body = json.loads(resp.get_body())
        assert body["scope"] == "alice@sanmar.com"
        assert body["is_admin"] is False
        assert body["count"] == 1
        assert "ClaimedBy eq 'alice@sanmar.com'" in fake.last_filter

    def test_non_admin_cannot_list_others(self, monkeypatch):
        monkeypatch.setattr(claims_routes, "require_role", lambda h, min_role: ("alice@sanmar.com", ["contributor"]))
        resp = _fn(claims_routes.list_claims)(_make_request(params={"owner": "bob@sanmar.com"}))
        assert resp.status_code == 403

    def test_admin_owner_all(self, monkeypatch):
        monkeypatch.setattr(claims_routes, "require_role", lambda h, min_role: ("admin@sanmar.com", ["admin"]))
        fake = FakeTable(SAMPLE_ENTITIES)
        monkeypatch.setattr(claims_routes, "get_table_client", lambda _: fake)

        resp = _fn(claims_routes.list_claims)(_make_request(params={"owner": "all"}))
        assert resp.status_code == 200
        body = json.loads(resp.get_body())
        assert body["scope"] == "all"
        assert body["count"] == 2
        # No ClaimedBy filter when owner=all and admin
        assert fake.last_filter is None or "ClaimedBy" not in (fake.last_filter or "")

    def test_admin_owner_specific(self, monkeypatch):
        monkeypatch.setattr(claims_routes, "require_role", lambda h, min_role: ("admin@sanmar.com", ["admin"]))
        fake = FakeTable([SAMPLE_ENTITIES[1]])
        monkeypatch.setattr(claims_routes, "get_table_client", lambda _: fake)

        resp = _fn(claims_routes.list_claims)(_make_request(params={"owner": "bob@sanmar.com"}))
        assert resp.status_code == 200
        body = json.loads(resp.get_body())
        assert body["scope"] == "bob@sanmar.com"
        assert "ClaimedBy eq 'bob@sanmar.com'" in fake.last_filter

    def test_query_filter(self, monkeypatch):
        monkeypatch.setattr(claims_routes, "require_role", lambda h, min_role: ("admin@sanmar.com", ["admin"]))
        fake = FakeTable(SAMPLE_ENTITIES)
        monkeypatch.setattr(claims_routes, "get_table_client", lambda _: fake)

        resp = _fn(claims_routes.list_claims)(_make_request(params={"owner": "all", "query": "marketing"}))
        body = json.loads(resp.get_body())
        assert body["count"] == 1
        assert body["items"][0]["project"] == "marketing"

    def test_invalid_limit(self, monkeypatch):
        monkeypatch.setattr(claims_routes, "require_role", lambda h, min_role: ("alice@sanmar.com", ["contributor"]))
        resp = _fn(claims_routes.list_claims)(_make_request(params={"limit": "abc"}))
        assert resp.status_code == 400

    def test_partition_filter_with_region_and_env(self, monkeypatch):
        monkeypatch.setattr(claims_routes, "require_role", lambda h, min_role: ("admin@sanmar.com", ["admin"]))
        fake = FakeTable(SAMPLE_ENTITIES)
        monkeypatch.setattr(claims_routes, "get_table_client", lambda _: fake)

        resp = _fn(claims_routes.list_claims)(_make_request(params={"owner": "all", "region": "wus2", "environment": "prd"}))
        assert resp.status_code == 200
        assert "PartitionKey eq 'wus2-prd'" in fake.last_filter
