# File: utils/naming_rules.py
# Version: 1.0.0
# Last Modified: 2025-07-24
# Authors: ChatGPT & Geoff DeFilippi
# Summary: Provides simple loader for resource naming rules.
"""Simple loader for resource naming rules."""

from __future__ import annotations

import importlib
import logging
import os
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Mapping, Optional, Protocol, Sequence

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DisplayField:
    """Describes how to present a field in the response payload."""

    key: str
    label: str
    description: Optional[str] = None
    optional: bool = True

    def to_dict(self) -> Dict[str, object]:  # pragma: no cover - trivial
        data: Dict[str, object] = {
            "key": self.key,
            "label": self.label,
            "optional": self.optional,
        }
        if self.description:
            data["description"] = self.description
        return data


@dataclass(frozen=True)
class NamingRule:
    """Immutable representation of a naming rule."""

    segments: Sequence[str]
    max_length: int
    require_sanmar_prefix: bool = False
    display_fields: Sequence[DisplayField] = ()
    validators: Sequence[Callable[[Mapping[str, object]], None]] = ()

    def to_dict(self) -> Dict[str, object]:
        return {
            "segments": list(self.segments),
            "max_length": self.max_length,
            "require_sanmar_prefix": self.require_sanmar_prefix,
            "display_fields": [field.to_dict() for field in self.display_fields],
        }

    def validate_payload(self, payload: Mapping[str, object]) -> None:
        for validator in self.validators:
            validator(payload)

    def render_display(self, payload: Mapping[str, object]) -> List[Dict[str, object]]:
        """Create an ordered view of response fields for end-user presentation."""

        formatted: List[Dict[str, object]] = []
        for field in self.display_fields:
            raw_value = payload.get(field.key) if isinstance(payload, Mapping) else None
            if raw_value is None and field.optional:
                continue
            entry: Dict[str, object] = {
                "key": field.key,
                "label": field.label,
                "value": None if raw_value is None else str(raw_value),
            }
            if field.description:
                entry["description"] = field.description
            formatted.append(entry)
        return formatted


class NamingRuleProvider(Protocol):
    """Contract for pluggable naming rule providers."""

    def get_rule(self, resource_type: str) -> NamingRule:
        """Return a naming rule for the given resource type."""


class DictionaryRuleProvider:
    """Default provider backed by in-memory rule dictionaries."""

    def __init__(
        self,
        default_rule: NamingRule,
        resource_rules: Mapping[str, NamingRule],
    ) -> None:
        self._default_rule = default_rule
        self._resource_rules = {key.lower(): rule for key, rule in resource_rules.items()}

    def get_rule(self, resource_type: str) -> NamingRule:  # pragma: no cover - trivial
        key = resource_type.lower()
        return self._resource_rules.get(key, self._default_rule)


def _build_display_fields(config: Optional[Iterable[Mapping[str, object]]]) -> Sequence[DisplayField]:
    fields: List[DisplayField] = []
    for item in config or DEFAULT_DISPLAY_CONFIG:
        key = str(item.get("key"))
        label = str(item.get("label", key.replace("_", " ").title()))
        description = item.get("description")
        optional = bool(item.get("optional", True))
        fields.append(
            DisplayField(
                key=key,
                label=label,
                description=str(description) if description else None,
                optional=optional,
            )
        )
    return tuple(fields)


def _build_rule(config: Mapping[str, object], fallback_segments: Iterable[str]) -> NamingRule:
    segments = tuple(config.get("segments") or fallback_segments)
    max_length = int(config.get("max_length", 80))
    require_prefix = bool(config.get("require_sanmar_prefix", False))
    display_fields = _build_display_fields(config.get("display"))
    return NamingRule(
        segments=segments,
        max_length=max_length,
        require_sanmar_prefix=require_prefix,
        display_fields=display_fields,
        validators=(),
    )


DEFAULT_RULE_CONFIG: Dict[str, object] = {
    "segments": [
        "slug",
        "system_short",
        "domain",
        "subdomain",
        "environment",
        "region",
        "index",
    ],
    "max_length": 80,
    "require_sanmar_prefix": False,
    "display": [
        {"key": "name", "label": "Resource Name", "optional": False},
        {"key": "resourceType", "label": "Resource Type", "optional": False},
        {"key": "slug", "label": "Slug", "optional": False},
        {"key": "region", "label": "Region", "optional": False},
        {"key": "environment", "label": "Environment", "optional": False},
        {"key": "project", "label": "Project"},
        {"key": "purpose", "label": "Purpose"},
        {"key": "system", "label": "System"},
        {"key": "index", "label": "Index"},
    ],
}

RESOURCE_RULE_CONFIG: Dict[str, Dict[str, object]] = {
    "storage_account": {
        "segments": DEFAULT_RULE_CONFIG["segments"],
        "max_length": 24,
        "require_sanmar_prefix": True,
        "display": [
            {"key": "name", "label": "Storage Account Name", "optional": False},
            {"key": "resourceType", "label": "Resource Type", "optional": False},
            {"key": "slug", "label": "Slug", "optional": False},
            {"key": "environment", "label": "Environment", "optional": False},
            {"key": "region", "label": "Region", "optional": False},
            {"key": "project", "label": "Project"},
            {"key": "purpose", "label": "Purpose"},
            {"key": "system", "label": "System"},
            {"key": "index", "label": "Index"},
        ],
    }
}

DEFAULT_DISPLAY_CONFIG: Sequence[Mapping[str, object]] = tuple(DEFAULT_RULE_CONFIG["display"])

DEFAULT_RULE = _build_rule(DEFAULT_RULE_CONFIG, DEFAULT_RULE_CONFIG["segments"])
RESOURCE_RULES = {
    key: _build_rule(config, DEFAULT_RULE.segments)
    for key, config in RESOURCE_RULE_CONFIG.items()
}


_provider: NamingRuleProvider = DictionaryRuleProvider(DEFAULT_RULE, RESOURCE_RULES)


def _load_provider_from_env() -> Optional[NamingRuleProvider]:
    provider_path = os.environ.get("NAMING_RULE_PROVIDER")
    if not provider_path:
        return None

    try:
        module_path, _, attr_name = provider_path.rpartition(".")
        if not module_path or not attr_name:
            raise ValueError("NAMING_RULE_PROVIDER must be in 'module.attr' format")

        module = importlib.import_module(module_path)
        factory = getattr(module, attr_name)
        provider = factory() if callable(factory) else factory
        if not hasattr(provider, "get_rule"):
            raise TypeError("Provider must define a 'get_rule' method")
        return provider  # type: ignore[return-value]
    except Exception:  # pragma: no cover - defensive logging only
        logger.exception("Failed to load naming rule provider from environment")
        return None


_env_provider = _load_provider_from_env()
if _env_provider:
    _provider = _env_provider


def set_rule_provider(provider: NamingRuleProvider) -> None:
    """Override the active naming rule provider at runtime."""

    global _provider
    _provider = provider


def get_rule_provider() -> NamingRuleProvider:
    """Return the currently active naming rule provider."""

    return _provider


def load_naming_rule(resource_type: str) -> NamingRule:
    """Return the naming rule for the requested resource type."""

    return _provider.get_rule(resource_type)
