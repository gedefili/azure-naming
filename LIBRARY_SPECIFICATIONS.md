# Library Specifications for Tools Refactoring

This document provides detailed API specifications for the new `tools/lib/` modules.

## Overview

Four new modules will be created to eliminate duplication and follow SOLID principles:

```
tools/lib/
├── __init__.py               # Public API exports
├── process_utils.py          # Subprocess & port management
├── bootstrap_utils.py        # Logging & watchdog setup
├── token_utils.py            # JWT & token handling
└── storage_config.py         # Azurite constants
```

---

## 1. `tools/lib/process_utils.py`

**Purpose**: Centralized subprocess execution and port lifecycle management.

**Key Responsibilities**:
- Execute commands with error handling
- Check port availability
- Wait for ports to open (polling)
- Kill processes by port (cross-platform)
- Manage process lifecycle (start, track, terminate)

### Public API

```python
# Subprocess execution
def run_command(
    cmd: str | list[str],
    check: bool = True,
    capture_output: bool = False,
    shell: bool = False,
    text: bool = True,
) -> subprocess.CompletedProcess:
    """Execute a command.
    
    Args:
        cmd: Command as string or list of args
        check: Raise on non-zero exit code
        capture_output: Capture stdout/stderr
        shell: Run through shell
        text: Return str instead of bytes
        
    Returns:
        CompletedProcess with returncode, stdout, stderr
        
    Raises:
        subprocess.CalledProcessError: If check=True and command fails
    """

def run_az_command(args: list[str]) -> dict[str, Any]:
    """Execute Azure CLI command and return JSON output.
    
    Args:
        args: Args to pass to 'az' (without 'az' prefix, without '-o json')
        
    Returns:
        Parsed JSON response from Azure CLI
        
    Raises:
        RuntimeError: If Azure CLI not installed or command fails
    """

# Port management
def is_port_open(
    host: str = "127.0.0.1",
    port: int = 7071,
    timeout: float = 0.5,
) -> bool:
    """Check if a port is open (socket connection succeeds).
    
    Args:
        host: Hostname/IP to connect to
        port: Port number
        timeout: Connection timeout in seconds
        
    Returns:
        True if port is open, False otherwise
    """

def wait_for_port(
    host: str,
    port: int,
    timeout: float = 60.0,
    poll_interval: float = 0.2,
    logger: logging.Logger | None = None,
) -> None:
    """Poll until port opens or timeout.
    
    Args:
        host: Hostname to connect to
        port: Port number
        timeout: Max wait time in seconds
        poll_interval: Time between checks
        logger: Optional logger for debug messages
        
    Raises:
        TimeoutError: If port doesn't open within timeout
    """

def kill_process_by_port(port: int, logger: logging.Logger | None = None) -> None:
    """Kill process holding the port (cross-platform).
    
    Supports:
    - Windows: Uses 'netstat -ano | findstr' + 'taskkill /F /PID'
    - Linux/macOS: Uses 'lsof -ti' + 'kill -9'
    
    Args:
        port: Port number to free
        logger: Optional logger for debug messages
        
    Logs errors but does not raise on failure (best-effort cleanup).
    """

# Process management
class ProcessManager:
    """Track and cleanly terminate child processes."""
    
    def __init__(self) -> None:
        """Initialize empty process list."""
    
    def add(self, proc: subprocess.Popen) -> None:
        """Add process to tracking list.
        
        Args:
            proc: Process object from subprocess.Popen()
        """
    
    def terminate_all(self) -> None:
        """Terminate all tracked processes gracefully.
        
        First sends SIGTERM to all processes in reverse order,
        then waits up to 5 seconds. If any survive, sends SIGKILL.
        """
```

### Example Usage

```python
from tools.lib import process_utils

# Check port availability
if process_utils.is_port_open(port=7071):
    print("Port 7071 is already in use")

# Wait for port to open
process_utils.wait_for_port("127.0.0.1", 7071, timeout=30)

# Kill process using port
process_utils.kill_process_by_port(7071)

# Run Azure CLI command
token_info = process_utils.run_az_command(["account", "show", "-o", "json"])

# Manage child processes
pm = process_utils.ProcessManager()
proc = subprocess.Popen(["func", "start"])
pm.add(proc)
# ... later ...
pm.terminate_all()
```

---

## 2. `tools/lib/bootstrap_utils.py`

**Purpose**: Bootstrap script utilities (logging, watchdog, directories).

**Key Responsibilities**:
- Configure logging for tools
- Monitor process port binding with timeout
- Ensure directory exists

### Public API

