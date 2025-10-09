# 🧩 Proposed Module Layout for `function_app`

This blueprint keeps Azure Functions running on the same host process while
making the codebase easier to navigate, test, and extend. No extra consumption
costs are incurred—the modules are pure Python and imported at startup.

```
azure-naming/
│
├── function_app.py             # Thin entry point that wires endpoints together
│
├── app/
│   ├── __init__.py             # Exposes the shared FunctionApp instance
│   ├── routes/
│   │   ├── __init__.py         # Registers all HTTP + timer routes
│   │   ├── names.py            # /claim, /generate, /release handlers
│   │   ├── audit.py            # /audit and /audit_bulk handlers
│   │   └── slug.py             # /slug_sync and timer-based sync
│   │
│   ├── models.py               # Pydantic request/response models used by routes
│   ├── dependencies.py         # Common setup (require_role, service singletons)
│   ├── responses.py            # Helper builders for HttpResponse payloads
│   └── errors.py               # Shared exception types + error mappers
│
└── utils/                      # Existing domain helpers remain here
```

## Why split things up?

| Pain point in `function_app.py` | Mitigation in proposed layout |
| --- | --- |
| Large 600+ line file mixes HTTP decorators, validation, and response plumbing. | Routes become small modules that import shared helpers, keeping each file focused. |
| Pydantic models sit far from the endpoints that use them, leading to scrolling and merge friction. | All schemas live in `app/models.py`; routes import the ones they need. |
| Helper functions (e.g., `_build_claim_response`) are hidden in the middle of the file and duplicated for new routes. | Helpers move into `responses.py` / `dependencies.py`, encouraging reuse. |
| Testing routes directly requires importing the entire `function_app.py` module. | Unit tests can import specific route modules, while integration tests still use the full FunctionApp. |

## Migration guide

1. **Create the `app` package** and move the existing `FunctionApp` instance to
   `app/__init__.py`. Import it in `function_app.py` to keep the Azure Functions
   runtime happy.
2. **Relocate models** from `function_app.py` to `app/models.py`. Update
   references in the route modules.
3. **Extract route handlers** (`claim`, `generate`, `release`, `audit`, etc.)
   into `app/routes/*`. Each module imports the shared `FunctionApp` and
   registers its routes using decorators.
4. **Add shared helpers** (`dependencies.py`, `responses.py`, `errors.py`) to
   centralise logic that multiple routes consume.
5. **Slim down `function_app.py`** so it only imports `app` modules and exposes
   `app.FunctionApp` for the runtime.

> ✅ The Azure Functions Python worker discovers functions at import time, so as
> long as the decorator calls happen during module import, the runtime behaves
> exactly the same. No host.json or deployment changes are required.

## Testing considerations

- **Unit tests** can import `app.routes.names` (for example) and call the
  underlying handler functions with mocked dependencies.
- **Existing integration tests** that exercise the HTTP surface through
  `function_app.py` continue to work after updating import paths.
- Add new tests around `responses.py` / `dependencies.py` as logic moves there to
  keep coverage high.

## Next steps

- Socialise this layout in the team; confirm the package name (`app`) works for
  your deployment pipeline.
- Once agreed, execute the migration in small commits (models first, then routes,
  then helpers) to keep reviews manageable.
- Update `docs/architecture.mmd` (PlantUML) after the refactor to reflect the
  new structure.
