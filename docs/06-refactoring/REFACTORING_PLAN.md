# Python Scripts Refactoring Plan: DRY & SOLID

## Executive Summary

The `tools/` directory contains 4 production scripts that have grown to significant size (382-233 lines each) with **substantial code duplication**. This plan extracts common patterns into reusable libraries following SOLID (Single Responsibility) and DRY (Don't Repeat Yourself) principles.

**Current State**: ~900 lines of tool scripts with ~35% duplication  
**Target State**: ~500 lines of scripts + ~150 lines of libraries with zero duplication

---

## Duplication Analysis

### 1. **Subprocess & Process Management** (Highest Priority)

**Location**: Used in 3/4 scripts

#### `tools/start_local_stack.py`
```python
def _kill_port_holder(port: int) -> None:
    """Attempt to kill process holding the given port."""
    # 20 lines: Windows netstat + Linux lsof logic
    
def _run_az_command(args: list[str]) -> Dict[str, Any]:
    """Execute subprocess with JSON output parsing"""
    # 15 lines
```

#### `tools/run_integration_locally.py`
```python
def _run(cmd: str, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    """Execute command with logging"""
    # 3 lines, similar wrapper
    
def _is_port_open(port: int) -> bool:
    """Check if port is listening"""
    # 7 lines
    
def _wait_for_table(port: int, timeout_s: int = 30) -> bool:
    """Poll port until responsive"""
    # 11 lines
```

#### `tools/get_access_token.py`
```python
def _run_az_command(args: list[str]) -> Dict[str, Any]:
    """Same as start_local_stack.py - EXACT DUPLICATE"""
    # 15 lines - DUPLICATED
```

**Issues**:
- ❌ `_run_az_command()` duplicated in 2 files
- ❌ Port checking logic spread across 3 files
- ❌ Process termination logic only in 1 file (should be reusable)
- ❌ Subprocess error handling inconsistent

**Impact**: ~40 lines of duplicate/similar code

---

### 2. **Logging & Bootstrap Setup** (Medium Priority)

**Location**: `tools/start_local_stack.py` (large)

#### Issues
- ❌ Logging configuration is inline (18 lines)
- ❌ `ProcessManager` class (15 lines) is specific to bootstrap but uses generic patterns
- ❌ Port validation (`ensure_port_free`, `wait_for_port`, `_kill_port_holder`) = 50 lines of utility logic tightly coupled to main script

**Impact**: ~50 lines of reusable but embedded utilities

---

### 3. **JWT/Token Utilities** (Low-Medium Priority)

**Location**: `tools/get_access_token.py`

#### Issues
- ❌ `_decode_claims()` (5 lines) + `_format_expiry()` (10 lines) = 15 lines of JWT-specific logic
- ❌ Not reusable in other token-based workflows
- ❌ Could be extracted for potential test/auth integrations

**Impact**: ~15 lines of specialized utilities

---

### 4. **Azure Storage Connection Strings** (Low Priority)

**Location**: `tools/run_integration_locally.py`

```python
AZURITE_TABLE_PORT = 10002
AZURITE_BLOB_PORT = 10000
AZURITE_QUEUE_PORT = 10001

DEV_CONNECTION = "DefaultEndpointsProtocol=http;..."  # 10 lines
```

**Issue**: Could be shared with `start_local_stack.py` if that script needs local storage config

---

## Refactoring Plan

### Phase 1: Create Library Structure

Create `tools/lib/` directory with focused, single-responsibility modules:

```
tools/
├── lib/
│   ├── __init__.py
│   ├── process_utils.py       # NEW: subprocess, port management
│   ├── bootstrap_utils.py      # NEW: logging, port utilities
│   ├── token_utils.py          # NEW: JWT decoding, formatting
│   └── storage_config.py       # NEW: Azurite constants
├── start_local_stack.py        # REFACTORED: 382 → 220 lines
├── run_integration_locally.py  # REFACTORED: 140 → 80 lines
├── get_access_token.py         # REFACTORED: 120 → 60 lines
└── run_tests_with_coverage.py  # UNCHANGED: 233 lines (no duplication)
```

---

### Phase 2: Detailed Library Specifications

#### **tools/lib/process_utils.py** (NEW)
**Purpose**: Handle all subprocess and process lifecycle management

```python
# Public API
def run_command(
    cmd: str | list[str],
    check: bool = True,
    capture_output: bool = False,
    shell: bool = False,
) -> subprocess.CompletedProcess:
    """Execute command with optional capture."""

def run_az_command(args: list[str]) -> dict[str, Any]:
    """Execute Azure CLI command and return JSON-parsed output."""

def is_port_open(host: str = "127.0.0.1", port: int, timeout: float = 0.5) -> bool:
    """Check if port is listening."""

def wait_for_port(
    host: str,
    port: int,
    timeout: float = 60.0,
    poll_interval: float = 0.2,
) -> None:
    """Poll until port is open or timeout."""

def kill_process_by_port(port: int) -> None:
    """Kill process holding port (cross-platform: Windows/Linux)."""

# ProcessManager class
class ProcessManager:
    """Track and cleanly terminate child processes."""
    def add(self, proc: subprocess.Popen) -> None: ...
    def terminate_all(self) -> None: ...
```

**Lines**: ~80  
**Dependencies**: `subprocess`, `socket`, `os`, `time`, `logging`

---

#### **tools/lib/bootstrap_utils.py** (NEW)
**Purpose**: Logging setup, bootstrap-specific utilities

```python
# Public API
def setup_logging(level: str = "DEBUG", format_str: str = "[%(levelname)s] %(message)s") -> logging.Logger:
    """Configure stderr logging for bootstrap scripts."""

def watchdog_port_binding(
    proc: subprocess.Popen,
    port: int,
    timeout: float,
) -> None:
    """Monitor process; kill if doesn't bind to port within timeout."""

def ensure_directory(path: Path) -> None:
    """Create directory with parents."""
```

**Lines**: ~40  
**Dependencies**: `logging`, `socket`, `subprocess`, `time`, `pathlib`

---

#### **tools/lib/token_utils.py** (NEW)
**Purpose**: JWT and Azure token utilities

```python
# Public API
def decode_jwt_claims(token: str) -> dict[str, Any]:
    """Decode JWT payload and return claims dict."""

def format_expiry_timestamp(timestamp: str | None) -> str:
    """Convert ISO 8601 timestamp to local timezone."""

def extract_token_from_cli_output(output: str) -> str | None:
    """Parse token from 'az account get-access-token' output."""
```

**Lines**: ~30  
**Dependencies**: `jwt`, `json`, `datetime`, `typing`

---

#### **tools/lib/storage_config.py** (NEW)
**Purpose**: Centralize Azurite/storage configuration

```python
# Public API (constants)
AZURITE_BLOB_PORT: int = 10000
AZURITE_QUEUE_PORT: int = 10001
AZURITE_TABLE_PORT: int = 10002

def dev_storage_connection_string() -> str:
    """Generate Azurite connection string."""

def dev_blob_endpoint() -> str:
    """Get Azurite blob endpoint."""
    
# ... similar for queue, table
```

**Lines**: ~15  
**Dependencies**: None (pure constants)

---

### Phase 3: Refactored Scripts

#### **tools/start_local_stack.py** (REFACTORED)

**Before**: 382 lines (large, monolithic)  
**After**: 220 lines (lean, delegating to libraries)

**Changes**:
- Remove `_kill_port_holder()` → use `process_utils.kill_process_by_port()`
- Remove `wait_for_port()` → use `process_utils.wait_for_port()`
- Remove `ensure_port_free()` → use `process_utils.is_port_open()` + `kill_process_by_port()`
- Remove `_watchdog_port_binding()` → use `bootstrap_utils.watchdog_port_binding()`
- Remove `ProcessManager` → use `process_utils.ProcessManager()`
- Keep logging config → use `bootstrap_utils.setup_logging()`
- Extract `AZURITE_PORTS` → use `storage_config`

**New structure**:
```python
from tools.lib import process_utils, bootstrap_utils, storage_config

def start_azurite(...): # 30 lines, now using shared utilities
def start_functions(...): # 35 lines, now using shared utilities
def main(...): # 65 lines
```

**Savings**: ~162 lines removed (42% reduction)

---

#### **tools/run_integration_locally.py** (REFACTORED)

**Before**: 140 lines  
**After**: 80 lines

**Changes**:
- Remove `_run()` → use `process_utils.run_command()`
- Remove `_is_port_open()` → use `process_utils.is_port_open()`
- Remove `_wait_for_table()` → use `process_utils.wait_for_port()`
- Remove `_get_access_token_via_helper()` → use `token_utils.extract_token_from_cli_output()`
- Remove port constants → use `storage_config.AZURITE_*`
- Remove connection string construction → use `storage_config.dev_storage_connection_string()`

**Savings**: ~60 lines removed (43% reduction)

---

#### **tools/get_access_token.py** (REFACTORED)

**Before**: 120 lines  
**After**: 60 lines

**Changes**:
- Remove `_run_az_command()` → use `process_utils.run_az_command()`
- Remove `_decode_claims()` → use `token_utils.decode_jwt_claims()`
- Remove `_format_expiry()` → use `token_utils.format_expiry_timestamp()`

**Savings**: ~60 lines removed (50% reduction)

---

#### **tools/run_tests_with_coverage.py** (UNCHANGED)

No significant duplication detected. This script is self-contained and focused on a single concern (coverage analysis). No refactoring needed.

---

## Metrics

| Metric | Before | After | Δ |
|--------|--------|-------|---|
| **Total Tool Lines** | 875 | 520 | -305 (-35%) |
| **Library Lines** | 0 | 165 | +165 |
| **Duplication** | 40 lines | 0 lines | -40 (-100%) |
| **Files** | 4 | 8 (4 scripts + 4 libs) | +4 |
| **Reusability** | Low | High | ✓ |

---

## SOLID Principles Applied

### **Single Responsibility**
- ✅ `process_utils.py` → only process/subprocess concerns
- ✅ `bootstrap_utils.py` → only logging/bootstrap setup
- ✅ `token_utils.py` → only JWT/token concerns
- ✅ `storage_config.py` → only storage constants

### **Open/Closed Principle**
- ✅ Libraries accept configuration (logging level, timeouts, ports) without modification
- ✅ Scripts are *closed* for modification, *open* for extension via CLI args

### **Liskov Substitution**
- ✅ `ProcessManager` maintains consistent interface (not applicable for util functions, but maintained for class)

### **Interface Segregation**
- ✅ Each library exports only necessary functions (no kitchen-sink modules)

### **Dependency Inversion**
- ✅ Scripts depend on library abstractions, not platform-specific details
- ✅ Port management, subprocess execution abstracted away

---

## DRY Improvements

| Pattern | Before | After | Status |
|---------|--------|-------|--------|
| `_run_az_command()` | 2 files (duplicate) | 1 library (shared) | ✅ |
| Port checking | 3 different styles | 1 unified API | ✅ |
| Process termination | 1 file only | All files can use | ✅ |
| Logging setup | Inline in 1 file | Reusable function | ✅ |
| JWT decoding | Only in 1 file | Reusable library | ✅ |
| Storage config | Inline constants | Centralized module | ✅ |

---

## Implementation Order

1. **Create `tools/lib/__init__.py`** (exports public API)
2. **Create `tools/lib/storage_config.py`** (no dependencies, easiest first)
3. **Create `tools/lib/token_utils.py`** (depends only on stdlib + jwt)
4. **Create `tools/lib/process_utils.py`** (depends only on stdlib)
5. **Create `tools/lib/bootstrap_utils.py`** (depends on process_utils)
6. **Create `tests/test_lib_*.py`** (unit tests for libraries)
7. **Refactor `tools/get_access_token.py`** (simplest refactor)
8. **Refactor `tools/run_integration_locally.py`** (medium complexity)
9. **Refactor `tools/start_local_stack.py`** (most complex, most to gain)
10. **Update docstrings & README** (document new library usage)

---

## Testing Strategy

- ✅ **Unit tests**: Create `tests/test_lib_process_utils.py`, etc. (mock subprocess)
- ✅ **Integration tests**: Run each refactored script to verify behavior unchanged
- ✅ **Smoke tests**: Run full local stack (`dev:start-local-stack` task) to verify port binding

---

## Breaking Changes

**None**. All scripts maintain identical CLI interfaces and behavior. This is a **pure refactoring** (internal restructuring, no API changes).

---

## Future Opportunities

Once libraries are in place:

1. **Reuse in CI/CD**: GitHub Actions workflows could potentially import and use these libraries
2. **Extend token helpers**: `token_utils` could support device code flow, refresh tokens, etc.
3. **Share with function_app.py**: Bootstrap logging setup could potentially be used in cloud functions
4. **Metrics & telemetry**: `process_utils` could emit startup metrics for observability

---

## Conclusion

This refactoring delivers:
- 🎯 **Zero duplication** (down from ~40 lines)
- 🎯 **35% smaller scripts** (880 → 520 lines)
- 🎯 **SOLID-compliant** library design
- 🎯 **Reusable components** for future scripts
- 🎯 **No breaking changes** to CLI or behavior
- 🎯 **Improved maintainability** and testability

Estimated effort: **2-3 hours** for implementation + testing.
