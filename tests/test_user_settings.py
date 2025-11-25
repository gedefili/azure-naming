import pathlib
import sys
from datetime import datetime, timedelta, timezone

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.user_settings import (
    InMemorySettingsRepository,
    UserSettingsService,
    _filter_entity_fields,
)


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


def test_apply_defaults_does_not_override_existing_values():
    service = _service()
    service.set_permanent_defaults("user-4", {"environment": "dev", "region": "eus"})

    payload = {"environment": "qa", "region": "", "resource_type": "storage_account"}
    merged = service.apply_defaults(payload, "user-4")

    assert merged["environment"] == "qa"
    assert merged["region"] == "eus"


def test_normalise_removes_none_and_casts_to_strings():
    result = UserSettingsService._normalise({"index": 5, "region": "wus2", "skip": None})
    assert result == {"index": "5", "region": "wus2"}


def test_in_memory_repository_returns_copies():
    repository = InMemorySettingsRepository()
    now = datetime.now(timezone.utc)
    repository.set_permanent("user", {"env": "dev"})
    repository.set_session("user", "session", {"region": "eus"}, now)

    permanent = repository.get_permanent("user")
    session, _ = repository.get_session("user", "session")
    permanent["env"] = "qa"
    session["region"] = "wus2"

    assert repository.get_permanent("user")["env"] == "dev"
    assert repository.get_session("user", "session")[0]["region"] == "eus"


def test_delete_session_removes_empty_user_bucket():
    repository = InMemorySettingsRepository()
    now = datetime.now(timezone.utc)
    repository.set_session("user", "one", {"region": "eus"}, now)
    repository.delete_session("user", "one")

    assert repository.get_session("user", "one") is None
    assert "user" not in repository._sessions  # type: ignore[attr-defined]


def test_active_session_is_touched_when_accessed():
    class RecordingRepository(InMemorySettingsRepository):
        def __init__(self) -> None:
            super().__init__()
            self.touched: list[tuple[str, str, datetime]] = []

        def set_session(self, user_id, session_id, values, last_seen):  # type: ignore[override]
            super().set_session(user_id, session_id, values, last_seen)
            self.touched.append((user_id, session_id, last_seen))

    repository = RecordingRepository()
    service = UserSettingsService(repository=repository)
    now = datetime.now(timezone.utc)
    repository.set_session("user", "session", {"region": "eus"}, now)

    later = now + timedelta(minutes=5)
    defaults = service.get_defaults("user", session_id="session", now=later)

    assert defaults["region"] == "eus"
    assert repository.touched
    assert repository.touched[-1][2] == later


def test_clear_session_deletes_session():
    repository = InMemorySettingsRepository()
    service = UserSettingsService(repository=repository)
    now = datetime.now(timezone.utc)
    repository.set_session("user", "session", {"region": "eus"}, now)

    service.clear_session("user", "session")

    assert repository.get_session("user", "session") is None


def test_delete_session_is_noop_for_unknown_user():
    repository = InMemorySettingsRepository()
    repository.delete_session("missing", "session")

    assert repository.get_session("missing", "session") is None


def test_filter_entity_fields_strips_reserved_keys():
    entity = {
        "PartitionKey": "user",
        "RowKey": "defaults",
        "Timestamp": "ignored",
        "etag": "ignored",
        "region": "wus2",
        "count": 3,
    }

    assert _filter_entity_fields(entity) == {"region": "wus2", "count": "3"}

