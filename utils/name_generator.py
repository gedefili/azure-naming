# File: utils/name_generator.py
# Version: 1.0.0
# Created: 2025-07-24
# Last Modified: 2025-07-24
# Authors: ChatGPT & Geoff DeFilippi
# Summary: Utility to assemble a compliant Azure resource name based on rules and slug.

from typing import Iterable, Mapping


def _get_segments(rule) -> Iterable[str]:
    if hasattr(rule, "segments"):
        return getattr(rule, "segments")
    if isinstance(rule, Mapping):
        return rule.get("segments", [])
    return []


def _require_prefix(rule) -> bool:
    if hasattr(rule, "require_sanmar_prefix"):
        return bool(getattr(rule, "require_sanmar_prefix"))
    if isinstance(rule, Mapping):
        return bool(rule.get("require_sanmar_prefix", False))
    return False


def build_name(region, environment, slug, rule, optional_inputs):
    """
    Build a resource name following the provided naming rule and inputs.
    
    Parameters:
    - region: The Azure region short code (e.g., "wus2")
    - environment: Environment code (e.g., "prod")
    - slug: The resource type short code (e.g., "st" for storage)
    - rule: The naming rule dict that includes segment order and constraints
    - optional_inputs: dict of optional segments like system_short, domain, subdomain, index

    Returns:
    - Fully assembled name string
    """
    parts = []

    # Define known fields and fallback to blank if not supplied
    for segment in _get_segments(rule):
        if segment == "region":
            parts.append(region)
        elif segment == "environment":
            parts.append(environment)
        elif segment == "slug":
            parts.append(slug)
        elif segment in optional_inputs:
            value = optional_inputs.get(segment, "")
            parts.append(value)

    name = "-".join(filter(None, parts)).lower()

    if _require_prefix(rule):
        if not name.startswith("sanmar"):
            name = f"sanmar-{name}"

    return name
