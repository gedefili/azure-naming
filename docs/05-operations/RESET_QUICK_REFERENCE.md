# Quick Reference: Azurite Reset

## Automatic Reset (Recommended)

Starting local stack now automatically resets Azurite! ✨

```bash
# Just run start_local_stack.py - it handles reset automatically
python tools/start_local_stack.py
```

No separate reset command needed!

## Manual Reset (Optional)

If you want to reset without restarting the stack:

```bash
# Python version (recommended)
python tools/reset_azurite.py

# Bash version
./tools/reset_azurite.sh
```

## What Gets Reset

| Table | Purpose | State After Reset |
|-------|---------|-------------------|
| **ClaimedNames** | Claimed resource names | Empty |
| **AuditLogs** | Audit trail of operations | Empty |
| **SlugMappings** | Resource type ↔ slug mappings | Empty (populated by test 1.5) |

## Typical Workflow

```bash
# 1. Start local stack (Azurite + Functions + Auto-Reset)
python tools/start_local_stack.py

# 2. In ANOTHER terminal, open Postman and run:
#    Group 1: 1.5 (Slug Sync) - populates SlugMappings
#    Group 2: 2.1, 2.2 (Claim tests)
#    Group 3: 3.1, 3.1b, 3.2... (Release tests)
#    Group 4: 4.1, 4.2... (Audit tests)

# 3. To reset again for another test run:
python tools/reset_azurite.py
# (No need to restart the stack)
```

## Troubleshooting

**"Azurite is not running"**
```bash
# Make sure start_local_stack.py is running
python tools/start_local_stack.py
```

**"Name already exists" errors in Postman**
```bash
# Reset Azurite
python tools/reset_azurite.py

# Then re-run the Postman tests
```

**Complete reset (if all else fails)**
```bash
# Kill everything
pkill -f 'azurite|func host start|start_local_stack'

# Start fresh
python tools/start_local_stack.py

# Wait a moment, then reset
sleep 3
python tools/reset_azurite.py
```

## Important Notes

⚠️ **The reset script DELETES all data**
- Before running, make sure you don't need any existing data
- Great for test runs, but be careful in production-like environments

✅ **Safe to run multiple times**
- No harm in resetting when you don't need to
- Good practice: Reset before each full test run

📝 **Manual reset alternative**
- If script doesn't work, use Azure Storage Explorer
- See RESET_AZURITE_README.md for manual steps

## See Also

- [Full Reset Documentation](RESET_AZURITE_README.md)
- [Postman Collection Docs](../docs/04-development/postman.md)
- [Local Testing Guide](../docs/04-development/local-testing.md)
