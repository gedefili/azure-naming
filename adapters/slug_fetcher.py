"""Fetch Azure resource abbreviations from the Microsoft Cloud Adoption Framework."""

from __future__ import annotations

import logging
import re
from typing import Dict

import requests

# Official Microsoft CAF resource abbreviations (raw markdown from GitHub)
CAF_ABBREVIATIONS_URL = (
    "https://raw.githubusercontent.com/MicrosoftDocs/cloud-adoption-framework/"
    "main/docs/ready/azure-best-practices/resource-abbreviations.md"
)

# Matches markdown table rows: | Resource name | `Provider/namespace` | `abbr` |
_TABLE_ROW = re.compile(
    r"\|\s*(.+?)\s*\|\s*`([^`]+)`\s*\|\s*`([^`]+)`\s*\|?"
)

LOCAL_SLUG_OVERRIDES = {
    "app": "app_service",
    "ca": "container_app",
    "cae": "container_app_environment",
    "cr": "container_registry",
    "cosmos": "cosmosdb_account",
    "id": "managed_identity",
    "pdnsz": "private_dns_zone",
    "pip": "public_ip_address",
    "snet": "subnet",
    "sql": "sql_server",
    "sqldb": "sql_database",
}


def _to_snake_case(name: str) -> str:
    """Convert a human-readable resource name to snake_case identifier."""
    # Strip parenthetical qualifiers like "(OS)", "(internal)"
    name = re.sub(r"\s*\([^)]*\)\s*", " ", name)
    # Replace non-alphanumeric runs with a single underscore
    name = re.sub(r"[^a-zA-Z0-9]+", "_", name.strip())
    name = re.sub(r"_+", "_", name).strip("_")
    return name.lower()


class SlugSourceError(RuntimeError):
    """Raised when slug definitions cannot be loaded from the upstream source."""


def get_all_remote_slugs() -> Dict[str, str]:
    """Return a mapping of abbreviation → resource type from Microsoft CAF."""

    try:
        logging.info("Fetching resource abbreviations from Microsoft CAF...")
        response = requests.get(CAF_ABBREVIATIONS_URL, timeout=15)
        response.raise_for_status()
        md_text = response.text

        slug_map: Dict[str, str] = {}

        for match in _TABLE_ROW.finditer(md_text):
            resource_name, _provider, abbreviation = match.groups()
            # Skip header separators and placeholder abbreviations
            if abbreviation.startswith("-") or "*" in abbreviation:
                continue
            resource_type = _to_snake_case(resource_name)
            if resource_type and abbreviation:
                slug_map[abbreviation] = resource_type

        if not slug_map:
            raise ValueError(
                "No abbreviation entries parsed from the CAF markdown"
            )

        # Preserve the naming service's canonical resource type identifiers for
        # abbreviations that differ from the CAF labels.
        for slug, resource_type in LOCAL_SLUG_OVERRIDES.items():
            slug_map[slug] = resource_type

        logging.info("Parsed %s slug mappings from Microsoft CAF.", len(slug_map))
        return slug_map
    except Exception as exc:
        logging.exception("Failed to fetch or parse Microsoft CAF abbreviations.")
        raise SlugSourceError(
            "Unable to load slug definitions from Microsoft CAF"
        ) from exc
