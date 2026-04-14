"""Application package exposing the shared FunctionApp instance.

The FunctionApp uses ANONYMOUS authentication at the Azure Functions runtime
level. All authorization is handled by the application layer via require_role()
in each route handler, which validates Entra ID JWT bearer tokens and enforces
role-based access control (reader/contributor/admin).

Every endpoint MUST call require_role() — there is no infrastructure-level
fallback. Code reviews should verify this on all new routes.
"""

from __future__ import annotations

import azure.functions as func

# ANONYMOUS at the Functions level — all auth is handled by require_role()
# in each route handler via JWT validation against Entra ID
app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

# Import route modules so decorators execute at import time
from .routes import audit as _audit_routes  # noqa: F401
from .routes import docs as _docs_routes  # noqa: F401
from .routes import names as _name_routes  # noqa: F401
from .routes import slug as _slug_routes  # noqa: F401

__all__ = ["app"]
