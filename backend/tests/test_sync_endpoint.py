"""
Fast-path sync endpoint — the Phase 4 exit criterion.

Simulates the demo loop: register + report on-chain, then a single
`POST /api/sync/protocols/<id>` must make the API report HALTED immediately.
"""

import pytest

from apps.protocols.models import Protocol
from apps.sync.models import SyncCursor
from tests.fakes import UnreachableChain

pytestmark = pytest.mark.django_db


def test_fast_path_shows_halted_immediately_after_a_report(client, patched_reader):
    chain = patched_reader
    chain.register_protocol()
    client.post("/api/sync/protocols/0")
    assert client.get("/api/protocols/0").json()["status"] == "ACTIVE"

    chain.report_exploit(0, exploit=True, summary="Drain confirmed")

    response = client.post("/api/sync/protocols/0")

    assert response.status_code == 200
    body = response.json()
    assert body["protocol"]["status"] == "HALTED"
    assert body["protocol"]["active_case"]["verdict_summary"] == "Drain confirmed"
    assert body["synced"]["protocols_updated"] == 1
    assert body["synced"]["cases_created"] == 1

    # And the plain read endpoints agree without another sync.
    assert client.get("/api/protocols/0").json()["status"] == "HALTED"
    case = client.get("/api/cases/1").json()
    assert case["status"] == "ACCEPTED_HALT"
    assert case["bond_settled"] is False
    assert len(case["events"]) == 1
    assert case["events"][0]["event_type"] == "REPORT_EVALUATED"


def test_fast_path_creates_a_protocol_the_indexer_had_never_seen(client, patched_reader):
    patched_reader.register_protocol(name="Fresh Registration")

    response = client.post("/api/sync/protocols/0")

    assert response.status_code == 200
    assert response.json()["synced"]["protocols_created"] == 1
    assert Protocol.objects.get(onchain_id=0).name == "Fresh Registration"


def test_fast_path_reflects_unhalt(client, patched_reader):
    chain = patched_reader
    chain.register_protocol()
    chain.report_exploit(0, exploit=True)
    client.post("/api/sync/protocols/0")

    chain.request_unhalt(0)
    body = client.post("/api/sync/protocols/0").json()

    assert body["protocol"]["status"] == "ACTIVE"
    assert body["protocol"]["active_case"] is None
    case = client.get("/api/cases/1").json()
    assert case["status"] == "CLEARED"
    assert case["verdict_summary"] == "Active exploit confirmed"
    assert "Unhalt:" not in case["verdict_summary"]
    assert len(case["events"]) == 2
    assert [row["event_type"] for row in case["events"]] == [
        "REPORT_EVALUATED",
        "UNHALT_EVALUATED",
    ]


def test_fast_path_for_an_unregistered_protocol_is_404(client, patched_reader):
    response = client.post("/api/sync/protocols/7")

    assert response.status_code == 404
    assert "Protocol does not exist" in response.json()["detail"]


def test_fast_path_returns_502_when_the_chain_is_unreachable(client, monkeypatch):
    monkeypatch.setattr("apps.sync.views.get_reader", lambda: UnreachableChain())

    response = client.post("/api/sync/protocols/0")

    assert response.status_code == 502
    assert "Could not reach GenLayer" in response.json()["detail"]


def test_sync_all_endpoint_seeds_everything(client, patched_reader):
    chain = patched_reader
    chain.register_protocol()
    chain.register_protocol()
    chain.report_exploit(1, exploit=True)

    body = client.post("/api/sync/all").json()

    assert body["synced"]["protocol_count"] == 2
    assert body["synced"]["case_count"] == 1
    assert client.get("/api/protocols/1").json()["status"] == "HALTED"
    assert SyncCursor.load().case_count == 1


def test_shared_secret_is_enforced_when_configured(client, patched_reader, settings):
    settings.SYNC_SHARED_SECRET = "topsecret"
    patched_reader.register_protocol()

    assert client.post("/api/sync/protocols/0").status_code == 403
    assert client.post("/api/sync/all").status_code == 403

    ok = client.post("/api/sync/protocols/0", headers={"X-Sync-Secret": "topsecret"})
    assert ok.status_code == 200


def test_get_on_a_sync_route_is_rejected(client, patched_reader):
    assert client.get("/api/sync/protocols/0").status_code == 405
