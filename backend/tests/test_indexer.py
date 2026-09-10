"""Indexer mapping + poll-and-diff behaviour against the in-memory chain."""

import pytest

from apps.cases.models import Case, CaseEvent
from apps.protocols.models import Protocol
from apps.sync import indexer
from apps.sync.models import SyncCursor
from tests.fakes import BACKUP, GOVERNOR, ONE_GEN, REPORTER

pytestmark = pytest.mark.django_db


def test_sync_protocol_maps_every_abi_field(chain):
    chain.register_protocol(
        name="Demo Vault Protocol",
        trusted_domains=["rentry.co", "status.example.com"],
        protected_actions=["withdraw", "transfer"],
        allowed_while_halted=["deposit"],
        reporter_bond=ONE_GEN,
        min_evidence=2,
        appeal_window_seconds=86400,
    )

    indexer.sync_protocol(0, reader=chain)

    protocol = Protocol.objects.get(onchain_id=0)
    assert protocol.name == "Demo Vault Protocol"
    assert protocol.status == "ACTIVE"
    assert protocol.governor == GOVERNOR
    assert protocol.reporter_bond == str(ONE_GEN)
    assert protocol.config["trusted_domains"] == ["rentry.co", "status.example.com"]
    assert protocol.config["protected_actions"] == ["withdraw", "transfer"]
    assert protocol.config["allowed_while_halted"] == ["deposit"]
    assert protocol.config["min_evidence"] == 2
    assert protocol.backup_unhalters == []
    assert protocol.halted_at is None
    assert protocol.config["backup_unhalters"] == []
    assert protocol.config["halted_at_unix"] == 0
    assert protocol.chain_created_at is not None
    # u256 bonds must not land in `raw` as a JS-lossy number.
    assert protocol.raw["reporter_bond"] == str(ONE_GEN)


def test_fast_path_sync_mirrors_halt_and_case(chain):
    chain.register_protocol()
    indexer.sync_protocol(0, reader=chain)
    assert Protocol.objects.get(onchain_id=0).status == "ACTIVE"

    case_id = chain.report_exploit(0, exploit=True, summary="Drain confirmed on-chain")
    report = indexer.sync_protocol(0, reader=chain)

    protocol = Protocol.objects.get(onchain_id=0)
    assert protocol.status == "HALTED"
    assert protocol.active_case_id == case_id
    assert report.protocols_updated == 1

    case = Case.objects.get(onchain_id=case_id)
    assert case.protocol_id == protocol.pk
    assert case.status == "ACCEPTED_HALT"
    assert case.verdict_exploit is True
    assert case.verdict_summary == "Drain confirmed on-chain"
    assert case.reporter == REPORTER
    assert case.bond_amount == str(ONE_GEN)
    assert case.bond_settled is False
    assert protocol.halted_at is not None
    assert CaseEvent.objects.filter(case=case).count() == 1


def test_rejected_report_leaves_protocol_active(chain):
    chain.register_protocol()
    case_id = chain.report_exploit(0, exploit=False)

    indexer.sync_protocol(0, reader=chain)

    assert Protocol.objects.get(onchain_id=0).status == "ACTIVE"
    case = Case.objects.get(onchain_id=case_id)
    assert case.status == "REJECTED"
    assert case.verdict_exploit is False


def test_unhalt_is_mirrored_back_to_active_and_cleared(chain):
    chain.register_protocol()
    case_id = chain.report_exploit(0, exploit=True)
    indexer.sync_protocol(0, reader=chain)

    chain.request_unhalt(0)
    indexer.sync_protocol(0, reader=chain)

    protocol = Protocol.objects.get(onchain_id=0)
    assert protocol.status == "ACTIVE"
    assert protocol.active_case_id == 0
    assert protocol.halted_at is None
    case = Case.objects.get(onchain_id=case_id)
    assert case.status == "CLEARED"
    assert case.verdict_summary == "Active exploit confirmed"
    assert "Unhalt:" not in case.verdict_summary
    events = list(CaseEvent.objects.filter(case=case).order_by("onchain_id"))
    assert len(events) == 2
    assert events[0].event_type == "REPORT_EVALUATED"
    assert events[1].event_type == "UNHALT_EVALUATED"
    assert events[0].consensus_summary != events[1].consensus_summary


def test_unchanged_chain_state_is_not_reported_as_an_update(chain):
    chain.register_protocol()
    indexer.sync_protocol(0, reader=chain)

    report = indexer.sync_protocol(0, reader=chain)

    assert report.protocols_created == 0
    assert report.protocols_updated == 0
    assert report.changed_protocol_ids == []


def test_sync_protocol_uses_chain_counts_not_onchain_id_plus_one(chain):
    # Register three protocols but only sync id 0 — count must stay 3, not 1.
    for index in range(3):
        chain.register_protocol(name=f"Protocol {index}")

    report = indexer.sync_protocol(0, reader=chain)

    assert report.protocol_count == 3
    assert report.case_count == 0
    assert Protocol.objects.count() == 1


