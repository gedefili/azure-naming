"""Application package exposing the shared FunctionApp instance."""

from __future__ import annotations

import azure.functions as func

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

# Import route modules so decorators execute at import time
from .routes import audit as _audit_routes  # noqa: F401
from .routes import docs as _docs_routes  # noqa: F401
from .routes import names as _name_routes  # noqa: F401
from .routes import slug as _slug_routes  # noqa: F401

__all__ = ["app"]
