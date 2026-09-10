import pytest

from tests.fakes import FakeHaltModule

# Must match config.settings_test.SYNC_SHARED_SECRET
SYNC_HEADERS = {"X-Sync-Secret": "test-sync-secret"}


@pytest.fixture
def chain() -> FakeHaltModule:
    return FakeHaltModule()


@pytest.fixture
def patched_reader(monkeypatch, chain):
    """Make every `get_reader()` call site use the in-memory chain."""
    monkeypatch.setattr("apps.sync.indexer.get_reader", lambda: chain)
    monkeypatch.setattr("apps.sync.views.get_reader", lambda: chain)
    return chain


@pytest.fixture
def sync_client(client):
    """APIClient that attaches the test sync secret on every request."""

    class _SyncClient:
        def get(self, path, *args, **kwargs):
            return client.get(path, *args, **kwargs)

        def post(self, path, *args, **kwargs):
            headers = dict(kwargs.pop("headers", {}) or {})
            headers.setdefault("X-Sync-Secret", SYNC_HEADERS["X-Sync-Secret"])
            return client.post(path, *args, headers=headers, **kwargs)

    return _SyncClient()