def test_case_arriving_before_its_protocol_backfills_the_protocol(chain):
    chain.register_protocol()
    case_id = chain.report_exploit(0, exploit=True)

    indexer.sync_case(case_id, reader=chain)

    assert Protocol.objects.filter(onchain_id=0).exists()
    assert Case.objects.get(onchain_id=case_id).protocol.onchain_id == 0


def test_poll_and_diff_pages_in_everything_and_updates_cursor(chain):
    for index in range(3):
        chain.register_protocol(name=f"Protocol {index}")
    chain.report_exploit(0, exploit=True)
    chain.report_exploit(1, exploit=False)

    result = indexer.poll_and_diff(reader=chain)

    assert result["protocol_count"] == 3
    assert result["case_count"] == 2
    assert Protocol.objects.count() == 3
    assert Case.objects.count() == 2

    cursor = SyncCursor.load()
    assert cursor.protocol_count == 3
    assert cursor.case_count == 2
    assert cursor.case_event_count == 2
    assert cursor.last_success_at is not None
    assert cursor.last_error == ""


def test_poll_and_diff_picks_up_a_halt_that_does_not_change_counts(chain):
    chain.register_protocol()
    indexer.poll_and_diff(reader=chain)

    chain.report_exploit(0, exploit=True)
    indexer.poll_and_diff(reader=chain)
    assert Protocol.objects.get(onchain_id=0).status == "HALTED"

    # Unhalt changes neither protocol_count nor case_count.
    chain.request_unhalt(0)
    indexer.poll_and_diff(reader=chain)

    assert Protocol.objects.get(onchain_id=0).status == "ACTIVE"
    assert Case.objects.get(onchain_id=1).status == "CLEARED"


def test_poll_and_diff_records_the_error_and_reraises(chain):
    from apps.sync.genlayer_client import GenLayerError

    chain.fail_next = GenLayerError("RPC rate limited: -32006")
    with pytest.raises(GenLayerError):
        indexer.poll_and_diff(reader=chain)

    cursor = SyncCursor.load()
    assert "rate limited" in cursor.last_error
    assert cursor.last_success_at is None


def test_page_limit_is_capped_at_the_contract_maximum(settings, chain):
    settings.SYNC_PAGE_LIMIT = 500
    settings.API_MAX_PAGE_SIZE = 50
    chain.register_protocol()

    indexer.sync_protocols_page(0, reader=chain)

    assert ("list_protocols", (0, 50)) in chain.calls


def test_event_sync_is_idempotent(chain):
    chain.register_protocol()
    chain.report_exploit(0, exploit=True)
    indexer.poll_and_diff(reader=chain)
    assert CaseEvent.objects.count() == 1
    pk = CaseEvent.objects.get().pk

    indexer.poll_and_diff(reader=chain)

    assert CaseEvent.objects.count() == 1
    assert CaseEvent.objects.get().pk == pk


def test_sync_registers_backup_unhalters(chain):
    chain.register_protocol(backup_unhalters=[BACKUP])
    indexer.sync_protocol(0, reader=chain)

    protocol = Protocol.objects.get(onchain_id=0)
    assert protocol.backup_unhalters == [BACKUP]


def test_poll_and_diff_indexes_finalize_without_status_change(chain):
    chain.register_protocol()
    chain.report_exploit(0, exploit=True)
    indexer.poll_and_diff(reader=chain)
    assert Case.objects.get(onchain_id=1).bond_settled is False

    chain.finalize_appeal(0)
    indexer.poll_and_diff(reader=chain)

    protocol = Protocol.objects.get(onchain_id=0)
    assert protocol.status == "HALTED"
    case = Case.objects.get(onchain_id=1)
    assert case.bond_settled is True
    assert case.status == "ACCEPTED_HALT"
    types = list(
        CaseEvent.objects.filter(case=case)
        .order_by("onchain_id")
        .values_list("event_type", flat=True)
    )
    assert types == ["REPORT_EVALUATED", "APPEAL_FINALIZED"]
    assert CaseEvent.objects.get(event_type="APPEAL_FINALIZED").bond_disposition == (
        "REFUND_REPORTER"
    )


def test_window_zero_halt_refunds_reporter_immediately(chain):
    chain.register_protocol(appeal_window_seconds=0)
    chain.report_exploit(0, exploit=True)
    indexer.sync_protocol(0, reader=chain)

    case = Case.objects.get(onchain_id=1)
    assert case.bond_settled is True
    event = CaseEvent.objects.get(case=case)
    assert event.bond_disposition == "REFUND_ACTOR"


def test_halt_module_address_change_wipes_indexer_cache(chain):
    chain.register_protocol()
    indexer.sync_protocol(0, reader=chain)
    SyncCursor.load().mark_success(
        protocol_count=1,
        case_count=0,
        case_event_count=0,
        contract_address=chain.contract_address,
    )
    assert Protocol.objects.count() == 1

    chain.contract_address = "0x" + "ef" * 20
    indexer.ensure_contract_address(chain)

    assert Protocol.objects.count() == 0
    assert Case.objects.count() == 0
    assert CaseEvent.objects.count() == 0
    cursor = SyncCursor.load()
    assert cursor.contract_address == ""
    assert cursor.protocol_count == 0
