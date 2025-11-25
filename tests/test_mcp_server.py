"""Tests for the MCP server implementation."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Dict

import pytest

from app.dependencies import ResourceNotFoundError
from tools.mcp_server.server import NamingMCPServer


@dataclass
class FakeNameResult:
    name: str = "wus2prdsvc0001"
    resource_type: str = "storage_account"
    region: str = "wus2"
    environment: str = "prd"
    slug: str = "st"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "resourceType": self.resource_type,
            "region": self.region,
            "environment": self.environment,
            "slug": self.slug,
        }


def _run(awaitable):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(awaitable)
    finally:
        loop.close()


def test_initialize_and_list_tools(monkeypatch):
    server = NamingMCPServer()
    init = _run(server.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize"}))
    assert init["result"]["protocolVersion"] == server.protocol_version

    listed = _run(server.handle({"jsonrpc": "2.0", "id": 2, "method": "list_tools"}))
    tool_names = {tool["name"] for tool in listed["result"]["tools"]}
    assert {"claim_name", "release_name", "lookup_slug", "audit_name"}.issubset(tool_names)


def test_claim_tool(monkeypatch):
    server = NamingMCPServer(default_user="tester")

    monkeypatch.setattr(
        "tools.mcp_server.server.generate_and_claim_name",
        lambda payload, requested_by: FakeNameResult(),
    )

    response = _run(
        server.handle(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "call_tool",
            "params": {
                "name": "claim_name",
                "arguments": {"payload": {"resource_type": "storage_account", "region": "wus2", "environment": "prd"}},
            },
        }
        )
    )

    assert response["result"]["name"] == "wus2prdsvc0001"
    assert response["result"]["requestedBy"] == "tester"


class FakeTable:
    def __init__(self) -> None:
        self.entity = {
            "PartitionKey": "wus2-prd",
            "RowKey": "wus2prdsvc0001",
            "InUse": True,
        }
        self.updated = None

    def get_entity(self, partition_key: str, row_key: str) -> Dict[str, Any]:
        if row_key != self.entity["RowKey"]:
            raise ResourceNotFoundError("not found")
        return dict(self.entity)

    def update_entity(self, *, entity: Dict[str, Any], mode: str) -> None:
        self.updated = (entity, mode)


def test_release_tool(monkeypatch):
    server = NamingMCPServer(default_user="tester")
    table = FakeTable()

    monkeypatch.setattr("tools.mcp_server.server.get_table_client", lambda name: table)
    monkeypatch.setattr("tools.mcp_server.server.write_audit_log", lambda *args, **kwargs: None)
    monkeypatch.setattr("tools.mcp_server.server.UpdateMode", type("U", (), {"REPLACE": "Replace"}))

    response = _run(
        server.handle(
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "call_tool",
            "params": {
                "name": "release_name",
                "arguments": {
                    "name": "wus2prdsvc0001",
                    "region": "wus2",
                    "environment": "prd",
                },
            },
        }
        )
    )

    assert response["result"]["message"] == "Name released"
    updated, mode = table.updated
    assert updated["InUse"] is False
    assert mode == "Replace"


def test_lookup_slug_tool(monkeypatch):
    server = NamingMCPServer()
    table = FakeTable()
    table.entity = {
        "PartitionKey": "slugs",
        "RowKey": "st",
        "FullName": "Storage Account",
    }

    monkeypatch.setattr("tools.mcp_server.server.get_slug", lambda resource_type: "st")
    monkeypatch.setattr("tools.mcp_server.server.get_table_client", lambda name: table)

    response = _run(
        server.handle(
        {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "call_tool",
            "params": {"name": "lookup_slug", "arguments": {"resource_type": "storage_account"}},
        }
        )
    )

    assert response["result"]["slug"] == "st"
    assert response["result"]["fullName"] == "Storage Account"


def test_audit_tool(monkeypatch):
    server = NamingMCPServer()
    table = FakeTable()

    def fake_get(name: str) -> FakeTable:
        return table

    monkeypatch.setattr("tools.mcp_server.server.get_table_client", fake_get)

    response = _run(
        server.handle(
        {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "call_tool",
            "params": {
                "name": "audit_name",
                "arguments": {
                    "name": "wus2prdsvc0001",
                    "region": "wus2",
                    "environment": "prd",
                },
            },
        }
        )
    )

    assert response["result"]["name"] == "wus2prdsvc0001"


def test_unknown_tool_error():
    server = NamingMCPServer()
    result = _run(server.handle({"jsonrpc": "2.0", "id": 7, "method": "call_tool", "params": {"name": "nope", "arguments": {}}}))
    assert result["error"]["code"] == -32601
