"""Adapter for resolving resource slugs from storage."""

from __future__ import annotations

import logging

from adapters.storage import get_table_client

_TABLE_NAME = "SlugMappings"


class TableSlugProvider:
    """Resolve slugs using Azure Table Storage."""

    def __init__(self, table_name: str = _TABLE_NAME) -> None:
        self._table_name = table_name

    def get_slug(self, resource_type: str) -> str:
        resource_type = resource_type.lower()
        candidates = self._build_candidates(resource_type)

        try:
            table = get_table_client(self._table_name)
            for candidate in candidates:
                escaped = candidate.replace("'", "''")
                filter_query = f"(ResourceType eq '{escaped}') or (FullName eq '{escaped}')"
                entities = list(table.query_entities(query_filter=filter_query))
                if entities:
                    entity = entities[0]
                    return entity.get("Slug") or entity.get("RowKey")
        except Exception as exc:  # pragma: no cover - defensive logging
            logging.error("Failed to fetch slug for %s: %s", resource_type, exc)

        raise ValueError(f"Slug not found for resource type '{resource_type}'")

    @staticmethod
    def _build_candidates(resource_type: str) -> list[str]:
        candidates = [resource_type]
        underscore_variant = resource_type.replace(" ", "_")
        space_variant = resource_type.replace("_", " ")
        for variant in (underscore_variant, space_variant):
            if variant not in candidates:
                candidates.append(variant)
        return candidates


_default_provider = TableSlugProvider()


def get_slug(resource_type: str) -> str:
    """Backward compatible helper that delegates to the default table-backed provider."""

    return _default_provider.get_slug(resource_type)


__all__ = ["TableSlugProvider", "get_slug"]
