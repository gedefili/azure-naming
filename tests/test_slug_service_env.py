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

    # Temporarily add test provider to allowlist and call loader directly
    original_allowed = slug_service._ALLOWED_SLUG_PROVIDERS.copy()
    slug_service._ALLOWED_SLUG_PROVIDERS.add(f"{module_name}.EnvProvider")
    original_providers = slug_service.get_slug_providers()

    try:
        env_providers = slug_service._load_providers_from_env()
        assert env_providers is not None
        slug_service.set_slug_providers(env_providers)
        assert slug_service.get_slug("env") == "ev"
    finally:
        # cleanup
        slug_service._ALLOWED_SLUG_PROVIDERS = original_allowed
        slug_service.set_slug_providers(original_providers)
        monkeypatch.delenv("SLUG_PROVIDER", raising=False)
