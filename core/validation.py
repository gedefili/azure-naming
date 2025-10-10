"""Validation helpers for generated resource names."""

from __future__ import annotations

import re
from typing import Any


def _get_rule_value(rule: Any, key: str, default: int) -> int:
    if hasattr(rule, key):
        return int(getattr(rule, key))
    if isinstance(rule, dict):
        return int(rule.get(key, default))
    return default


def validate_name(name: str, rule) -> None:
    """Raise :class:`ValueError` when the generated name violates policy."""

    max_length = _get_rule_value(rule, "max_length", 80)

    if len(name) > max_length:
        raise ValueError(f"Name '{name}' exceeds maximum length of {max_length} characters.")

    if not name.islower():
        raise ValueError("Name must be lowercase.")

    if not re.fullmatch(r"[a-z0-9-]+", name):
        raise ValueError("Name may only contain lowercase letters, numbers, and hyphens.")
