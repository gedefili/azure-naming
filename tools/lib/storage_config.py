"""Azure storage configuration for local development.

Centralized constants and helpers for Azurite and Azure Storage configuration
used across tool scripts. Supports local development with Azurite emulator.
"""

from __future__ import annotations

# Azurite port constants
AZURITE_BLOB_PORT: int = 10000
AZURITE_QUEUE_PORT: int = 10001
AZURITE_TABLE_PORT: int = 10002

# Default development storage account
DEVSTORE_ACCOUNT_NAME: str = "devstoreaccount1"
DEVSTORE_ACCOUNT_KEY: str = "Eby8vdM02xNOcqFe4d01+EXAMPLETESTKEY=="


def dev_storage_connection_string() -> str:
    """Generate Azurite connection string for local development.

    Returns:
        Connection string for local Azurite endpoints.

    Example:
        "DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;..."
    """
    return (
        f"DefaultEndpointsProtocol=http;"
        f"AccountName={DEVSTORE_ACCOUNT_NAME};"
        f"AccountKey={DEVSTORE_ACCOUNT_KEY};"
        f"BlobEndpoint=http://127.0.0.1:{AZURITE_BLOB_PORT}/{DEVSTORE_ACCOUNT_NAME};"
        f"QueueEndpoint=http://127.0.0.1:{AZURITE_QUEUE_PORT}/{DEVSTORE_ACCOUNT_NAME};"
        f"TableEndpoint=http://127.0.0.1:{AZURITE_TABLE_PORT}/{DEVSTORE_ACCOUNT_NAME};"
    )


def dev_blob_endpoint() -> str:
    """Get Azurite blob service endpoint."""
    return f"http://127.0.0.1:{AZURITE_BLOB_PORT}/{DEVSTORE_ACCOUNT_NAME}"


def dev_queue_endpoint() -> str:
    """Get Azurite queue service endpoint."""
    return f"http://127.0.0.1:{AZURITE_QUEUE_PORT}/{DEVSTORE_ACCOUNT_NAME}"


def dev_table_endpoint() -> str:
    """Get Azurite table service endpoint."""
    return f"http://127.0.0.1:{AZURITE_TABLE_PORT}/{DEVSTORE_ACCOUNT_NAME}"
