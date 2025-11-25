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
        excess = len(name) - max_length
        raise ValueError(
            f"Name '{name}' exceeds character limit. "
            f"Length: {len(name)} characters, Limit: {max_length} characters, "
            f"Over by: {excess} character{'s' if excess != 1 else ''}. "
            f"Please shorten the system, subsystem, project, or purpose fields."
        )

    if not name.islower():
        raise ValueError(f"Name '{name}' must be lowercase. Found uppercase or non-alphabetic characters.")

    if not re.fullmatch(r"[a-z0-9-]+", name):
        invalid_chars = set(c for c in name if not re.fullmatch(r"[a-z0-9-]", c))
        raise ValueError(
            f"Name '{name}' contains invalid characters: {', '.join(sorted(invalid_chars))}. "
            f"Only lowercase letters (a-z), numbers (0-9), and hyphens (-) are allowed."
        )
