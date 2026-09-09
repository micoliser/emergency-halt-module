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

from apps.cases.models import Case
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


@dataclass
class SyncReport:
    """What a sync run touched — returned to callers and logged."""

    protocols_seen: int = 0
    protocols_created: int = 0
    protocols_updated: int = 0
    cases_seen: int = 0
    cases_created: int = 0
    cases_updated: int = 0
    protocol_count: int = 0
    case_count: int = 0
    changed_protocol_ids: list[int] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "protocols_seen": self.protocols_seen,
            "protocols_created": self.protocols_created,
            "protocols_updated": self.protocols_updated,
            "cases_seen": self.cases_seen,
            "cases_created": self.cases_created,
            "cases_updated": self.cases_updated,
            "protocol_count": self.protocol_count,
            "case_count": self.case_count,
            "changed_protocol_ids": sorted(set(self.changed_protocol_ids)),
        }

    def merge(self, other: "SyncReport") -> "SyncReport":
        self.protocols_seen += other.protocols_seen
        self.protocols_created += other.protocols_created
        self.protocols_updated += other.protocols_updated
        self.cases_seen += other.cases_seen
        self.cases_created += other.cases_created
        self.cases_updated += other.cases_updated
        self.protocol_count = max(self.protocol_count, other.protocol_count)
        self.case_count = max(self.case_count, other.case_count)
        self.changed_protocol_ids.extend(other.changed_protocol_ids)
        return self


# ---------------------------------------------------------------------------
# Snapshot → model field mapping
# ---------------------------------------------------------------------------


def protocol_fields(snapshot: dict) -> dict:
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
        },
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
        "chain_submitted_at": unix_to_datetime(snapshot.get("submitted_at")),
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
    "chain_submitted_at",
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


def upsert_case(snapshot: dict, report: SyncReport, reader: HaltModuleReader) -> Case:
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
    return case


def _ensure_protocol(
    protocol_onchain_id: int, report: SyncReport, reader: HaltModuleReader
) -> Protocol:
    """A case can arrive before its protocol has been paged in — fetch it."""
    protocol = Protocol.objects.filter(onchain_id=protocol_onchain_id).first()
    if protocol is not None:
        return protocol
    snapshot = reader.get_protocol(protocol_onchain_id)
    return upsert_protocol(snapshot, report)


# ---------------------------------------------------------------------------
# Sync entrypoints
# ---------------------------------------------------------------------------


def _page_limit(limit: int | None = None) -> int:
    configured = int(limit or settings.SYNC_PAGE_LIMIT)
    return max(1, min(configured, settings.API_MAX_PAGE_SIZE))


def sync_counts(reader: HaltModuleReader | None = None) -> dict:
    """Read the diff anchors and persist them on the cursor."""
    reader = reader or get_reader()
    protocol_count = reader.get_protocol_count()
    case_count = reader.get_case_count()
    cursor = SyncCursor.load()
    cursor.mark_success(
        protocol_count=protocol_count,
        case_count=case_count,
        contract_address=reader.contract_address,
    )
    return {"protocol_count": protocol_count, "case_count": case_count}


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
    return report


def sync_case(case_id: int, reader: HaltModuleReader | None = None) -> SyncReport:
    reader = reader or get_reader()
    report = SyncReport()
    snapshot = reader.get_case(int(case_id))
    with transaction.atomic():
        upsert_case(snapshot, report, reader)
    return report


def poll_and_diff(reader: HaltModuleReader | None = None) -> dict:
    """
    Beat body: read counts, page in anything new, and refresh existing rows
    whose on-chain state can change without bumping a counter
    (HALTED → ACTIVE on unhalt, case → CLEARED).
    """
    reader = reader or get_reader()
    cursor = SyncCursor.load()
    report = SyncReport()

    try:
        protocol_count = reader.get_protocol_count()
        case_count = reader.get_case_count()
        report.protocol_count = protocol_count
        report.case_count = case_count

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

        cursor.mark_success(
            protocol_count=protocol_count,
            case_count=case_count,
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
