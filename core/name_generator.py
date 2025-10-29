# File: core/name_generator.py
# Version: 1.0.0
# Created: 2025-07-24
# Last Modified: 2025-07-24
# Authors: ChatGPT & Geoff DeFilippi
# Summary: Utility to assemble a compliant Azure resource name based on rules and slug.

from __future__ import annotations

import re
from typing import Iterable, Mapping

from core.naming_rules import _normalise_context


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


def _template_context(region: str, environment: str, slug: str, optional_inputs: Mapping[str, str], require_prefix: bool = False) -> Mapping[str, str]:
    context: dict[str, str] = {
        "region": region,
        "environment": environment,
        "slug": slug,
        "sanmar_prefix": "sanmar" if require_prefix else "",
    }
    context.update(optional_inputs)
    for key, value in list(optional_inputs.items()):
        context[f"{key}_segment"] = f"-{value}" if value else ""
    return context


def _apply_prefix(name: str, rule) -> str:
    if _require_prefix(rule) and not name.startswith("sanmar"):
        return f"sanmar-{name}"
    return name


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
    
    require_prefix = _require_prefix(rule)
    template = getattr(rule, "name_template", None)

    if template:
        context = _normalise_context(_template_context(region, environment, slug, optional_inputs, require_prefix))
        try:
            rendered = template.format_map(context)
        except KeyError as exc:  # pragma: no cover - defensive, tested via InvalidRequestError
            missing = exc.args[0]
            raise ValueError(f"name_template references unknown placeholder '{missing}'") from exc
        rendered = re.sub(r"-{2,}", "-", rendered.strip("-"))
        name = rendered.lower()
        # Only apply auto-prefix if template doesn't already include sanmar_prefix
        if require_prefix and "{sanmar_prefix}" not in template and not name.startswith("sanmar"):
            return f"sanmar-{name}"
        return name

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

    return _apply_prefix(name, rule)
