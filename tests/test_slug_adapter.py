import pytest

import os

from adapters import slug as slug_adapter


class FakeTable:
    def __init__(self):
        self.queries = []

    def query_entities(self, filter_str):
        # record queries for assertions
        self.queries.append(filter_str)
        # return a matching entity when FullName matches 'resource group'
        if "FullName eq 'resource group'" in filter_str:
            return [{"Slug": "rg", "RowKey": "rg", "ResourceType": "resource_group", "FullName": "resource group"}]
        # return a matching entity when ResourceType matches 'storage_account'
        if "ResourceType eq 'storage_account'" in filter_str:
            return [{"Slug": "st", "RowKey": "st", "ResourceType": "storage_account", "FullName": "storage account"}]
        return []


def test_get_slug_prefers_fullname_and_resource_type_variants(monkeypatch):
    fake = FakeTable()
    monkeypatch.setattr(slug_adapter, "get_table_client", lambda *_: fake)

    # human-readable lookup
    assert slug_adapter.get_slug("resource group") == "rg"
    # canonical lookup
    assert slug_adapter.get_slug("storage_account") == "st"

    # queries recorded should include both FullName and ResourceType checks
    assert any("FullName eq 'resource group'" in q for q in fake.queries)
    assert any("ResourceType eq 'storage_account'" in q for q in fake.queries)


def test_get_slug_raises_when_missing(monkeypatch):
    class EmptyTable:
        def query_entities(self, filter_str):
            return []

    monkeypatch.setattr(slug_adapter, "get_table_client", lambda *_: EmptyTable())

    with pytest.raises(ValueError):
        slug_adapter.get_slug("nonexistent")
