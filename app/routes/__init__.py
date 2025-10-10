"""Route modules registered with the shared FunctionApp."""

from . import audit, docs, names, slug  # noqa: F401

__all__ = ["audit", "docs", "names", "slug"]
