# File: utils/naming_rules.py
# Version: 1.0.0
# Last Modified: 2025-07-24
# Authors: ChatGPT & Geoff DeFilippi
# Summary: Provides simple loader for resource naming rules.
"""Simple loader for resource naming rules."""

from typing import Dict

# Basic default rule used for most resources
DEFAULT_RULE: Dict[str, object] = {
    "segments": ["slug", "system_short", "domain", "subdomain", "environment", "region", "index"],
    "max_length": 80,
    "require_sanmar_prefix": False,
}

# Specific overrides for known resource types
RESOURCE_RULES: Dict[str, Dict[str, object]] = {
    "storage_account": {
        "segments": DEFAULT_RULE["segments"],
        "max_length": 24,
        "require_sanmar_prefix": True,
    }
}


def load_naming_rule(resource_type: str) -> Dict[str, object]:
    """Return the naming rule dictionary for the requested resource type."""
    key = resource_type.lower()
    return RESOURCE_RULES.get(key, DEFAULT_RULE)