```python
# Logging
def setup_logging(
    level: str | int = logging.DEBUG,
    format_str: str = "[%(levelname)s] %(message)s",
    stream = sys.stderr,
) -> logging.Logger:
    """Configure and return root logger.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
        format_str: Log message format
        stream: Output stream (default: stderr)
        
    Returns:
        Configured root logger instance
    """

# Port binding watchdog
def watchdog_port_binding(
    proc: subprocess.Popen,
    port: int,
    timeout: float,
    logger: logging.Logger | None = None,
) -> None:
    """Monitor process; kill if doesn't bind to port within timeout.
    
    Runs in a background thread. Polls port every 0.5 seconds.
    Logs progress every 20 checks (~10 seconds).
    
    Args:
        proc: Process object to monitor
        port: Expected port to bind to
        timeout: Max wait time in seconds
        logger: Optional logger
        
    Raises:
        TimeoutError: If port not bound after timeout (kills process first)
    """

# File system
def ensure_directory(path: Path) -> None:
    """Create directory with parents (like mkdir -p).
    
    Args:
        path: Directory path to create
    """
```

### Example Usage

```python
from tools.lib import bootstrap_utils
import threading

# Setup logging
logger = bootstrap_utils.setup_logging(level="DEBUG")

# Create directory
bootstrap_utils.ensure_directory(Path(".azurite"))

# Watch a process for port binding
proc = subprocess.Popen(["func", "start"])
watchdog = threading.Thread(
    target=bootstrap_utils.watchdog_port_binding,
    args=(proc, 7071, 40),  # Timeout after 40 seconds
    daemon=True,
)
watchdog.start()
```

---

## 3. `tools/lib/token_utils.py`

**Purpose**: JWT token utilities for Azure authentication.

**Key Responsibilities**:
- Decode JWT payload
- Format expiry timestamps
- Parse tokens from command output

### Public API

```python
# JWT handling
def decode_jwt_claims(token: str) -> dict[str, Any]:
    """Decode JWT and return claims dictionary.
    
    Extracts the payload section of the JWT, base64-decodes it,
    and returns the JSON claims dict.
    
    Args:
        token: JWT token string (format: header.payload.signature)
        
    Returns:
        Decoded claims dictionary
        
    Raises:
        ValueError: If token format is invalid
        json.JSONDecodeError: If payload is not valid JSON
    """

def format_expiry_timestamp(timestamp: str | None) -> str:
    """Convert ISO 8601 timestamp to local timezone string.
    
    Azure CLI returns timestamps like "2025-10-29T14:30:00.000000+00:00"
    or sometimes without timezone info. This converts to local time
    and returns ISO format string.
    
    Args:
        timestamp: ISO 8601 timestamp string (or None)
        
    Returns:
        Formatted timestamp in local timezone, or "unknown" if None
    """

def extract_token_from_cli_output(output: str) -> str | None:
    """Parse bearer token from 'az account get-access-token' output.
    
    The output contains the token between markers:
    "=== Bearer Token ===\n<token>\n=== End Token ==="
    
    Args:
        output: Stdout from get_access_token script
        
    Returns:
        Token string if found, None otherwise
    """
```

### Example Usage

```python
from tools.lib import token_utils
import json

# Decode JWT
token = "eyJ..."
claims = token_utils.decode_jwt_claims(token)
print(f"Token expiry: {claims.get('exp')}")

# Format timestamp
expires = token_utils.format_expiry_timestamp("2025-10-29T14:30:00+00:00")
print(f"Expires: {expires}")

# Extract token from script output
token = token_utils.extract_token_from_cli_output(script_stdout)
if token:
    print("Token extracted successfully")
```

---

## 4. `tools/lib/storage_config.py`

**Purpose**: Centralize Azurite/storage configuration constants.

**Key Responsibilities**:
- Define port constants
- Build connection strings
- Generate endpoint URLs

### Public API

```python
# Port constants
AZURITE_BLOB_PORT: int = 10000
AZURITE_QUEUE_PORT: int = 10001
AZURITE_TABLE_PORT: int = 10002

# Connection strings
def dev_storage_connection_string() -> str:
    """Generate Azurite connection string for local development.
    
    Returns:
        Connection string: "DefaultEndpointsProtocol=http;..."
        
    Example:
        "DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;..."
    """

# Endpoints
def dev_blob_endpoint() -> str:
    """Get Azurite blob service endpoint."""

def dev_queue_endpoint() -> str:
    """Get Azurite queue service endpoint."""

def dev_table_endpoint() -> str:
    """Get Azurite table service endpoint."""

def set_endpoints_in_env() -> None:
    """Set AzureWebJobsStorage and related env vars for local development."""
```

### Example Usage

```python
from tools.lib import storage_config
import os

# Get port constants
print(f"Table port: {storage_config.AZURITE_TABLE_PORT}")

# Set environment for local testing
os.environ["AzureWebJobsStorage"] = storage_config.dev_storage_connection_string()

# Get individual endpoints
table_url = storage_config.dev_table_endpoint()
blob_url = storage_config.dev_blob_endpoint()
```

---

## 5. `tools/lib/__init__.py`

**Purpose**: Public API exports for the library package.

### Public API

