# 🛠️ Development

Local development setup, testing, architecture documentation, and tools.

## Documents

- **[Local Testing Setup](local-testing.md)** — Running the service locally with Azurite and Azure Functions
- **[Module Structure](module-structure.md)** — Python package organization and component responsibilities
- **[Architecture Deep Dive](architecture.mmd)** — Mermaid diagram showing system components and flow
- **[Token Workflow](token_workflow.md)** — How to obtain bearer tokens for CLI and CI/CD testing
- **[Postman Testing](postman.md)** — Using the Postman collection for manual and automated testing

## Assets

- **[postman-local-collection.json](postman-local-collection.json)** — Importable Postman collection with pre-configured local endpoints

## Development Workflow

### 1. Set Up Local Environment

```bash
cd /home/geoffdefilippi/workspaces/azure-naming
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

See [Local Testing Setup](local-testing.md) for detailed steps.

### 2. Start Local Services

```bash
# Terminal 1: Start Azurite (local storage)
python tools/start_local_stack.py

# Or use VS Code task: Tasks → Run Task → "dev:start-local-stack"
```

### 3. Get a Bearer Token

```bash
python tools/get_access_token.py --client-id <CLIENT_ID>
```

See [Token Workflow](token_workflow.md) for details.

### 4. Test an Endpoint

```bash
curl -H "Authorization: Bearer <TOKEN>" \
  http://localhost:7071/api/slug?resource_type=storage_account
```

### 5. Understand the Architecture

- [Architecture Diagram](architecture.mmd) — Visual overview
- [Module Structure](module-structure.md) — Code organization
- [Data Schema](../03-api-reference/schema.md) — Storage models

## Testing

### Unit Tests

```bash
pytest tests/ -v
```

### Integration Tests

```bash
python tools/run_integration_locally.py --client-id <CLIENT_ID>
```

### Postman Collection

- [Postman Testing Guide](postman.md)
- [Import Collection](postman-local-collection.json)

## Key Tools

| Tool | Purpose | Reference |
|------|---------|-----------|
| Azure Functions Core Tools | Local Functions runtime | [Local Testing](local-testing.md) |
| Azurite | Local Azure Storage emulator | [Local Testing](local-testing.md) |
| Postman | API testing and documentation | [Postman Guide](postman.md) |
| `tools/start_local_stack.py` | Bootstrap local dev environment | [Local Testing](local-testing.md) |
| `tools/get_access_token.py` | Obtain bearer tokens | [Token Workflow](token_workflow.md) |

## See Also

- **Contributing** → [Contributing Guidelines](../01-planning/CONTRIBUTING.md)
- **API Usage** → [Usage & Endpoints](../03-api-reference/usage.md)
- **Deployment** → [Deployment Checklist](../05-operations/deployment.md)

## Quick Links

- [Back to Main Index](../index.md)
- [Full Documentation](../index.md#-development)
- [Main README](../../README.md) — High-level overview
