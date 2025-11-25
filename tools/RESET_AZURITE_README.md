# Resetting Azurite Storage for Local Testing

This guide explains how Azurite storage is automatically reset when you start the local development stack.

## ✨ Automatic Reset (NEW!)

As of the latest update, Azurite tables are **automatically reset** when you start the local stack!

### Quick Start

Just run the startup script:

```bash
python tools/start_local_stack.py
```

That's it! The script will:
1. Start Azurite (Azure Storage Emulator)
2. Start Azure Functions host
3. **Automatically reset all tables** ✓
4. Display ready message with endpoints

## Why Reset Azurite?

When testing the Azure Naming API locally with Postman, you may encounter:
- Duplicate names from previous test runs
- Stale audit logs
- Missing or corrupted slug mappings

The automatic reset gives you a clean slate for each test session.

## What Gets Reset?

Three Azure Table Storage tables are automatically deleted and recreated:

Expected output:
```
2025-10-29 10:15:30,123 - INFO - ======================================================================
2025-10-29 10:15:30,124 - INFO - RESETTING AZURITE STORAGE FOR LOCAL POSTMAN TESTING
2025-10-29 10:15:30,125 - INFO - ======================================================================
2025-10-29 10:15:30,126 - INFO - Connecting to Azurite...
2025-10-29 10:15:30,200 - INFO - ✓ Connected to Azurite successfully
2025-10-29 10:15:30,201 - INFO - Deleting table: ClaimedNames (Claimed names table)...
2025-10-29 10:15:30,250 - INFO - ✓ Deleted ClaimedNames
2025-10-29 10:15:30,251 - INFO - Creating table: ClaimedNames...
2025-10-29 10:15:30,300 - INFO - ✓ Created ClaimedNames
2025-10-29 10:15:30,301 - INFO - Deleting table: AuditLogs (Audit logs table)...
2025-10-29 10:15:30,350 - INFO - ✓ Deleted AuditLogs
2025-10-29 10:15:30,351 - INFO - Creating table: AuditLogs...
2025-10-29 10:15:30,400 - INFO - ✓ Created AuditLogs
2025-10-29 10:15:30,401 - INFO - Deleting table: SlugMappings (Slug mappings table)...
2025-10-29 10:15:30,450 - INFO - ✓ Deleted SlugMappings
2025-10-29 10:15:30,451 - INFO - Creating table: SlugMappings...
2025-10-29 10:15:30,500 - INFO - ✓ Created SlugMappings

======================================================================
AZURITE RESET COMPLETE
======================================================================

## Getting Started

### 1. Start the Local Stack

```bash
python tools/start_local_stack.py
```

This will:
- Start Azurite on `http://127.0.0.1:10002`
- Start Azure Functions host on `http://localhost:7071`
- **Automatically reset all tables** (ClaimedNames, AuditLogs, SlugMappings)
- Display endpoints and next steps

### 2. Populate SlugMappings (First Time Only)

Before running claim tests, you need to populate the SlugMappings table with Azure resource types:

1. Open the Postman collection: `docs/04-development/postman-local-collection.json`
2. Go to **Group 1. Slug Endpoints**
3. Run test **1.5 Slug Sync - Fetch and Update**
4. This fetches all 86 resource types from GitHub and populates SlugMappings

### 3. Run Postman Tests

Now you're ready to run the full test suite:

1. **Group 1**: Slug lookups (already tested via 1.5)
2. **Group 2**: Claim name tests (2.1, 2.2, etc.)
3. **Group 3**: Release name tests (3.1, 3.1b, 3.2, etc.)
4. **Group 4**: Audit & Rules endpoints (4.1, 4.2, etc.)

### 4. Reset for Another Test Run

To reset storage for another test run:

```bash
# Option A: Restart the stack (resets automatically)
python tools/start_local_stack.py

# Option B: Reset without restarting
python tools/reset_azurite.py
```

## Tables Automatically Reset

The startup script deletes and recreates three Azure Table Storage tables:

### ClaimedNames
Stores currently claimed resource names. Structure:
- **PartitionKey**: `{region}-{environment}` (e.g., "wus2-prd", "eus-tst")
- **RowKey**: The claimed name (e.g., "stwus2prd01")
- **Columns**: ResourceType, Slug, InUse, ClaimedBy, ClaimedAt, ReleasedBy, ReleasedAt, etc.

### AuditLogs
Stores audit trail of all claim/release operations. Structure:
- **PartitionKey**: User ID or action type
- **RowKey**: Timestamp-based unique identifier
- **Columns**: Action, Name, ResourceType, Region, Environment, EventTime, etc.

### SlugMappings
Stores resource type to slug mappings from Azure. Structure:
- **PartitionKey**: "default"
- **RowKey**: Resource type (e.g., "storage_account", "cosmos")
- **Columns**: slug, description, etc.

## Troubleshooting

### Connection Error: "Azurite is not running"

**Problem**: Script fails to connect to Azurite

**Solution**:
```bash
# Check if Azurite is running
netstat -an | grep 10002

# Start the local stack
python tools/start_local_stack.py
```

### "ResourceNotFoundError" when deleting tables

**Problem**: One or more tables don't exist

**Solution**: This is normal on first run. The script handles this gracefully by catching the exception and continuing.

### After reset, tests fail with "Name already exists"

**Problem**: Azurite wasn't fully reset or claim test ran twice

**Solution**: 
```bash
# Completely reset Azurite
python tools/reset_azurite.py

# If that doesn't work, stop and restart everything
pkill -f 'azurite|func host start'
sleep 2
python tools/start_local_stack.py
python tools/reset_azurite.py
```

## Manual Reset (Alternative)

If you prefer to use Azure Storage Explorer:

1. Open **Azure Storage Explorer**
2. Connect to "Local storage account" (Azurite)
3. Expand **Tables**
4. Right-click and delete:
   - ClaimedNames
   - AuditLogs
   - SlugMappings
5. Right-click and create new tables with those names

## Environment Variables

If you need to modify the Azurite connection, edit `tools/reset_azurite.py`:

```python
# Default (Azurite on localhost)
AZURITE_CONNECTION = "UseDevelopmentStorage=true"

# Or specify explicit connection string:
# AZURITE_CONNECTION = "DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=...;TableEndpoint=http://127.0.0.1:10002/devstoreaccount1;"
```

## Full Workflow Example

```bash
# Terminal 1: Start local stack (auto-resets Azurite)
python tools/start_local_stack.py

# Terminal 2: Open Postman and run tests in order:
#    - 1.5 Slug Sync (to populate SlugMappings)
#    - 2.1 Claim Name (happy path)
#    - 2.2 Claim Name (different region)
#    - 3.1 Release Name
#    - 3.1b Release Name (second claim)
#    - 4.1 Get Audit Logs
#    - etc.

# To test again with clean data:
python tools/reset_azurite.py
# (No need to restart the stack!)
```

## See Also

- [Local Testing Guide](local-testing.md)
- [Postman Collection Documentation](postman.md)
- [Architecture Overview](architecture.mmd)
