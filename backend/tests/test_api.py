"""Read API contract tests — these shapes are what the Phase 5 frontend consumes."""

import pytest

from apps.sync import indexer
from tests.fakes import BACKUP, GOVERNOR, ONE_GEN

pytestmark = pytest.mark.django_db


@pytest.fixture
def seeded(chain):
    chain.register_protocol(name="Demo Vault Protocol")
    chain.register_protocol(name="Second Protocol")
    chain.report_exploit(0, exploit=True, summary="Drain confirmed")
    indexer.poll_and_diff(reader=chain)
    return chain


def test_protocol_list_is_empty_but_well_formed_on_a_fresh_db(client):
    response = client.get("/api/protocols")

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "count": 0,
        "offset": 0,
        "limit": 20,
        "next": None,
        "previous": None,
        "results": [],
    }


def test_health_on_a_never_synced_database(client):
    body = client.get("/api/health").json()

    assert body["status"] == "ok"
    assert body["indexed"] == {"protocols": 0, "cases": 0, "events": 0}
    assert body["cursor"] is None


def test_protocol_list_returns_indexed_rows(client, seeded):
    body = client.get("/api/protocols").json()

    assert body["count"] == 2
    first = body["results"][0]
    assert first["id"] == 0
    assert first["name"] == "Demo Vault Protocol"
    assert first["status"] == "HALTED"
    assert first["is_halted"] is True
    assert first["governor"] == GOVERNOR
    assert first["protected_actions"] == ["withdraw", "transfer"]
    assert first["reporter_bond"] == str(ONE_GEN)
    assert first["reporter_bond_gen"] == "1"
    assert first["active_case_id"] == 1
    assert first["case_count"] == 1


def test_protocol_list_supports_offset_limit_and_status_filter(client, seeded):
    page = client.get("/api/protocols?offset=1&limit=1").json()
    assert page["count"] == 2
    assert page["offset"] == 1
    assert page["limit"] == 1
    assert [row["id"] for row in page["results"]] == [1]

    halted = client.get("/api/protocols?status=halted").json()
    assert [row["id"] for row in halted["results"]] == [0]


def test_protocol_list_limit_is_capped(client, seeded, settings):
    body = client.get("/api/protocols?limit=5000").json()
    assert body["limit"] == settings.API_MAX_PAGE_SIZE


def test_protocol_detail_embeds_the_active_case(client, seeded):
    body = client.get("/api/protocols/0").json()

    assert body["id"] == 0
    assert body["status"] == "HALTED"
    assert body["active_case"]["id"] == 1
    assert body["active_case"]["verdict_exploit"] is True
    assert body["active_case"]["verdict_summary"] == "Drain confirmed"


def test_protocol_detail_uses_prefetched_cases(client, seeded, django_assert_num_queries):
    # Protocol fetch + cases prefetch (+ any connection/session overhead is
    # wrapped by django_assert_num_queries). Without prefetch, get_active_case
    # would add another Cases SELECT.
    with django_assert_num_queries(2):
        response = client.get("/api/protocols/0")
    assert response.status_code == 200
    assert response.json()["active_case"]["id"] == 1


def test_protocol_detail_active_case_is_null_when_not_halted(client, seeded):
    body = client.get("/api/protocols/1").json()
    assert body["status"] == "ACTIVE"
    assert body["active_case"] is None


def test_unknown_protocol_is_404(client):
    assert client.get("/api/protocols/99").status_code == 404


def test_protocol_cases_list(client, seeded):
    body = client.get("/api/protocols/0/cases").json()

    assert body["count"] == 1
    case = body["results"][0]
    assert case["id"] == 1
    assert case["protocol_id"] == 0
    assert case["status"] == "ACCEPTED_HALT"
    assert case["bond_amount_gen"] == "1"
    assert case["evidence_urls"] == ["https://rentry.co/incident"]


def test_protocol_cases_for_unknown_protocol_is_404(client, seeded):
    assert client.get("/api/protocols/99/cases").status_code == 404


def test_case_list_and_filters(client, seeded):
    body = client.get("/api/cases").json()
    assert body["count"] == 1

    filtered = client.get("/api/cases?protocol_id=1").json()
    assert filtered["count"] == 0


