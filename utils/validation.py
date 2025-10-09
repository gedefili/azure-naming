# File: utils/validation.py
# Version: 1.0.0
# Created: 2025-07-24
# Last Modified: 2025-07-24
# Authors: ChatGPT & Geoff DeFilippi
# Summary: Validates that names meet length, casing, and format requirements.

import re
from typing import Any


def _get_rule_value(rule: Any, key: str, default: int) -> int:
    if hasattr(rule, key):
        return int(getattr(rule, key))
    if isinstance(rule, dict):
        return int(rule.get(key, default))
    return default

def validate_name(name: str, rule) -> None:
    """
    Raises ValueError if the name does not meet policy.
    Checks:
    - Max length
    - Lowercase
    - Dash-separated
    
    Parameters:
    - name: the generated resource name string
    - rule: the rule definition (dict-like or NamingRule) with validation constraints
    """
    max_length = _get_rule_value(rule, "max_length", 80)

    if len(name) > max_length:
        raise ValueError(f"Name '{name}' exceeds maximum length of {max_length} characters.")

    if not name.islower():
        raise ValueError(f"Name '{name}' must be all lowercase.")

    if not re.match(r'^[a-z0-9-]+$', name):
        raise ValueError(f"Name '{name}' contains invalid characters. Only a-z, 0-9, and dashes are allowed.")