```python
"""Tools library for Azure Naming Scripts."""

# process_utils exports
from tools.lib.process_utils import (
    run_command,
    run_az_command,
    is_port_open,
    wait_for_port,
    kill_process_by_port,
    ProcessManager,
)

# bootstrap_utils exports
from tools.lib.bootstrap_utils import (
    setup_logging,
    watchdog_port_binding,
    ensure_directory,
)

# token_utils exports
from tools.lib.token_utils import (
    decode_jwt_claims,
    format_expiry_timestamp,
    extract_token_from_cli_output,
)

# storage_config exports
from tools.lib.storage_config import (
    AZURITE_BLOB_PORT,
    AZURITE_QUEUE_PORT,
    AZURITE_TABLE_PORT,
    dev_storage_connection_string,
    dev_blob_endpoint,
    dev_queue_endpoint,
    dev_table_endpoint,
)

__all__ = [
    # process_utils
    "run_command",
    "run_az_command",
    "is_port_open",
    "wait_for_port",
    "kill_process_by_port",
    "ProcessManager",
    # bootstrap_utils
    "setup_logging",
    "watchdog_port_binding",
    "ensure_directory",
    # token_utils
    "decode_jwt_claims",
    "format_expiry_timestamp",
    "extract_token_from_cli_output",
    # storage_config
    "AZURITE_BLOB_PORT",
    "AZURITE_QUEUE_PORT",
    "AZURITE_TABLE_PORT",
    "dev_storage_connection_string",
    "dev_blob_endpoint",
    "dev_queue_endpoint",
    "dev_table_endpoint",
]
```

### Usage Examples

```python
# Can import from package
from tools.lib import (
    run_az_command,
    wait_for_port,
    decode_jwt_claims,
    AZURITE_TABLE_PORT,
)

# Or from submodules
from tools.lib.process_utils import ProcessManager
from tools.lib.token_utils import format_expiry_timestamp
```

---

## Dependency Graph

```
storage_config.py
    ↓ (no dependencies)

token_utils.py
    ↓ (depends on: jwt, json, datetime)

process_utils.py
    ↓ (depends on: subprocess, socket, os, time, logging)

bootstrap_utils.py
    ↓ (depends on: process_utils, socket, subprocess, time, logging, pathlib)

__init__.py
    ↓ (depends on: all above modules)
```

**Build Order**:
1. `storage_config.py` (no dependencies)
2. `token_utils.py` (only stdlib + jwt)
3. `process_utils.py` (only stdlib)
4. `bootstrap_utils.py` (depends on process_utils)
5. `__init__.py` (depends on all)

---

## Testing Strategy

Each module should have corresponding tests in `tests/test_lib_*.py`:

- `tests/test_lib_process_utils.py`: Mock subprocess, test port checking, process management
- `tests/test_lib_bootstrap_utils.py`: Mock subprocess, test logging, watchdog timeout
- `tests/test_lib_token_utils.py`: Test JWT decoding, timestamp formatting, token extraction
- `tests/test_lib_storage_config.py`: Verify constants, connection string format

**Approach**:
- Use `unittest.mock` to mock subprocess calls
- Test both success and error paths
- Verify cross-platform handling (Windows vs Linux)

---

## Migration Guide

### Before (Monolithic)

```python
# tools/start_local_stack.py - 382 lines
def _kill_port_holder(port: int) -> None:
    # ... 20 lines of platform-specific code

def _run_az_command(args: list[str]) -> Dict[str, Any]:
    # ... 15 lines of subprocess logic

def wait_for_port(host: str, port: int, timeout: float) -> None:
    # ... 15 lines of polling logic
```

### After (Modular)

```python
# tools/start_local_stack.py - 220 lines
from tools.lib import (
    kill_process_by_port,
    run_az_command,
    wait_for_port,
    setup_logging,
)

logger = setup_logging()
kill_process_by_port(7071)
wait_for_port("127.0.0.1", 7071)
token = run_az_command(["account", "get-access-token"])
```

---

## Summary Table

| Module | Lines | Exports | Dependencies |
|--------|-------|---------|--------------|
| `process_utils.py` | ~80 | 6 | stdlib |
| `bootstrap_utils.py` | ~40 | 3 | stdlib + process_utils |
| `token_utils.py` | ~30 | 3 | stdlib + jwt |
| `storage_config.py` | ~15 | 8 | None |
| `__init__.py` | ~15 | 20 | All submodules |
| **Total** | **~180** | **20 exports** | - |

---

## Future Extensions

Once libraries are established, they could support:

1. **Metrics & Telemetry**: Add timing/logging to `ProcessManager`
2. **Device Code Flow**: Extend `token_utils` for interactive auth
3. **Config Files**: Load Azurite config from YAML in `storage_config`
4. **Retry Logic**: Add exponential backoff to `wait_for_port`
5. **Health Checks**: Extend bootstrap to verify health endpoints
