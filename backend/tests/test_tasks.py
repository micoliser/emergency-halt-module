"""Celery task wiring + retry classification (runs eagerly, no broker)."""

import pytest

from apps.protocols.models import Protocol
from apps.sync import tasks
from apps.sync.genlayer_client import ContractCallError, GenLayerError
from tests.fakes import UnreachableChain

pytestmark = pytest.mark.django_db


def test_registered_task_names_match_the_beat_schedule():
    from config.celery import app

    names = set(app.tasks)
    assert "apps.sync.tasks.poll_and_diff" in names
    assert "apps.sync.tasks.sync_protocol" in names
    assert "apps.sync.tasks.sync_counts" in names


def test_poll_and_diff_task_indexes_through_the_reader(monkeypatch, chain):
    chain.register_protocol()
    chain.report_exploit(0, exploit=True)
    monkeypatch.setattr("apps.sync.indexer.get_reader", lambda: chain)

    result = tasks.poll_and_diff.apply().get()

    assert result["protocol_count"] == 1
    assert Protocol.objects.get(onchain_id=0).status == "HALTED"


def test_sync_protocol_task_uses_the_fast_path(monkeypatch, chain):
    chain.register_protocol(name="Task Protocol")
    monkeypatch.setattr("apps.sync.indexer.get_reader", lambda: chain)

    result = tasks.sync_protocol.apply(args=[0]).get()

    assert result["protocols_created"] == 1
    assert Protocol.objects.get(onchain_id=0).name == "Task Protocol"


def test_contract_revert_is_not_retried(monkeypatch, chain):
    chain.fail_next = ContractCallError("RPC error -32001: Contract not found")
    monkeypatch.setattr("apps.sync.indexer.get_reader", lambda: chain)

    result = tasks.poll_and_diff.apply().get()

    assert result == {"error": "RPC error -32001: Contract not found", "retried": False}


def test_transport_failure_is_retried(monkeypatch):
    from celery.exceptions import Retry

    monkeypatch.setattr("apps.sync.indexer.get_reader", UnreachableChain)

    with pytest.raises((Retry, GenLayerError)):
        tasks.poll_and_diff.apply(throw=True).get()
