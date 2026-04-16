"""Canonical resource type helpers used across rules and slug lookup."""

from __future__ import annotations

import re

_AZURE_RESOURCE_TYPE_ALIASES = {
    "microsoft.resources/resourcegroups": "resource_group",
    "microsoft.storage/storageaccounts": "storage_account",
    "microsoft.keyvault/vaults": "key_vault",
    "microsoft.network/virtualnetworks": "virtual_network",
    "microsoft.network/virtualnetworks/subnets": "subnet",
    "microsoft.network/networksecuritygroups": "network_security_group",
}


def canonicalize_resource_type(resource_type: str) -> str:
    """Return the canonical internal name for a resource type."""

    cleaned = resource_type.strip().lower()
    if not cleaned:
        return ""

    alias = _AZURE_RESOURCE_TYPE_ALIASES.get(cleaned)
    if alias:
        return alias

    normalized = re.sub(r"[\s-]+", "_", cleaned)
    normalized = re.sub(r"_+", "_", normalized)
    return normalized


def normalise_resource_type(resource_type: str) -> tuple[str, str]:
    """Return canonical and human-readable variants for a resource type."""

    canonical = canonicalize_resource_type(resource_type)
    human = canonical.replace("_", " ")
    return canonical, human


__all__ = ["canonicalize_resource_type", "normalise_resource_type"]