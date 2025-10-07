"""User-configurable settings service for name generation defaults.

The service allows callers to persist default values on a per-user basis as
well as transient per-session overrides. Session scoped defaults automatically
expire after a period of inactivity (one hour by default).

The module exposes a ready-to-use :data:`settings_service` instance which will
attempt to use Azure Table Storage when the Azure SDK and configuration are
available. When that is not possible (for example in local unit tests) the
service gracefully falls back to an in-memory repository.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Dict, MutableMapping, Optional, Protocol, Tuple

try:  # pragma: no cover - optional dependency for production deployments
    from azure.data.tables import TableServiceClient
    from azure.core.exceptions import ResourceNotFoundError
except ImportError:  # pragma: no cover - dependency is optional for tests
    TableServiceClient = None  # type: ignore

    class ResourceNotFoundError(Exception):
        """Placeholder exception when Azure SDK is unavailable."""


# Keys that are reserved by Azure Table Storage and should not leak to callers.
_RESERVED_ENTITY_FIELDS = {"PartitionKey", "RowKey", "Timestamp", "etag"}


class SettingsRepository(Protocol):
    """Storage abstraction for the :class:`UserSettingsService`."""

    def get_permanent(self, user_id: str) -> Dict[str, str]:
        ...

    def set_permanent(self, user_id: str, values: Dict[str, str]) -> None:
        ...

    def get_session(self, user_id: str, session_id: str) -> Optional[Tuple[Dict[str, str], datetime]]:
        ...

    def set_session(self, user_id: str, session_id: str, values: Dict[str, str], last_seen: datetime) -> None:
        ...

    def delete_session(self, user_id: str, session_id: str) -> None:
        ...


class InMemorySettingsRepository:
    """Simple repository implementation backed by process memory."""

    def __init__(self) -> None:
        self._permanent: Dict[str, Dict[str, str]] = {}
        self._sessions: Dict[str, Dict[str, Tuple[Dict[str, str], datetime]]] = {}
        self._lock = Lock()

    def get_permanent(self, user_id: str) -> Dict[str, str]:
        with self._lock:
            return dict(self._permanent.get(user_id, {}))

    def set_permanent(self, user_id: str, values: Dict[str, str]) -> None:
        with self._lock:
            self._permanent[user_id] = dict(values)

    def get_session(self, user_id: str, session_id: str) -> Optional[Tuple[Dict[str, str], datetime]]:
        with self._lock:
            session = self._sessions.get(user_id, {}).get(session_id)
            if not session:
                return None
            values, last_seen = session
            return dict(values), last_seen

    def set_session(self, user_id: str, session_id: str, values: Dict[str, str], last_seen: datetime) -> None:
        with self._lock:
            user_sessions = self._sessions.setdefault(user_id, {})
            user_sessions[session_id] = (dict(values), last_seen)

    def delete_session(self, user_id: str, session_id: str) -> None:
        with self._lock:
            sessions = self._sessions.get(user_id)
            if not sessions:
                return
            sessions.pop(session_id, None)
            if not sessions:
                self._sessions.pop(user_id, None)


class TableStorageSettingsRepository:
    """Repository implementation backed by Azure Table Storage."""

    _PERMANENT_TABLE = "UserSettings"
    _SESSION_TABLE = "UserSessionSettings"

    def __init__(self, connection_string: Optional[str] = None) -> None:
        if TableServiceClient is None:  # pragma: no cover - exercised in production
            raise RuntimeError("azure-data-tables is required for TableStorageSettingsRepository")

        connection_string = connection_string or os.environ.get("AzureWebJobsStorage")
        if not connection_string:
            raise RuntimeError("AzureWebJobsStorage must be configured for table storage settings")

        self._service = TableServiceClient.from_connection_string(connection_string)
        self._service.create_table_if_not_exists(self._PERMANENT_TABLE)
        self._service.create_table_if_not_exists(self._SESSION_TABLE)

    def get_permanent(self, user_id: str) -> Dict[str, str]:  # pragma: no cover - requires Azure SDK
        table = self._service.get_table_client(self._PERMANENT_TABLE)
        try:
            entity = table.get_entity(partition_key=user_id, row_key="defaults")
        except ResourceNotFoundError:
            return {}
        return _filter_entity_fields(entity)

    def set_permanent(self, user_id: str, values: Dict[str, str]) -> None:  # pragma: no cover - requires Azure SDK
        table = self._service.get_table_client(self._PERMANENT_TABLE)
        entity = {"PartitionKey": user_id, "RowKey": "defaults"}
        entity.update({key: str(value) for key, value in values.items()})
        table.upsert_entity(entity=entity, mode="Merge")

    def get_session(self, user_id: str, session_id: str) -> Optional[Tuple[Dict[str, str], datetime]]:  # pragma: no cover - requires Azure SDK
        table = self._service.get_table_client(self._SESSION_TABLE)
        try:
            entity = table.get_entity(partition_key=user_id, row_key=session_id)
        except ResourceNotFoundError:
            return None
        data = _filter_entity_fields(entity)
        last_seen_raw = data.pop("lastSeen", None) or data.pop("LastSeen", None)
        if not last_seen_raw:
            return data, datetime.now(timezone.utc)
        if isinstance(last_seen_raw, datetime):
            last_seen = last_seen_raw.astimezone(timezone.utc)
        else:
            last_seen = datetime.fromisoformat(str(last_seen_raw)).astimezone(timezone.utc)
        return data, last_seen

    def set_session(self, user_id: str, session_id: str, values: Dict[str, str], last_seen: datetime) -> None:  # pragma: no cover - requires Azure SDK
        table = self._service.get_table_client(self._SESSION_TABLE)
        entity = {"PartitionKey": user_id, "RowKey": session_id, "LastSeen": last_seen.isoformat()}
        entity.update({key: str(value) for key, value in values.items()})
        table.upsert_entity(entity=entity, mode="Merge")

    def delete_session(self, user_id: str, session_id: str) -> None:  # pragma: no cover - requires Azure SDK
        table = self._service.get_table_client(self._SESSION_TABLE)
        try:
            table.delete_entity(partition_key=user_id, row_key=session_id)
        except ResourceNotFoundError:
            return


def _filter_entity_fields(entity: MutableMapping[str, object]) -> Dict[str, str]:
    """Return a dictionary excluding Azure reserved fields."""

    cleaned: Dict[str, str] = {}
    for key, value in entity.items():
        if key in _RESERVED_ENTITY_FIELDS:
            continue
        cleaned[key] = str(value)
    return cleaned


@dataclass
class UserSettingsService:
    """High level coordinator for user default resolution."""

    repository: SettingsRepository
    session_timeout: timedelta = timedelta(hours=1)

    def set_permanent_defaults(self, user_id: str, values: Dict[str, str]) -> None:
        self.repository.set_permanent(user_id, self._normalise(values))

    def set_session_defaults(self, user_id: str, session_id: str, values: Dict[str, str], *, now: Optional[datetime] = None) -> None:
        if not session_id:
            raise ValueError("session_id must be provided for session defaults")
        now = now or datetime.now(timezone.utc)
        self.repository.set_session(user_id, session_id, self._normalise(values), now)

    def clear_session(self, user_id: str, session_id: str) -> None:
        self.repository.delete_session(user_id, session_id)

    def get_defaults(self, user_id: str, *, session_id: Optional[str] = None, now: Optional[datetime] = None) -> Dict[str, str]:
        now = now or datetime.now(timezone.utc)
        defaults = self.repository.get_permanent(user_id)
        if session_id:
            session = self.repository.get_session(user_id, session_id)
            if session:
                values, last_seen = session
                if now - last_seen > self.session_timeout:
                    logging.info(
                        "[user_settings] Session defaults expired for user %s session %s",
                        user_id,
                        session_id,
                    )
                    self.repository.delete_session(user_id, session_id)
                else:
                    # Touch the session to extend its lifetime.
                    self.repository.set_session(user_id, session_id, values, now)
                    defaults.update(values)
        return defaults

    def apply_defaults(
        self,
        payload: Dict[str, object],
        user_id: str,
        *,
        session_id: Optional[str] = None,
        now: Optional[datetime] = None,
    ) -> Dict[str, object]:
        merged = dict(payload)
        defaults = self.get_defaults(user_id, session_id=session_id, now=now)
        for key, value in defaults.items():
            if key not in merged or merged[key] in (None, ""):
                merged[key] = value
        return merged

    @staticmethod
    def _normalise(values: Dict[str, str]) -> Dict[str, str]:
        return {key: str(value) for key, value in values.items() if value is not None}


def _default_repository() -> SettingsRepository:
    if TableServiceClient is None:
        logging.info("[user_settings] Azure SDK not available; using in-memory settings repository")
        return InMemorySettingsRepository()

    try:  # pragma: no cover - exercised only when Azure SDK is present
        return TableStorageSettingsRepository()
    except Exception as exc:  # pragma: no cover - fallback path
        logging.warning(
            "[user_settings] Falling back to in-memory repository due to configuration error: %s",
            exc,
        )
        return InMemorySettingsRepository()


# Shared singleton instance used across the application.
settings_service = UserSettingsService(repository=_default_repository())

