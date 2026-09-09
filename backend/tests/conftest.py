import pytest

from tests.fakes import FakeHaltModule


@pytest.fixture
def chain() -> FakeHaltModule:
    return FakeHaltModule()


@pytest.fixture
def patched_reader(monkeypatch, chain):
    """Make every `get_reader()` call site use the in-memory chain."""
    monkeypatch.setattr("apps.sync.indexer.get_reader", lambda: chain)
    monkeypatch.setattr("apps.sync.views.get_reader", lambda: chain)
    return chain
