"""Minimal Model Context Protocol (MCP) server for azure-naming."""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, Mapping, Optional

from adapters.audit_logs import write_audit_log
from adapters.storage import get_table_client
from app.constants import NAMES_TABLE_NAME, SLUG_PARTITION_KEY, SLUG_TABLE_NAME
from app.dependencies import ResourceNotFoundError, UpdateMode
from core.name_service import NameGenerationResult, generate_and_claim_name
from core.slug_service import get_slug

logger = logging.getLogger(__name__)


@dataclass
class ToolSpec:
    """Description for a tool exposed over MCP."""

    name: str
    description: str
    schema: Mapping[str, Any]
    handler: Callable[[Mapping[str, Any]], Awaitable[Any]]


class MCPError(Exception):
    """Exception raised for protocol errors returned to the caller."""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class NamingMCPServer:
    """Implements a subset of the MCP JSON-RPC protocol over stdin/stdout."""

    protocol_version = "2024-05-01"

    def __init__(self, default_user: str | None = None) -> None:
        self._default_user = default_user or "system"
        self._tools: Dict[str, ToolSpec] = {}
        self._register_tools()

    # ------------------------------------------------------------------
    # Tool registration
    def _register_tools(self) -> None:
        self._tools = {
            "claim_name": ToolSpec(
                name="claim_name",
                description="Generate and claim a compliant name using azure-naming.",
                schema={
                    "type": "object",
                    "properties": {
                        "requested_by": {"type": "string", "description": "UPN or identifier performing the claim."},
                        "payload": {
                            "type": "object",
                            "description": "Payload accepted by the /api/claim endpoint.",
                        },
                    },
                    "required": ["payload"],
                },
                handler=self._handle_claim,
            ),
            "release_name": ToolSpec(
                name="release_name",
                description="Release a previously claimed name using azure-naming persistence layer.",
                schema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "region": {"type": "string"},
                        "environment": {"type": "string"},
                        "reason": {"type": "string", "default": "released by MCP"},
                    },
                    "required": ["name", "region", "environment"],
                },
                handler=self._handle_release,
            ),
            "lookup_slug": ToolSpec(
                name="lookup_slug",
                description="Return slug metadata for the supplied resource type.",
                schema={
                    "type": "object",
                    "properties": {
                        "resource_type": {"type": "string"},
                    },
                    "required": ["resource_type"],
                },
                handler=self._handle_lookup_slug,
            ),
            "audit_name": ToolSpec(
                name="audit_name",
                description="Retrieve claim audit metadata for a given name.",
                schema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "region": {"type": "string"},
                        "environment": {"type": "string"},
                    },
                    "required": ["name", "region", "environment"],
                },
                handler=self._handle_audit,
            ),
        }

    # ------------------------------------------------------------------
    # JSON-RPC handlers
    async def handle(self, request: Mapping[str, Any]) -> Dict[str, Any]:
        method = request.get("method")
        request_id = request.get("id")

        try:
            if method == "initialize":
                result = self._initialize()
            elif method == "list_tools":
                result = self._list_tools()
            elif method == "call_tool":
                params = request.get("params") or {}
                tool = params.get("name")
                args = params.get("arguments") or {}
                result = await self._call_tool(tool, args)
            elif method == "shutdown":
                result = {"ok": True}
            else:
                raise MCPError(-32601, f"Unknown method: {method}")
        except MCPError as exc:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": exc.code, "message": exc.message},
            }
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.exception("Unhandled MCP server error")
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32000, "message": str(exc)},
            }

        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    def _initialize(self) -> Dict[str, Any]:
        return {
            "protocolVersion": self.protocol_version,
            "serverInfo": {"name": "azure-naming", "version": "1.0"},
            "capabilities": {
                "tools": {
                    "list": True,
                    "call": True,
                }
            },
        }

    def _list_tools(self) -> Dict[str, Any]:
        tools_payload = []
        for spec in self._tools.values():
            tools_payload.append(
                {
                    "name": spec.name,
                    "description": spec.description,
                    "inputSchema": spec.schema,
                }
            )
        return {"tools": tools_payload}

    async def _call_tool(self, name: str, arguments: Mapping[str, Any]) -> Any:
        if not name:
            raise MCPError(-32602, "Tool name is required")
        spec = self._tools.get(name)
        if not spec:
            raise MCPError(-32601, f"Unknown tool: {name}")
        return await spec.handler(arguments)

    # ------------------------------------------------------------------
    # Tool implementations
    async def _handle_claim(self, arguments: Mapping[str, Any]) -> Dict[str, Any]:
        payload = arguments.get("payload")
        if not isinstance(payload, Mapping):
            raise MCPError(-32602, "payload must be an object")
        requested_by = arguments.get("requested_by") or self._default_user

        def _run() -> NameGenerationResult:
            return generate_and_claim_name(dict(payload), requested_by=requested_by)

        loop = asyncio.get_running_loop()
        result: NameGenerationResult = await loop.run_in_executor(None, _run)
        data = result.to_dict()
        data["requestedBy"] = requested_by
        return data

    async def _handle_release(self, arguments: Mapping[str, Any]) -> Dict[str, Any]:
        name = str(arguments.get("name") or "").lower()
        region = str(arguments.get("region") or "").lower()
        environment = str(arguments.get("environment") or "").lower()
        reason = str(arguments.get("reason") or "released by MCP")
        if not name or not region or not environment:
            raise MCPError(-32602, "name, region, and environment are required")

        table = get_table_client(NAMES_TABLE_NAME)
        mode = getattr(UpdateMode, "REPLACE", getattr(UpdateMode, "Replace", "Replace"))

        def _release() -> Dict[str, Any]:
            try:
                entity = table.get_entity(partition_key=f"{region}-{environment}", row_key=name)
            except ResourceNotFoundError as exc:  # pragma: no cover - depends on storage backend
                raise MCPError(404, f"Name '{name}' not found") from exc

            entity["InUse"] = False
            entity["ReleasedAt"] = datetime.utcnow().isoformat()
            entity["ReleasedBy"] = self._default_user
            entity["ReleaseReason"] = reason
            table.update_entity(entity=entity, mode=mode)
            write_audit_log(
                name,
                self._default_user,
                "released",
                reason,
                metadata={"Region": region, "Environment": environment},
            )
            return {
                "message": "Name released",
                "name": name,
                "region": region,
                "environment": environment,
            }

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _release)

    async def _handle_lookup_slug(self, arguments: Mapping[str, Any]) -> Dict[str, Any]:
        resource_type = str(arguments.get("resource_type") or "").strip()
        if not resource_type:
            raise MCPError(-32602, "resource_type is required")

        loop = asyncio.get_running_loop()

        def _lookup() -> Dict[str, Any]:
            slug_value = get_slug(resource_type)
            table = get_table_client(SLUG_TABLE_NAME)
            entity = None
            try:
                entity = table.get_entity(partition_key=SLUG_PARTITION_KEY, row_key=slug_value)
            except ResourceNotFoundError:
                entity = None
            payload = {"resourceType": resource_type.lower(), "slug": slug_value}
            if entity:
                for key, value in entity.items():
                    if key in {"PartitionKey", "RowKey"}:
                        continue
                    payload[key[0].lower() + key[1:]] = value
            return payload

        return await loop.run_in_executor(None, _lookup)

    async def _handle_audit(self, arguments: Mapping[str, Any]) -> Dict[str, Any]:
        name = str(arguments.get("name") or "").lower()
        region = str(arguments.get("region") or "").lower()
        environment = str(arguments.get("environment") or "").lower()
        if not name or not region or not environment:
            raise MCPError(-32602, "name, region, and environment are required")

        loop = asyncio.get_running_loop()

        def _fetch() -> Dict[str, Any]:
            table = get_table_client(NAMES_TABLE_NAME)
            try:
                entity = table.get_entity(partition_key=f"{region}-{environment}", row_key=name)
            except ResourceNotFoundError as exc:
                raise MCPError(404, f"Name '{name}' not found") from exc
            payload: Dict[str, Any] = {}
            for key, value in entity.items():
                if key in {"PartitionKey", "RowKey", "Timestamp"}:
                    continue
                payload[key[0].lower() + key[1:]] = value
            payload.setdefault("name", name)
            payload.setdefault("region", region)
            payload.setdefault("environment", environment)
            return payload

        return await loop.run_in_executor(None, _fetch)


async def _readline(reader: asyncio.StreamReader) -> Optional[str]:
    try:
        line = await reader.readline()
    except Exception:  # pragma: no cover - safety net
        return None
    if not line:
        return None
    return line.decode("utf-8").strip()


async def run_stdio_server(server: NamingMCPServer) -> None:
    """Run the MCP server over stdio until EOF or shutdown."""

    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await asyncio.get_event_loop().connect_read_pipe(lambda: protocol, sys.stdin)
    writer_transport, writer_protocol = await asyncio.get_event_loop().connect_write_pipe(asyncio.streams.FlowControlMixin, sys.stdout)
    writer = asyncio.StreamWriter(writer_transport, writer_protocol, reader, asyncio.get_event_loop())

    while True:
        line = await _readline(reader)
        if line is None:
            break
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            logger.warning("Ignoring invalid JSON payload: %s", line)
            continue

        response = await server.handle(request)
        writer.write(json.dumps(response).encode("utf-8") + b"\n")
        await writer.drain()

        if request.get("method") == "shutdown":
            break

    writer.close()
    await writer.wait_closed()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    server = NamingMCPServer()
    asyncio.run(run_stdio_server(server))


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()
