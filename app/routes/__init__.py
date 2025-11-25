"""Route modules registered with the shared FunctionApp."""

from . import audit, docs, names, rules, slug  # noqa: F401

__all__ = ["audit", "docs", "names", "rules", "slug"]
