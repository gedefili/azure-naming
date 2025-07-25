# File: utils/slug.py
# Version: 1.0.0
# Last Modified: 2025-07-24
# Authors: ChatGPT & Geoff DeFilippi
# Summary: Lookup slug short codes for Azure resource types in Table Storage.
"""Lookup slug short codes for Azure resource types."""

import logging
import os
from typing import Optional

from azure.data.tables import TableServiceClient

_CONN_STR = os.environ.get("AzureWebJobsStorage", "")
_TABLE_NAME = "SlugMappings"
_service = TableServiceClient.from_connection_string(_CONN_STR)
_table = _service.get_table_client(_TABLE_NAME)


def get_slug(resource_type: str) -> str:
    """Retrieve the slug corresponding to a full resource type name."""
    resource_type = resource_type.lower()
    filter_query = f"FullName eq '{resource_type}'"
    try:
        entities = list(_table.query_entities(filter=filter_query))
        if entities:
            entity = entities[0]
            return entity.get("Slug") or entity.get("RowKey")
    except Exception as exc:
        logging.error(f"Failed to fetch slug for {resource_type}: {exc}")

    raise ValueError(f"Slug not found for resource type '{resource_type}'")
