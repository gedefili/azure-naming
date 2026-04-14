"""Shared naming rule types used by providers and runtime helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Mapping, Optional, Protocol, Sequence


class _SafeFormatDict(dict):
    """Dict that returns an empty string when formatting misses a key."""

    def __missing__(self, key: str) -> str:  # pragma: no cover - trivial
        return ""


def _normalise_context(context: Mapping[str, object]) -> _SafeFormatDict:
    normalised: Dict[str, str] = {}
    for key, value in context.items():
        if isinstance(value, str):
            normalised[key] = value
        elif value is None:
            normalised[key] = ""
        else:
            normalised[key] = str(value)
    return _SafeFormatDict(normalised)


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
    name_template: Optional[str] = None
    summary_template: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        return {
            "segments": list(self.segments),
            "max_length": self.max_length,
            "require_sanmar_prefix": self.require_sanmar_prefix,
            "display_fields": [field.to_dict() for field in self.display_fields],
            "name_template": self.name_template,
            "summary_template": self.summary_template,
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

    def render_summary(self, payload: Mapping[str, object]) -> Optional[str]:
        if not self.summary_template:
            return None
        context = _normalise_context(payload)
        for key in ("environment", "region", "system", "resourceType"):
            value = context.get(key, "")
            context[f"{key}_upper"] = value.upper()
            context[f"{key}_title"] = value.title()
        return self.summary_template.format_map(context)


class NamingRuleProvider(Protocol):
    """Contract for pluggable naming rule providers."""

    def get_rule(self, resource_type: str) -> NamingRule:
        """Return a naming rule for the given resource type."""

    def list_resource_types(self) -> Sequence[str]:
        """Enumerate resource types with explicit rule definitions."""


__all__ = ["DisplayField", "NamingRule", "NamingRuleProvider"]