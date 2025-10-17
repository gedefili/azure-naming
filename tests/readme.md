# Local testing guide — quick commands

This file contains copy-and-paste commands to start the local stack (Azurite), run the slug sync, do lookups, claim and release names, and run the functional tests. These commands assume you're in the repository root and have the project's virtualenv at `./.venv`.

1) Start Azurite (local Table Storage)

```bash
# start azurite in Docker
docker run -d --name azurite -p 10000:10000 -p 10001:10001 -p 10002:10002 mcr.microsoft.com/azure-storage/azurite

# export the Azurite devstore connection string (example):
export AzureWebJobsStorage="DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=Eby8vdM02x...;BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1;QueueEndpoint=http://127.0.0.1:10001/devstoreaccount1;TableEndpoint=http://127.0.0.1:10002/devstoreaccount1;"
```

2) Start the local stack (repo helper)

```bash
.venv/bin/python tools/start_local_stack.py &
# or run the Azure Functions host directly if you prefer:
# func start
```

3) Sync slugs into Table Storage

```bash
.venv/bin/python - <<'PY'
from adapters.slug_loader import sync_slug_definitions
print('Syncing slugs...')
print('Updated:', sync_slug_definitions())
PY
```

4) Inspect the slug mappings

```bash
.venv/bin/python - <<'PY'
from adapters.storage import get_table_client
table = get_table_client('SlugMappings')
for e in table.query_entities():
    print(e)
PY
```

5) Do lookups via Python

```bash
.venv/bin/python - <<'PY'
from core import slug_service
for t in ("resource_group","storage_account","virtual_machine","resource group"):
    try:
        print(t, '->', slug_service.get_slug(t))
    except Exception as e:
        print(t, '-> not found')
PY
```

6) Claim a name (example)

```bash
.venv/bin/python - <<'PY'
from adapters.storage import get_table_client
table = get_table_client('ClaimedNames')
entity = {
    'PartitionKey': 'wus2-prod',
    'RowKey': 'sanmar-st-prod-wus2',
    'InUse': True,
    'ResourceType': 'storage_account',
    'ClaimedBy': 'local-test',
}
table.upsert_entity(entity=entity, mode=None)
print('Claimed name')
PY
```

7) Release a name (example)

```bash
.venv/bin/python - <<'PY'
from adapters.storage import get_table_client
table = get_table_client('ClaimedNames')
partition = 'wus2-prod'
name = 'sanmar-st-prod-wus2'
try:
    e = table.get_entity(partition_key=partition, row_key=name)
    e['InUse'] = False
    table.upsert_entity(entity=e, mode=None)
    print('Released', name)
except Exception as ex:
    print('Release failed', ex)
PY
```

8) Useful curl examples (requires function host running locally)

```bash
# Slug lookup (may require auth, see docs)
curl -s "http://localhost:7071/api/slug?resource_type=storage_account" | jq

# Claim name (example JSON body, requires auth)
curl -s -X POST http://localhost:7071/api/claim -H 'Content-Type: application/json' -d '{"resourceType":"storage_account","region":"wus2","environment":"prod","slug":"st","optional_inputs":{}}' | jq

# Release name
curl -s -X POST http://localhost:7071/api/release -H 'Content-Type: application/json' -d '{"region":"wus2","environment":"prod","name":"sanmar-st-prod-wus2"}' | jq

# Trigger slug sync (admin)
curl -s -X POST http://localhost:7071/api/slug_sync -H 'Content-Type: application/json' -d '{}' | jq

---

Bearer token quick reference

Most endpoints require an Entra ID bearer token. See the README section "Bearer token (local testing)" for detailed instructions, or use the helper:

```bash
# Print a token and decoded claims (copy the token between the markers)
python tools/get_access_token.py --show-claims --client-id "$AZURE_CLIENT_ID"

# Export it for curl/Postman
export ACCESS_TOKEN="<PASTE_TOKEN_HERE>"
# Example curl with Authorization header
curl -H "Authorization: Bearer $ACCESS_TOKEN" "http://localhost:7071/api/slug?resource_type=storage_account" | jq
```
```

9) Run the full tests

```bash
.venv/bin/python -m pytest -q
```

If you'd like, I can run the quick fake sync locally now (no Azurite) to demonstrate inserts and lookups. Or I can start Azurite and run the full integration flow.
