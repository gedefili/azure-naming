# MCP Server for azure-naming

AI agents can interact with the Azure Naming domain through a lightweight Model Context Protocol (MCP) server. The implementation
lives in [`tools/mcp_server/`](../../tools/mcp_server/) and exposes the same operations that back the HTTP API.

## Supported tools

| Tool name      | Description                                             |
| -------------- | ------------------------------------------------------- |
| `claim_name`   | Generates and persists a claim using `generate_and_claim_name`. |
| `release_name` | Releases a previously claimed name and records an audit entry. |
| `lookup_slug`  | Resolves slug metadata for a resource type.             |
| `audit_name`   | Fetches the audit entity for a claimed name.            |

The server follows the JSON-RPC flavour of the MCP spec. Clients should send newline-delimited JSON messages over stdin/stdout.

## Running the server

```bash
python -m tools.mcp_server.server
```

The server waits for MCP messages on stdin and responds on stdout. During development you can exercise the tools with the helper
script below:

```bash
python - <<'PY'
import json
import subprocess

proc = subprocess.Popen(
    ["python", "-m", "tools.mcp_server.server"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    text=True,
)

proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize"}) + "\n")
proc.stdin.flush()
print(proc.stdout.readline().strip())

proc.stdin.write(json.dumps({
    "jsonrpc": "2.0",
    "id": 2,
    "method": "call_tool",
    "params": {
        "name": "lookup_slug",
        "arguments": {"resource_type": "storage_account"},
    },
}) + "\n")
proc.stdin.flush()
print(proc.stdout.readline().strip())

proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": 3, "method": "shutdown"}) + "\n")
proc.stdin.flush()
print(proc.stdout.readline().strip())
PY
```

## Authentication and storage

The MCP handlers delegate to the same storage abstractions as the HTTP routes. Configure the usual environment variables
(`AzureWebJobsStorage`, etc.) before launching the server so that `get_table_client` resolves correctly. When running locally you
can point at the Azurite emulator, a development storage account, or the production tables if you have permission.

Because the server executes in-process it inherits the Python credentials already configured for the Function app. No additional
Azure AD tokens are required.
