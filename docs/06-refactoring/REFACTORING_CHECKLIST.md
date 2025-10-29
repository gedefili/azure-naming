# Quick Reference: Refactoring Checklist

## Phase 1: Create Libraries ✓ Planning Complete

### Step 1: Create Package Structure
- [ ] `mkdir -p tools/lib`
- [ ] `touch tools/lib/__init__.py`

### Step 2: Create Library Modules (in this order)
- [ ] `tools/lib/storage_config.py` (15 lines, no dependencies)
- [ ] `tools/lib/token_utils.py` (30 lines, stdlib + jwt only)
- [ ] `tools/lib/process_utils.py` (80 lines, stdlib only)
- [ ] `tools/lib/bootstrap_utils.py` (40 lines, uses process_utils)
- [ ] Update `tools/lib/__init__.py` with exports

### Step 3: Unit Tests for Libraries
- [ ] `tests/test_lib_storage_config.py`
- [ ] `tests/test_lib_token_utils.py`
- [ ] `tests/test_lib_process_utils.py` (with mocks)
- [ ] `tests/test_lib_bootstrap_utils.py` (with mocks)

---

## Phase 2: Refactor Scripts

### Step 4: Refactor `get_access_token.py` (Simplest)
**Changes**:
- Import: `from tools.lib import run_az_command, decode_jwt_claims, format_expiry_timestamp`
- Remove: `_run_az_command()` function → use imported version
- Remove: `_decode_claims()` function → use imported version
- Remove: `_format_expiry()` function → use imported version
- Keep: `get_parser()`, `main()` logic (simplified to 60 lines)

**Before**: 120 lines  
**After**: 60 lines (-50%)  
**Testing**: `python tools/get_access_token.py --help` should work unchanged

### Step 5: Refactor `run_integration_locally.py` (Medium)
**Changes**:
- Import: `from tools.lib import run_command, is_port_open, wait_for_port, dev_storage_connection_string, dev_table_endpoint`
- Remove: `_run()` function → use `run_command()`
- Remove: `_is_port_open()` function → use imported version
- Remove: `_wait_for_table()` logic → use `wait_for_port()`
- Remove: `AZURITE_*_PORT` constants → use `storage_config`
- Remove: `DEV_CONNECTION` constant → use `storage_config.dev_storage_connection_string()`
- Keep: `main()` orchestration (simplified to 80 lines)

**Before**: 140 lines  
**After**: 80 lines (-43%)  
**Testing**: `python tools/run_integration_locally.py --help` should work unchanged

### Step 6: Refactor `start_local_stack.py` (Most Complex)
**Changes**:
- Import: `from tools.lib import process_utils, bootstrap_utils, storage_config`
- Remove: `ProcessManager` class → use `process_utils.ProcessManager()`
- Remove: `_kill_port_holder()` → use `process_utils.kill_process_by_port()`
- Remove: `_watchdog_port_binding()` → use `bootstrap_utils.watchdog_port_binding()`
- Remove: `wait_for_port()` → use `process_utils.wait_for_port()`
- Remove: `ensure_port_free()` → use `process_utils.is_port_open()` + `kill_process_by_port()`
- Remove: `ensure_directory()` → use `bootstrap_utils.ensure_directory()`
- Remove: logging setup → use `bootstrap_utils.setup_logging()`
- Remove: `AZURITE_PORTS` constant → use `storage_config`
- Keep: `start_azurite()` orchestration (simplified to 30 lines)
- Keep: `start_functions()` orchestration (simplified to 35 lines)
- Keep: `main()` orchestration (simplified to 65 lines)

**Before**: 382 lines  
**After**: 220 lines (-42%)  
**Testing**: Run `dev:start-local-stack` task; verify ports bind and Swagger UI loads

### Step 7: NO CHANGES to `run_tests_with_coverage.py`
This script is already clean (no duplication detected).

---

## Phase 3: Validation

