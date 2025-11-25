import importlib
import os
import types

from core import slug_service


def test_register_and_set_providers(monkeypatch):
    original = slug_service.get_slug_providers()

    class Dummy:
        def get_slug(self, resource_type: str):
            if resource_type == "custom":
                return "cs"
            raise ValueError("Not found")

    try:
        slug_service.set_slug_providers([Dummy()])
        assert slug_service.get_slug("custom") == "cs"
    finally:
        slug_service.set_slug_providers(original)


def test_load_providers_from_env(monkeypatch, tmp_path):
    # create a temporary module that exposes a provider class
    module_name = "tests._temp_provider"
    module = types.ModuleType(module_name)

    class EnvProvider:
        def get_slug(self, resource_type: str):
            if resource_type == "env":
                return "ev"
            raise ValueError("Not found")

    module.EnvProvider = EnvProvider
    import sys

    sys.modules[module_name] = module

    monkeypatch.setenv("SLUG_PROVIDER", f"{module_name}.EnvProvider")

    # reload slug_service to pick up env provider
    importlib.reload(slug_service)

    try:
        assert slug_service.get_slug("env") == "ev"
    finally:
        # cleanup: remove env var and reload original module
        monkeypatch.delenv("SLUG_PROVIDER", raising=False)
        importlib.reload(slug_service)
