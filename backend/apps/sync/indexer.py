"""
Poll-and-diff indexer.

The only source of truth is the Halt Module contract. Every function here
reads a view and upserts the result; none of them derive, infer, or override
protocol status or case verdicts (IMPLEMENTATION_PLAN.md §2.2).

Plain functions (not Celery tasks) so they can be called inline from the
fast-path API view and unit-tested with a fake reader.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.cases.models import Case, CaseEvent
from apps.common.units import (
    json_safe,
    normalize_address,
    string_list,
    to_amount_str,
    to_int,
    unix_to_datetime,
)
from apps.protocols.models import Protocol
from apps.sync.genlayer_client import HaltModuleReader, get_reader
from apps.sync.models import SyncCursor

logger = logging.getLogger(__name__)


def wipe_indexer_cache(*, reason: str) -> None:
    """
    Drop mirrored rows when HALT_MODULE_ADDRESS changes so old and new
    contracts never mix in Postgres.
    """
    logger.warning("wiping indexer cache: %s", reason)
    with transaction.atomic():
        CaseEvent.objects.all().delete()
        Case.objects.all().delete()
        Protocol.objects.all().delete()
        cursor = SyncCursor.load()
        cursor.protocol_count = 0
        cursor.case_count = 0
        cursor.case_event_count = 0
        cursor.contract_address = ""
        cursor.last_error = ""
        cursor.save(
            update_fields=[
                "protocol_count",
                "case_count",
                "case_event_count",
                "contract_address",
                "last_error",
            ]
        )


def ensure_contract_address(reader: HaltModuleReader) -> None:
    """Refuse mixed mirrors when the configured Halt Module address changes."""
    addr = (reader.contract_address or "").strip().lower()
    if not addr:
        return
    cursor = SyncCursor.load()
    stored = (cursor.contract_address or "").strip().lower()
    if stored and stored != addr:
        wipe_indexer_cache(
            reason=f"HALT_MODULE_ADDRESS changed ({stored} → {addr})"
        )


@dataclass
class SyncReport:
    """What a sync run touched — returned to callers and logged."""

    protocols_seen: int = 0
    protocols_created: int = 0
    protocols_updated: int = 0
    cases_seen: int = 0
    cases_created: int = 0
    cases_updated: int = 0
    events_seen: int = 0
    events_created: int = 0
    events_updated: int = 0
    protocol_count: int = 0
    case_count: int = 0
    case_event_count: int = 0
    changed_protocol_ids: list[int] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "protocols_seen": self.protocols_seen,
            "protocols_created": self.protocols_created,
            "protocols_updated": self.protocols_updated,
            "cases_seen": self.cases_seen,
            "cases_created": self.cases_created,
            "cases_updated": self.cases_updated,
            "events_seen": self.events_seen,
            "events_created": self.events_created,
            "events_updated": self.events_updated,
            "protocol_count": self.protocol_count,
            "case_count": self.case_count,
            "case_event_count": self.case_event_count,
            "changed_protocol_ids": sorted(set(self.changed_protocol_ids)),
        }

    def merge(self, other: "SyncReport") -> "SyncReport":
        self.protocols_seen += other.protocols_seen
        self.protocols_created += other.protocols_created
        self.protocols_updated += other.protocols_updated
        self.cases_seen += other.cases_seen
        self.cases_created += other.cases_created
        self.cases_updated += other.cases_updated
        self.events_seen += other.events_seen
        self.events_created += other.events_created
        self.events_updated += other.events_updated
        self.protocol_count = max(self.protocol_count, other.protocol_count)
        self.case_count = max(self.case_count, other.case_count)
        self.case_event_count = max(self.case_event_count, other.case_event_count)
        self.changed_protocol_ids.extend(other.changed_protocol_ids)
        return self


# ---------------------------------------------------------------------------
# Snapshot → model field mapping
# ---------------------------------------------------------------------------


def protocol_fields(snapshot: dict) -> dict:
    backups = [
        normalize_address(item)
        for item in string_list(snapshot.get("backup_unhalters"))
        if normalize_address(item)
    ]
    halted_at_unix = to_int(snapshot.get("halted_at"))
    return {
        "name": str(snapshot.get("name") or "")[:200],
        "status": str(snapshot.get("status") or "")[:16],
        "governor": normalize_address(snapshot.get("governor")),
        "exploit_definition": str(snapshot.get("exploit_definition") or ""),
        "config": {
            "trusted_domains": string_list(snapshot.get("trusted_domains")),
            "protected_actions": string_list(snapshot.get("protected_actions")),
            "allowed_while_halted": string_list(snapshot.get("allowed_while_halted")),
            "min_evidence": to_int(snapshot.get("min_evidence")),
            "appeal_window_seconds": to_int(snapshot.get("appeal_window_seconds")),
            "backup_unhalters": backups,
            "halted_at_unix": halted_at_unix,
        },
        "backup_unhalters": backups,
        "halted_at": unix_to_datetime(halted_at_unix),
        "reporter_bond": to_amount_str(snapshot.get("reporter_bond")),
        "active_case_id": to_int(snapshot.get("active_case_id")),
        "onchain_case_count": to_int(snapshot.get("case_count")),
        "chain_created_at": unix_to_datetime(snapshot.get("created_at")),
        "raw": json_safe(snapshot),
    }


def case_fields(snapshot: dict) -> dict:
    return {
        "protocol_onchain_id": to_int(snapshot.get("protocol_id")),
        "reporter": normalize_address(snapshot.get("reporter")),
        "allegation": str(snapshot.get("allegation") or ""),
        "evidence_urls": string_list(snapshot.get("evidence_urls")),
        "verdict_exploit": bool(snapshot.get("verdict_exploit")),
        "verdict_summary": str(snapshot.get("verdict_summary") or ""),
        "status": str(snapshot.get("status") or "")[:24],
        "bond_amount": to_amount_str(snapshot.get("bond_amount")),
        "bond_settled": bool(snapshot.get("bond_settled")),
        "event_count": to_int(snapshot.get("event_count")),
        "chain_submitted_at": unix_to_datetime(snapshot.get("submitted_at")),
        "raw": json_safe(snapshot),
    }


def event_fields(snapshot: dict) -> dict:
    urls_source = snapshot.get("evidence_urls")
    if urls_source is None:
        urls_source = snapshot.get("evidence_urls_joined")
    return {
        "protocol_onchain_id": to_int(snapshot.get("protocol_id")),
        "event_type": str(snapshot.get("event_type") or "")[:32],
        "actor": normalize_address(snapshot.get("actor")),
        "statement": str(snapshot.get("statement") or ""),
        "evidence_urls": string_list(urls_source),
        "consensus_bool": bool(snapshot.get("consensus_bool")),
        "consensus_summary": str(snapshot.get("consensus_summary") or ""),
        "from_status": str(snapshot.get("from_status") or "")[:24],
        "to_status": str(snapshot.get("to_status") or "")[:24],
        "bond_amount": to_amount_str(snapshot.get("bond_amount")),
        "bond_disposition": str(snapshot.get("bond_disposition") or "")[:80],
        "chain_created_at": unix_to_datetime(snapshot.get("created_at")),
        "raw": json_safe(snapshot),
    }


# Fields compared to decide whether a row actually changed. `synced_at` and
# `raw` are excluded so an unchanged chain read is a no-op write.
_PROTOCOL_DIFF_FIELDS = (
    "name",
    "status",
    "governor",
    "exploit_definition",
    "config",
    "reporter_bond",
    "backup_unhalters",
    "halted_at",
    "active_case_id",
    "onchain_case_count",
    "chain_created_at",
)
_CASE_DIFF_FIELDS = (
    "protocol_onchain_id",
    "reporter",
    "allegation",
    "evidence_urls",
    "verdict_exploit",
    "verdict_summary",
    "status",
    "bond_amount",
    "bond_settled",
    "event_count",
    "chain_submitted_at",
)
_EVENT_DIFF_FIELDS = (
    "protocol_onchain_id",
    "event_type",
    "actor",
    "statement",
    "evidence_urls",
    "consensus_bool",
    "consensus_summary",
    "from_status",
    "to_status",
    "bond_amount",
    "bond_disposition",
    "chain_created_at",
    "raw",
)


def _changed_fields(instance, values: dict, diff_fields) -> list[str]:
    return [key for key in diff_fields if getattr(instance, key) != values[key]]


# ---------------------------------------------------------------------------
# Upserts
# ---------------------------------------------------------------------------


def upsert_protocol(snapshot: dict, report: SyncReport) -> Protocol:
    onchain_id = to_int(snapshot.get("id"))
    values = protocol_fields(snapshot)
    now = timezone.now()
    report.protocols_seen += 1

    protocol = Protocol.objects.filter(onchain_id=onchain_id).first()
    if protocol is None:
        protocol = Protocol.objects.create(
            onchain_id=onchain_id, synced_at=now, **values
        )
        report.protocols_created += 1
        report.changed_protocol_ids.append(onchain_id)
        return protocol

    changed = _changed_fields(protocol, values, _PROTOCOL_DIFF_FIELDS)
    for key, value in values.items():
        setattr(protocol, key, value)
    protocol.synced_at = now
    protocol.save()
    if changed:
        report.protocols_updated += 1
        report.changed_protocol_ids.append(onchain_id)
        logger.info("protocol %s changed: %s", onchain_id, ",".join(changed))
    return protocol


def upsert_case(
    snapshot: dict,
    report: SyncReport,
    reader: HaltModuleReader,
    *,
    sync_events: bool = True,
) -> Case:
    onchain_id = to_int(snapshot.get("id"))
    values = case_fields(snapshot)
    now = timezone.now()
    report.cases_seen += 1

    protocol = _ensure_protocol(values["protocol_onchain_id"], report, reader)

    case = Case.objects.filter(onchain_id=onchain_id).first()
    if case is None:
        case = Case.objects.create(
            onchain_id=onchain_id, protocol=protocol, synced_at=now, **values
        )
        report.cases_created += 1
        if sync_events:
            _sync_events_for_case(case, report, reader)
        return case

    changed = _changed_fields(case, values, _CASE_DIFF_FIELDS)
    for key, value in values.items():
        setattr(case, key, value)
    case.protocol = protocol
    case.synced_at = now
    case.save()
    if changed:
        report.cases_updated += 1
        logger.info("case %s changed: %s", onchain_id, ",".join(changed))
    if sync_events:
        _sync_events_for_case(case, report, reader)
    return case


def upsert_case_event(
    snapshot: dict,
    report: SyncReport,
    reader: HaltModuleReader,
    case: Case | None = None,
) -> CaseEvent | None:
    """
    Idempotent insert by onchain_id.

    Historical payloads are append-only: an identical re-sync is a no-op, and
    a differing snapshot is refused (never rewritten).
    """
    onchain_id = to_int(snapshot.get("id"))
    values = event_fields(snapshot)
    case_onchain_id = to_int(snapshot.get("case_id"))
    report.events_seen += 1

    if case is None or case.onchain_id != case_onchain_id:
        case = _ensure_case(case_onchain_id, report, reader)

    existing = CaseEvent.objects.filter(onchain_id=onchain_id).first()
    if existing is None:
        event = CaseEvent.objects.create(
            onchain_id=onchain_id,
            case=case,
            synced_at=timezone.now(),
            **values,
        )
        report.events_created += 1
        return event

    if _changed_fields(existing, values, _EVENT_DIFF_FIELDS):
        logger.warning(
            "case event %s payload differs from chain; leaving stored row unchanged",
            onchain_id,
        )
        return existing
    return existing


def _ensure_protocol(
    protocol_onchain_id: int, report: SyncReport, reader: HaltModuleReader
) -> Protocol:
    """A case can arrive before its protocol has been paged in — fetch it."""
    protocol = Protocol.objects.filter(onchain_id=protocol_onchain_id).first()
    if protocol is not None:
        return protocol
    snapshot = reader.get_protocol(protocol_onchain_id)
    return upsert_protocol(snapshot, report)


def _ensure_case(
    case_onchain_id: int, report: SyncReport, reader: HaltModuleReader
) -> Case:
    """An event can arrive before its case has been paged in — fetch it."""
    case = Case.objects.filter(onchain_id=case_onchain_id).first()
    if case is not None:
        return case
    snapshot = reader.get_case(case_onchain_id)
    return upsert_case(snapshot, report, reader, sync_events=False)


def _sync_events_for_case(
    case: Case, report: SyncReport, reader: HaltModuleReader
) -> None:
    """Page `list_case_events` oldest-first until exhausted."""
    limit = _page_limit()
    offset = 0
    while True:
        page = reader.list_case_events(case.onchain_id, offset, limit)
        if not page:
            break
        for snapshot in page:
            upsert_case_event(snapshot, report, reader, case=case)
        offset += len(page)
        if len(page) < limit:
            break


# ---------------------------------------------------------------------------
# Sync entrypoints
# ---------------------------------------------------------------------------


def _page_limit(limit: int | None = None) -> int:
    configured = int(limit or settings.SYNC_PAGE_LIMIT)
    return max(1, min(configured, settings.API_MAX_PAGE_SIZE))


def sync_counts(reader: HaltModuleReader | None = None) -> dict:
    """Read the diff anchors and persist them on the cursor."""
    reader = reader or get_reader()
    ensure_contract_address(reader)
    protocol_count = reader.get_protocol_count()
    case_count = reader.get_case_count()
    case_event_count = reader.get_case_event_count()
    cursor = SyncCursor.load()
    cursor.mark_success(
        protocol_count=protocol_count,
        case_count=case_count,
        case_event_count=case_event_count,
        contract_address=reader.contract_address,
    )
    return {
        "protocol_count": protocol_count,
        "case_count": case_count,
        "case_event_count": case_event_count,
    }


def sync_protocols_page(
    offset: int, limit: int | None = None, reader: HaltModuleReader | None = None
) -> SyncReport:
    reader = reader or get_reader()
    report = SyncReport()
    snapshots = reader.list_protocols(int(offset), _page_limit(limit))
    with transaction.atomic():
        for snapshot in snapshots:
            upsert_protocol(snapshot, report)
    return report


def sync_cases_page(
    offset: int, limit: int | None = None, reader: HaltModuleReader | None = None
) -> SyncReport:
    reader = reader or get_reader()
    report = SyncReport()
    snapshots = reader.list_cases(int(offset), _page_limit(limit))
    with transaction.atomic():
        for snapshot in snapshots:
            upsert_case(snapshot, report, reader)
    return report


def sync_protocol(
    protocol_id: int,
    reader: HaltModuleReader | None = None,
    include_cases: bool = True,
) -> SyncReport:
    """
    Fast path used by `POST /api/sync/protocols/<id>` right after a wallet tx.

    Reads the protocol and (by default) every case attached to it, so a
    freshly accepted report shows up as HALTED plus its case detail in one hop.
    """
    reader = reader or get_reader()
    ensure_contract_address(reader)
    report = SyncReport()
    snapshot = reader.get_protocol(int(protocol_id))

    with transaction.atomic():
        protocol = upsert_protocol(snapshot, report)

    if include_cases and protocol.onchain_case_count:
        limit = _page_limit()
        offset = 0
        while offset < protocol.onchain_case_count:
            page = reader.list_protocol_cases(int(protocol_id), offset, limit)
            if not page:
                break
            with transaction.atomic():
                for case_snapshot in page:
                    upsert_case(case_snapshot, report, reader)
            offset += len(page)
            if len(page) < limit:
                break

    # Use chain counts — do not infer from onchain_id + 1 (wrong with gaps / partial sync).
    report.protocol_count = reader.get_protocol_count()
    report.case_count = reader.get_case_count()
    report.case_event_count = reader.get_case_event_count()
    return report


def sync_case(case_id: int, reader: HaltModuleReader | None = None) -> SyncReport:
    reader = reader or get_reader()
    report = SyncReport()
    snapshot = reader.get_case(int(case_id))
    with transaction.atomic():
        upsert_case(snapshot, report, reader)
    report.protocol_count = reader.get_protocol_count()
    report.case_count = reader.get_case_count()
    report.case_event_count = reader.get_case_event_count()
    return report


def poll_and_diff(reader: HaltModuleReader | None = None) -> dict:
    """
    Beat body: read counts, page in anything new, and refresh existing rows
    whose on-chain state can change without bumping a counter
    (HALTED → ACTIVE on unhalt, case → CLEARED).
    """
    reader = reader or get_reader()
    ensure_contract_address(reader)
    cursor = SyncCursor.load()
    report = SyncReport()

    try:
        protocol_count = reader.get_protocol_count()
        case_count = reader.get_case_count()
        case_event_count = reader.get_case_event_count()
        report.protocol_count = protocol_count
        report.case_count = case_count
        report.case_event_count = case_event_count

        limit = _page_limit()

        # Protocols are few and mutate in place, so refresh every page.
        offset = 0
        while offset < protocol_count:
            report.merge(sync_protocols_page(offset, limit, reader))
            offset += limit

        # Cases are append-only except for status transitions, so page in the
        # new tail and refresh the cases of protocols that just changed.
        known_cases = Case.objects.count()
        start = min(cursor.case_count, known_cases)
        offset = max(0, start)
        while offset < case_count:
            page_report = sync_cases_page(offset, limit, reader)
            report.merge(page_report)
            if page_report.cases_seen == 0:
                break
            offset += page_report.cases_seen

        for protocol_id in sorted(set(report.changed_protocol_ids)):
            report.merge(_sync_protocol_cases(protocol_id, reader))

        # Event sync strategy (V1.1-D5):
        # 1. Fast path / case upserts: after each case, page
        #    `list_case_events(case_id, …)` until exhausted (see upsert_case).
        # 2. poll_and_diff also pages *new* global events via
        #    get_case_event_count + get_case_event(id) for ids
        #    (cursor.case_event_count+1)…count. That catches events that do not
        #    mutate protocol status (failed challenge/unhalt, finalize_appeal).
        # Skip the RPC when the onchain_id is already stored. Historical
        # payloads are never rewritten.
        report.merge(_sync_new_global_events(reader, cursor, case_event_count))

        cursor.mark_success(
            protocol_count=protocol_count,
            case_count=case_count,
            case_event_count=case_event_count,
            contract_address=reader.contract_address,
        )
    except Exception as exc:
        cursor.mark_error(str(exc))
        raise

    result = report.as_dict()
    logger.info("poll_and_diff %s", result)
    return result


def _sync_protocol_cases(protocol_id: int, reader: HaltModuleReader) -> SyncReport:
    report = SyncReport()
    limit = _page_limit()
    offset = 0
    while True:
        page = reader.list_protocol_cases(int(protocol_id), offset, limit)
        if not page:
            break
        with transaction.atomic():
            for snapshot in page:
                upsert_case(snapshot, report, reader)
        offset += len(page)
        if len(page) < limit:
            break
    return report


def _sync_new_global_events(
    reader: HaltModuleReader, cursor: SyncCursor, event_count: int
) -> SyncReport:
    """Page newly appended global events by onchain id (1-indexed)."""
    report = SyncReport()
    report.case_event_count = event_count
    refreshed_cases: set[int] = set()
    start = int(cursor.case_event_count)
    for event_id in range(start + 1, int(event_count) + 1):
        if CaseEvent.objects.filter(onchain_id=event_id).exists():
            continue
        snapshot = reader.get_case_event(event_id)
        case_id = to_int(snapshot.get("case_id"))
        if case_id and case_id not in refreshed_cases:
            # Refresh the case head so bond_settled / status stay honest
            # (finalize_appeal does not bump protocol_count or case_count).
            with transaction.atomic():
                upsert_case(
                    reader.get_case(case_id), report, reader, sync_events=False
                )
            refreshed_cases.add(case_id)
        with transaction.atomic():
            upsert_case_event(snapshot, report, reader)
    return report