def test_governor_filter_normalizes_unpadded_query_address(client, seeded):
    # Stored as 0x + 40 hex; bare/unpadded query must still match.
    bare = GOVERNOR.removeprefix("0x").lstrip("0") or "0"
    body = client.get(f"/api/protocols?governor={bare}").json()
    assert body["count"] == 2
    assert all(row["governor"] == GOVERNOR for row in body["results"])


def test_reporter_filter_normalizes_unpadded_query_address(client, seeded):
    from tests.fakes import REPORTER

    bare = REPORTER.removeprefix("0x").lstrip("0") or "0"
    body = client.get(f"/api/cases?reporter={bare}").json()
    assert body["count"] == 1
    assert body["results"][0]["reporter"] == REPORTER


def test_case_detail_includes_protocol_context(client, seeded):
    body = client.get("/api/cases/1").json()

    assert body["id"] == 1
    assert body["protocol"]["id"] == 0
    assert body["protocol"]["status"] == "HALTED"
    assert body["submitted_at"] is not None
    assert body["event_count"] == 1
    assert len(body["events"]) == 1
    assert body["events"][0]["event_type"] == "REPORT_EVALUATED"


def test_case_detail_timeline_after_report_and_unhalt(client, chain):
    chain.register_protocol(backup_unhalters=[BACKUP])
    chain.report_exploit(0, exploit=True, summary="Drain confirmed")
    chain.request_unhalt(0, summary="Patch verified")
    indexer.poll_and_diff(reader=chain)

    body = client.get("/api/cases/1").json()
    events = body["events"]
    assert len(events) >= 2
    assert [row["event_type"] for row in events[:2]] == [
        "REPORT_EVALUATED",
        "UNHALT_EVALUATED",
    ]
    assert events[0]["consensus_summary"] == "Drain confirmed"
    assert events[1]["consensus_summary"] == "Patch verified"
    assert events[0]["bond_disposition"] == "ESCROWED"
    assert events[1]["bond_disposition"] == "PAY_REPORTER|REFUND_REPORTER"
    assert body["verdict_summary"] == "Drain confirmed"
    assert "Unhalt:" not in body["verdict_summary"]


def test_protocol_detail_shows_backups_and_halted_at(client, chain):
    chain.register_protocol(backup_unhalters=[BACKUP])
    chain.report_exploit(0, exploit=True)
    indexer.poll_and_diff(reader=chain)

    body = client.get("/api/protocols/0").json()
    assert body["backup_unhalters"] == [BACKUP]
    assert body["halted_at"] is not None
    assert body["appeal_ends_at"] is not None
    assert body["status"] == "HALTED"


def test_protocol_list_includes_backups_and_still_lists(client, seeded):
    body = client.get("/api/protocols").json()
    assert body["count"] == 2
    halted = body["results"][0]
    assert "backup_unhalters" in halted
    assert "halted_at" in halted
    assert halted["backup_unhalters"] == []


def test_case_detail_prefetches_events(client, seeded, django_assert_num_queries):
    with django_assert_num_queries(2):
        response = client.get("/api/cases/1")
    assert response.status_code == 200
    assert len(response.json()["events"]) == 1


def test_unknown_case_is_404(client):
    assert client.get("/api/cases/42").status_code == 404


def test_trailing_slashes_are_accepted(client, seeded):
    assert client.get("/api/protocols/").status_code == 200
    assert client.get("/api/protocols/0/").status_code == 200
    assert client.get("/api/protocols/0/cases/").status_code == 200
    assert client.get("/api/cases/1/").status_code == 200


def test_health_reports_config_and_cursor(client, seeded, settings):
    body = client.get("/api/health").json()

    assert body["status"] == "ok"
    assert body["database"]["ok"] is True
    assert body["chain"]["chain_id"] == settings.GENLAYER_CHAIN_ID
    assert body["chain"]["configured"] is True
    assert body["indexed"] == {"protocols": 2, "cases": 1, "events": 1}
    assert body["cursor"]["protocol_count"] == 2
    assert body["cursor"]["case_count"] == 1


def test_root_lists_routes(client):
    body = client.get("/").json()
    assert body["service"] == "proofhalt-indexer"
    assert any("/api/protocols" in route for route in body["routes"])
