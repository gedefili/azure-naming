"""Application package exposing the shared FunctionApp instance.

The FunctionApp is configured with FUNCTION-level authentication, which requires
Azure EasyAuth (built-in authentication) to be enabled. All requests must include
valid authentication headers. Individual endpoints use custom require_role() checks
to implement RBAC.

This prevents accidental public exposure if a developer forgets to add require_role()
to a new endpoint.
"""

from __future__ import annotations

import azure.functions as func

# Use FUNCTION auth level to require authentication for all endpoints
# This ensures that even if a route forgets require_role(), it still requires auth
app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

# Import route modules so decorators execute at import time
from .routes import audit as _audit_routes  # noqa: F401
from .routes import docs as _docs_routes  # noqa: F401
from .routes import names as _name_routes  # noqa: F401
from .routes import slug as _slug_routes  # noqa: F401

__all__ = ["app"]
