"""Azure Functions entry point exposing the shared FunctionApp instance."""

from __future__ import annotations

from app import app

__all__ = ["app"]