### Step 8: Test Each Refactored Script
- [ ] `python tools/get_access_token.py --show-claims` → produces same output
- [ ] `python tools/run_integration_locally.py --help` → same help text
- [ ] `pytest tools/` → all tool scripts still work
- [ ] VS Code task `dev:start-local-stack` → ports bind within 15 seconds
- [ ] `curl http://localhost:7071/api/docs` → Swagger UI loads
- [ ] `curl http://localhost:10000/` → Azurite responds

### Step 9: Run Integration Tests
- [ ] `python tools/run_tests_with_coverage.py` → all tests pass
- [ ] `python tools/run_integration_locally.py` → integration tests pass

### Step 10: Documentation Updates
- [ ] Add section to `docs/module-structure.md` explaining new `tools/lib/` modules
- [ ] Add usage examples to each library module docstring
- [ ] Update any existing tool-related documentation

---

## Verification Commands

After each script refactor, run:

```bash
# Syntax check
python -m py_compile tools/get_access_token.py

# Quick smoke test
python tools/get_access_token.py --help

# Full integration test
python tools/run_integration_locally.py --help

# Run local stack
dev:start-local-stack  # VS Code task
```

---

## Commits Strategy

Suggest committing in phases:

**Commit 1**: "feat: add tools/lib infrastructure with 4 new utility modules"
- All 4 library modules + tests
- Includes all library specifications

**Commit 2**: "refactor: update get_access_token.py to use tools/lib"
- Only changes to get_access_token.py

**Commit 3**: "refactor: update run_integration_locally.py to use tools/lib"
- Only changes to run_integration_locally.py

**Commit 4**: "refactor: update start_local_stack.py to use tools/lib"
- Only changes to start_local_stack.py
- Largest change, easiest to review when isolated

**Commit 5**: "docs: update documentation for tools/lib modules"
- Documentation only

---

## Rollback Plan (if needed)

If any refactored script breaks:

1. `git diff tools/get_access_token.py` to see what changed
2. `git checkout HEAD -- tools/get_access_token.py` to revert
3. Debug library module (test in isolation)
4. Re-apply refactoring with fixes

Since libraries are new (not modifying existing code), rollback is safe and easy.

---

## Success Criteria ✓

- [ ] All 4 library modules created with full test coverage
- [ ] All 3 scripts refactored (get_access_token, run_integration_locally, start_local_stack)
- [ ] All CLI interfaces identical to before (no breaking changes)
- [ ] All tools work as expected (smoke tests pass)
- [ ] Code duplication reduced from 40 lines to 0 lines
- [ ] Total lines reduced from 875 to 685 (-22%)
- [ ] All tests passing (existing + new)

---

## Estimated Time Breakdown

| Task | Duration |
|------|----------|
| Create 4 library modules + tests | 45 min |
| Refactor get_access_token.py | 15 min |
| Refactor run_integration_locally.py | 20 min |
| Refactor start_local_stack.py | 30 min |
| Testing & validation | 20 min |
| Documentation update | 15 min |
| **Total** | **~2.5 hours** |

---

## Notes

- **No breaking changes**: All CLI interfaces remain identical
- **Pure refactoring**: Internal restructuring only
- **Backwards compatible**: Existing scripts unaffected
- **Testable**: Each library module is independently testable
- **Extensible**: Libraries can be extended for future needs

---

## Questions to Ask While Refactoring

1. **Is this logic used in multiple scripts?** → Extract to library
2. **Could this be tested independently?** → Extract to library
3. **Does this represent a single responsibility?** → Good library module
4. **Could another script benefit from this?** → Extract to library
5. **Is the error handling consistent?** → Consolidate in library

---

## Resources

- Full analysis: `REFACTORING_PLAN.md`
- Library specs: `LIBRARY_SPECIFICATIONS.md`
- Code locations:
  - Scripts to refactor: `tools/*.py`
  - New libraries: `tools/lib/*.py`
  - Library tests: `tests/test_lib_*.py`
