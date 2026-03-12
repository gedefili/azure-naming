"""Tests for adapters: release_name, audit_logs, slug_fetcher."""

from __future__ import annotations

import pathlib
import sys
from unittest import mock

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ---------------------------------------------------------------------------
# adapters.release_name
# ---------------------------------------------------------------------------

class TestReleaseName:
    def test_success(self, monkeypatch):
        from adapters import release_name as release_mod

        entity = {"InUse": True}
        updated = {}

        class FakeTable:
            def get_entity(self, partition_key, row_key):
                return dict(entity)

            def update_entity(self, e, mode=None):
                updated.update(e)

        monkeypatch.setattr(release_mod, "get_table_client", lambda name: FakeTable())
        result = release_mod.release_name("wus2", "dev", "myname", "user1")
        assert result is True
        assert updated["InUse"] is False
        assert updated["ReleasedBy"] == "user1"
        assert "ReleasedOn" in updated

    def test_not_found(self, monkeypatch):
        from adapters import release_name as release_mod
        from azure.core.exceptions import ResourceNotFoundError

        class FakeTable:
            def get_entity(self, partition_key, row_key):
                raise ResourceNotFoundError("gone")

        monkeypatch.setattr(release_mod, "get_table_client", lambda name: FakeTable())
        result = release_mod.release_name("wus2", "dev", "missing", "user1")
        assert result is False


# ---------------------------------------------------------------------------
# adapters.audit_logs
# ---------------------------------------------------------------------------

class TestWriteAuditLog:
    def test_success(self, monkeypatch):
        from adapters import audit_logs as audit_mod

        created = {}

        class FakeTable:
            def create_entity(self, entity):
                created.update(entity)

        monkeypatch.setattr(audit_mod, "get_table_client", lambda name: FakeTable())
        audit_mod.write_audit_log("res1", "user1", "claimed", "note here", metadata={"Project": "p1"})
        assert created["PartitionKey"] == "res1"
        assert created["User"] == "user1"
        assert created["Action"] == "claimed"
        assert created["Project"] == "p1"

    def test_runtime_error_on_init(self, monkeypatch):
        from adapters import audit_logs as audit_mod

        monkeypatch.setattr(audit_mod, "get_table_client", mock.Mock(side_effect=RuntimeError("no conn")))
        # Should not raise, just log
        audit_mod.write_audit_log("res1", "user1", "claimed")

    def test_azure_error_on_create(self, monkeypatch):
        from adapters import audit_logs as audit_mod
        from azure.core.exceptions import AzureError

        class FakeTable:
            def create_entity(self, entity):
                raise AzureError("storage fail")

        monkeypatch.setattr(audit_mod, "get_table_client", lambda name: FakeTable())
        # Should not raise, just log
        audit_mod.write_audit_log("res1", "user1", "claimed")

    def test_no_metadata(self, monkeypatch):
        from adapters import audit_logs as audit_mod

        created = {}

        class FakeTable:
            def create_entity(self, entity):
                created.update(entity)

        monkeypatch.setattr(audit_mod, "get_table_client", lambda name: FakeTable())
        audit_mod.write_audit_log("res1", "user1", "released")
        assert "PartitionKey" in created
        assert created["User"] == "user1"


# ---------------------------------------------------------------------------
# adapters.slug_fetcher
# ---------------------------------------------------------------------------

class TestGetAllRemoteSlugs:
    def test_success(self, monkeypatch):
        from adapters import slug_fetcher

        hcl = '''
variable "az" {
  default = {
    az = {
      storage_account = "st"
      virtual_machine = "vm"
    }
  }
}
'''
        # Construct text with az = { block
        hcl_text = 'az = {\n  storage_account = "st"\n  virtual_machine = "vm"\n}\n'

        class FakeResponse:
            text = hcl_text
            def raise_for_status(self):
                pass

        monkeypatch.setattr(slug_fetcher.requests, "get", lambda url, timeout: FakeResponse())
        result = slug_fetcher.get_all_remote_slugs()
        assert result["st"] == "storage_account"
        assert result["vm"] == "virtual_machine"

    def test_fetch_failure(self, monkeypatch):
        from adapters import slug_fetcher

        def fail_fetch(url, timeout):
            raise ConnectionError("network error")

        monkeypatch.setattr(slug_fetcher.requests, "get", fail_fetch)
        with pytest.raises(slug_fetcher.SlugSourceError):
            slug_fetcher.get_all_remote_slugs()

    def test_missing_block(self, monkeypatch):
        from adapters import slug_fetcher

        class FakeResponse:
            text = "no az block here"
            def raise_for_status(self):
                pass

        monkeypatch.setattr(slug_fetcher.requests, "get", lambda url, timeout: FakeResponse())
        with pytest.raises(slug_fetcher.SlugSourceError):
            slug_fetcher.get_all_remote_slugs()
