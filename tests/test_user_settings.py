import pathlib
import sys
from datetime import datetime, timedelta, timezone

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.user_settings import InMemorySettingsRepository, UserSettingsService


def _service() -> UserSettingsService:
    return UserSettingsService(repository=InMemorySettingsRepository())


def test_permanent_defaults_are_returned():
    service = _service()
    service.set_permanent_defaults("user-1", {"environment": "prod", "region": "wus2"})

    defaults = service.get_defaults("user-1")

    assert defaults == {"environment": "prod", "region": "wus2"}


def test_session_defaults_override_permanent():
    service = _service()
    now = datetime.now(timezone.utc)

    service.set_permanent_defaults("user-1", {"environment": "prod", "region": "wus2"})
    service.set_session_defaults("user-1", "session-a", {"environment": "dev"}, now=now)

    defaults = service.get_defaults("user-1", session_id="session-a", now=now + timedelta(minutes=5))

    assert defaults["environment"] == "dev"
    assert defaults["region"] == "wus2"


def test_session_defaults_expire_after_timeout():
    service = _service()
    now = datetime.now(timezone.utc)

    service.set_session_defaults("user-2", "session-b", {"environment": "qa"}, now=now)

    defaults = service.get_defaults(
        "user-2",
        session_id="session-b",
        now=now + service.session_timeout + timedelta(seconds=1),
    )

    assert "environment" not in defaults


def test_apply_defaults_merges_missing_fields():
    service = _service()
    service.set_permanent_defaults("user-3", {"environment": "dev", "region": "eus"})

    payload = {"resource_type": "storage_account"}
    merged = service.apply_defaults(payload, "user-3")

    assert merged["environment"] == "dev"
    assert merged["region"] == "eus"
    assert merged["resource_type"] == "storage_account"


def test_set_session_defaults_requires_session_id():
    service = _service()

    with pytest.raises(ValueError):
        service.set_session_defaults("user", "", {"environment": "dev"})

