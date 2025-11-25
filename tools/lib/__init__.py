"""Tools library for Azure Naming Scripts.

Provides reusable utilities for subprocess execution, port management,
logging, JWT handling, and storage configuration. Follows SOLID principles
with zero code duplication.
"""

# process_utils exports
from tools.lib.process_utils import (
    ProcessManager,
    is_port_open,
    kill_process_by_port,
    run_az_command,
    run_command,
    wait_for_port,
)

# bootstrap_utils exports
from tools.lib.bootstrap_utils import (
    ensure_directory,
    setup_logging,
    watchdog_port_binding,
)

# token_utils exports
from tools.lib.token_utils import (
    decode_jwt_claims,
    extract_token_from_cli_output,
    format_expiry_timestamp,
)

# storage_config exports
from tools.lib.storage_config import (
    AZURITE_BLOB_PORT,
    AZURITE_QUEUE_PORT,
    AZURITE_TABLE_PORT,
    DEVSTORE_ACCOUNT_KEY,
    DEVSTORE_ACCOUNT_NAME,
    dev_blob_endpoint,
    dev_queue_endpoint,
    dev_storage_connection_string,
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
    "DEVSTORE_ACCOUNT_KEY",
    "DEVSTORE_ACCOUNT_NAME",
    "dev_storage_connection_string",
    "dev_blob_endpoint",
    "dev_queue_endpoint",
    "dev_table_endpoint",
]
