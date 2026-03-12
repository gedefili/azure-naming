"""Tests for adapters.storage module."""

from __future__ import annotations

import os
import pathlib
import sys
from unittest import mock

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adapters import storage


class FakeTableClient:
    """Minimal fake for TableClient."""

    def __init__(self, entities=None):
        self._entities = entities or {}

    def get_entity(self, partition_key, row_key):
        key = (partition_key, row_key)
        if key not in self._entities:
            raise storage.ResourceNotFoundError("not found")
        return dict(self._entities[key])

    def create_entity(self, entity):
        key = (entity["PartitionKey"], entity["RowKey"])
        if key in self._entities:
            raise storage.ResourceExistsError("conflict")
        self._entities[key] = entity

    def update_entity(self, entity, mode=None):
        key = (entity["PartitionKey"], entity["RowKey"])
        self._entities[key] = entity

    def create_table_if_not_exists(self, **kwargs):
        pass

    def query_entities(self, query_filter=None):
        return list(self._entities.values())


class FakeTableServiceClient:
    """Minimal fake for TableServiceClient."""

    def __init__(self):
        self._tables = {}

    def create_table_if_not_exists(self, table_name):
        if table_name not in self._tables:
            self._tables[table_name] = FakeTableClient()

    def get_table_client(self, table_name):
        if table_name not in self._tables:
            self._tables[table_name] = FakeTableClient()
        return self._tables[table_name]

    @classmethod
    def from_connection_string(cls, conn_str):
        return cls()


# ---------------------------------------------------------------------------
# _get_service
# ---------------------------------------------------------------------------

class TestGetService:
    def setup_method(self):
        # Reset cached service before each test
        storage._service = None

    def teardown_method(self):
        storage._service = None

    def test_missing_connection_string(self, monkeypatch):
        monkeypatch.delenv("AzureWebJobsStorage", raising=False)
        with pytest.raises(RuntimeError, match="AzureWebJobsStorage"):
            storage._get_service()

    def test_success(self, monkeypatch):
        monkeypatch.setenv("AzureWebJobsStorage", "DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=key;TableEndpoint=http://127.0.0.1:10002/devstoreaccount1;")
        monkeypatch.setattr(storage, "TableServiceClient", FakeTableServiceClient)
        svc = storage._get_service()
        assert svc is not None

    def test_caching(self, monkeypatch):
        monkeypatch.setenv("AzureWebJobsStorage", "fake-conn")
        monkeypatch.setattr(storage, "TableServiceClient", FakeTableServiceClient)
        svc1 = storage._get_service()
        svc2 = storage._get_service()
        assert svc1 is svc2


# ---------------------------------------------------------------------------
# get_table_client
# ---------------------------------------------------------------------------

class TestGetTableClient:
    def setup_method(self):
        storage._service = None

    def teardown_method(self):
        storage._service = None

    def test_returns_table_client(self, monkeypatch):
        monkeypatch.setenv("AzureWebJobsStorage", "fake")
        monkeypatch.setattr(storage, "TableServiceClient", FakeTableServiceClient)
        tc = storage.get_table_client("TestTable")
        assert tc is not None


# ---------------------------------------------------------------------------
# check_name_exists
# ---------------------------------------------------------------------------

class TestCheckNameExists:
    def setup_method(self):
        storage._service = None

    def teardown_method(self):
        storage._service = None

    def test_found_in_use(self, monkeypatch):
        fake_svc = FakeTableServiceClient()
        fake_table = FakeTableClient({
            ("wus2-dev", "myname"): {"PartitionKey": "wus2-dev", "RowKey": "myname", "InUse": True}
        })
        fake_svc._tables["ClaimedNames"] = fake_table
        storage._service = fake_svc
        assert storage.check_name_exists("wus2", "dev", "myname") is True

    def test_found_not_in_use(self, monkeypatch):
        fake_svc = FakeTableServiceClient()
        fake_table = FakeTableClient({
            ("wus2-dev", "myname"): {"PartitionKey": "wus2-dev", "RowKey": "myname", "InUse": False}
        })
        fake_svc._tables["ClaimedNames"] = fake_table
        storage._service = fake_svc
        assert storage.check_name_exists("wus2", "dev", "myname") is False

    def test_not_found(self, monkeypatch):
        fake_svc = FakeTableServiceClient()
        fake_svc._tables["ClaimedNames"] = FakeTableClient()
        storage._service = fake_svc
        assert storage.check_name_exists("wus2", "dev", "noexist") is False


# ---------------------------------------------------------------------------
# claim_name
# ---------------------------------------------------------------------------

class TestClaimName:
    def setup_method(self):
        storage._service = None

    def teardown_method(self):
        storage._service = None

    def test_claim_success(self):
        fake_svc = FakeTableServiceClient()
        fake_svc._tables["ClaimedNames"] = FakeTableClient()
        storage._service = fake_svc

        storage.claim_name("wus2", "dev", "newname", "storage_account", "user@test.com")
        entity = fake_svc._tables["ClaimedNames"].get_entity("wus2-dev", "newname")
        assert entity["InUse"] is True
        assert entity["ClaimedBy"] == "user@test.com"

    def test_claim_already_in_use(self):
        fake_svc = FakeTableServiceClient()
        fake_table = FakeTableClient({
            ("wus2-dev", "taken"): {
                "PartitionKey": "wus2-dev", "RowKey": "taken",
                "InUse": True, "ClaimedBy": "other@test.com",
            }
        })
        fake_svc._tables["ClaimedNames"] = fake_table
        storage._service = fake_svc

        with pytest.raises(storage.ResourceExistsError, match="already in use"):
            storage.claim_name("wus2", "dev", "taken", "vm", "user@test.com")

    def test_claim_with_metadata(self):
        fake_svc = FakeTableServiceClient()
        fake_svc._tables["ClaimedNames"] = FakeTableClient()
        storage._service = fake_svc

        storage.claim_name(
            "wus2", "dev", "meta", "vm", "user@test.com",
            metadata={"Project": "proj1", "Purpose": "test"},
        )
        entity = fake_svc._tables["ClaimedNames"].get_entity("wus2-dev", "meta")
        assert entity["Project"] == "proj1"
        assert entity["Purpose"] == "test"

    def test_claim_metadata_reserved_keys_filtered(self):
        """C-02: reserved keys in metadata are stripped."""
        fake_svc = FakeTableServiceClient()
        fake_svc._tables["ClaimedNames"] = FakeTableClient()
        storage._service = fake_svc

        storage.claim_name(
            "wus2", "dev", "filtered", "vm", "user@test.com",
            metadata={"PartitionKey": "evil", "RowKey": "bad", "Safe": "kept"},
        )
        entity = fake_svc._tables["ClaimedNames"].get_entity("wus2-dev", "filtered")
        assert entity["PartitionKey"] == "wus2-dev"
        assert entity["RowKey"] == "filtered"
        assert entity["Safe"] == "kept"

    def test_claim_concurrent_conflict(self):
        """Simulate concurrent create: first create succeeds, second fails."""
        fake_svc = FakeTableServiceClient()
        fake_svc._tables["ClaimedNames"] = FakeTableClient()
        storage._service = fake_svc

        # First claim succeeds
        storage.claim_name("wus2", "dev", "race", "vm", "user1@test.com")

        # Second claim for same name — entity already created
        with pytest.raises(storage.ResourceExistsError):
            storage.claim_name("wus2", "dev", "race", "vm", "user2@test.com")
