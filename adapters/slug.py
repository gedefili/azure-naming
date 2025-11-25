"""Table-backed slug lookup helpers and a default provider.

This module provides a small Table-backed provider used by the core slug
service and by tests. It intentionally keeps logic minimal so unit tests
can monkeypatch the table client when the Azure SDK is not available.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from adapters import storage as _storage

TABLE_NAME = "SlugMappings"
PARTITION_KEY = "slug"


class TableSlugProvider:
    """Provider that resolves slugs from the SlugMappings table.

    The provider exposes a get_slug(resource_type) method which returns the
    canonical slug for a resource type (or raises ValueError when not found).
    """

    def __init__(self) -> None:
        self._table = None

    def _ensure_table(self):
        if self._table is None:
            self._table = get_table_client(TABLE_NAME)
        return self._table

    def get_slug(self, resource_type: str) -> str:
        return get_slug(resource_type)


def get_table_client(table_name: str = TABLE_NAME):
    """Return a table client for the slug mappings table.

    This function exists so tests can monkeypatch it with a fake table client.
    It delegates to the storage adapter to obtain a TableClient instance.
    """

    return _storage.get_table_client(table_name)


def _normalise_resource_type(resource_type: str) -> tuple[str, str]:
    """Return a tuple of (canonical, human_readable) variants for lookup.

    canonical: underscores, lower-case (e.g. 'resource_group')
    human_readable: spaces, lower-case (e.g. 'resource group')
    
    Note: Input validation and OData escaping happens in get_slug().
    """

    canonical = resource_type.replace(" ", "_").lower()
    human = resource_type.replace("_", " ").lower()
    return canonical, human


def _escape_odata_string(value: str) -> str:
    """Escape a string for safe use in OData filter expressions.
    
    OData string literals use single quotes and escape by doubling.
    This prevents OData injection attacks like: ' or '1'='1
    """
    return value.replace("'", "''")


def get_slug(resource_type: str) -> str:
    """Resolve a slug for the supplied resource_type.

    The function attempts to locate a matching row in the SlugMappings table
    by FullName (which stores the resource type name from the upstream source).
    
    Uses proper OData escaping to prevent injection attacks.
    """

    canonical, human = _normalise_resource_type(resource_type)
    table = get_table_client(TABLE_NAME)

    # Build OData filter with proper escaping
    # FullName is stored as the canonical name (e.g., 'storage_account')
    # OData escaping (doubling single quotes) prevents injection
    escaped_canonical = _escape_odata_string(canonical)
    filter_str = f"FullName eq '{escaped_canonical}'"
    
    entities = list(table.query_entities(filter_str))
    if not entities:
        raise ValueError(f"Slug not found for resource type '{resource_type}'")

    first = entities[0]
    slug = first.get("Slug") or first.get("RowKey")
    if not slug:
        raise ValueError("Slug entity missing 'Slug' value")
    return slug


__all__ = ["TableSlugProvider", "get_slug", "get_table_client"]
