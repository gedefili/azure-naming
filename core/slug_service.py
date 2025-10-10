"""Pluggable slug resolution service."""

from __future__ import annotations

import importlib
import logging
import os
from typing import Iterable, List, Optional, Protocol, Sequence

from adapters.slug import TableSlugProvider

logger = logging.getLogger(__name__)


class SlugProvider(Protocol):
    """Contract for resolving slugs for resource types."""

    def get_slug(self, resource_type: str) -> str:
        """Return the slug for the given resource type or raise ValueError if not found."""


def _validate_provider(provider: object) -> SlugProvider:
    if hasattr(provider, "get_slug"):
        return provider  # type: ignore[return-value]
    raise TypeError("Slug providers must define a 'get_slug(resource_type)' method")


def _resolve_sequence(obj: object) -> List[SlugProvider]:
    if isinstance(obj, Sequence) and not isinstance(obj, (str, bytes)):
        resolved: List[SlugProvider] = []
        for entry in obj:
            provider = entry() if callable(entry) else entry
            resolved.extend(_resolve_sequence(provider))
        return resolved
    provider_obj = obj() if callable(obj) else obj
    return [_validate_provider(provider_obj)]


def _load_providers_from_env() -> Optional[List[SlugProvider]]:
    provider_path = os.environ.get("SLUG_PROVIDER")
    if not provider_path:
        return None

    try:
        module_path, _, attr_name = provider_path.rpartition(".")
        if not module_path or not attr_name:
            raise ValueError("SLUG_PROVIDER must be in 'module.attr' format")

        module = importlib.import_module(module_path)
        attr = getattr(module, attr_name)
        providers = _resolve_sequence(attr)
        if not providers:
            raise ValueError("SLUG_PROVIDER did not yield any providers")
        return providers
    except Exception:  # pragma: no cover - defensive logging only
        logger.exception("Failed to load slug provider(s) from environment")
        return None


_default_provider = TableSlugProvider()
_providers: List[SlugProvider] = [_default_provider]

_env_providers = _load_providers_from_env()
if _env_providers:
    _providers = _env_providers


def set_slug_providers(providers: Iterable[SlugProvider]) -> None:
    """Replace the active provider chain with the supplied iterable."""

    global _providers
    new_chain = list(providers)
    if not new_chain:
        raise ValueError("At least one slug provider must be configured")
    _providers = new_chain


def register_slug_provider(provider: SlugProvider, *, prepend: bool = False) -> None:
    """Register an additional provider in the lookup chain."""

    resolved = _resolve_sequence(provider)
    if len(resolved) != 1:
        raise ValueError("register_slug_provider expects a single provider")
    validated = resolved[0]
    if prepend:
        _providers.insert(0, validated)
    else:
        _providers.append(validated)


def get_slug_providers() -> List[SlugProvider]:
    """Return a copy of the active provider chain."""

    return list(_providers)


def get_slug(resource_type: str) -> str:
    """Resolve the slug by consulting the registered providers in order."""

    last_error: Optional[Exception] = None
    for provider in _providers:
        try:
            slug = provider.get_slug(resource_type)
            if slug:
                return slug
        except Exception as exc:  # pragma: no cover - provider specific logic
            last_error = exc
    if last_error:
        raise last_error
    raise ValueError(f"Slug not found for resource type '{resource_type}'")


__all__ = [
    "SlugProvider",
    "get_slug",
    "get_slug_providers",
    "register_slug_provider",
    "set_slug_providers",
]
