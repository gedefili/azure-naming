import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.routes import audit


class FakeAuditTable:
    def __init__(self) -> None:
        self.query_kwargs = None
        self.list_called = False

    def query_entities(self, **kwargs):
        self.query_kwargs = kwargs
        yield from ()

    def list_entities(self):
        self.list_called = True
        yield from ()


def test_query_audit_entities_prefers_query_filter():
    table = FakeAuditTable()

    list(audit._query_audit_entities(table, "User eq 'someone'"))

    assert table.query_kwargs == {"query_filter": "User eq 'someone'"}
    assert table.list_called is False


def test_query_audit_entities_falls_back_to_list():
    table = FakeAuditTable()

    list(audit._query_audit_entities(table, ""))

    assert table.query_kwargs is None
    assert table.list_called is True
