"""
In-memory stand-in for the deployed Halt Module.

It returns the exact view dict shapes produced by
`contracts/halt_module.py` (`_protocol_to_dict` / `_case_to_dict` /
`_event_to_dict`), so indexer tests exercise the real mapping without
studionet. Keep this in sync with the ABI freeze in
IMPLEMENTATION_PLAN_V1_1.md §2.5 / §3.2–3.5.
"""

from __future__ import annotations

import time

from apps.sync.genlayer_client import ContractCallError, GenLayerError

GOVERNOR = "0x" + "11" * 20
REPORTER = "0x" + "22" * 20
BACKUP = "0x" + "33" * 20
CHALLENGER = "0x" + "44" * 20
ONE_GEN = 10**18


class FakeHaltModule:
    """Duck-typed replacement for `HaltModuleReader`."""

    def __init__(self, contract_address: str = "0x" + "ab" * 20) -> None:
        self.contract_address = contract_address
        self.rpc_url = "memory://fake"
        self.protocols: dict[int, dict] = {}
        self.cases: dict[int, dict] = {}
        self.events: dict[int, dict] = {}
        self.calls: list[tuple[str, tuple]] = []
        self.fail_next: Exception | None = None

    # -- chain-side mutations (test helpers, not part of the read ABI) -----

    def register_protocol(
        self,
        name: str = "Demo Vault Protocol",
        exploit_definition: str = "Halt if evidence shows an active drain of user funds.",
        trusted_domains: list[str] | None = None,
        protected_actions: list[str] | None = None,
        allowed_while_halted: list[str] | None = None,
        reporter_bond: int = ONE_GEN,
        min_evidence: int = 1,
        appeal_window_seconds: int = 86400,
        backup_unhalters: list[str] | None = None,
        governor: str = GOVERNOR,
    ) -> int:
        protocol_id = len(self.protocols)
        backups = list(backup_unhalters or [])
        self.protocols[protocol_id] = {
            "id": protocol_id,
            "name": name,
            "exploit_definition": exploit_definition,
            "trusted_domains": trusted_domains or ["rentry.co"],
            "protected_actions": protected_actions or ["withdraw", "transfer"],
            "allowed_while_halted": allowed_while_halted or [],
            "reporter_bond": reporter_bond,
            "min_evidence": min_evidence,
            "appeal_window_seconds": appeal_window_seconds,
            "governor": governor,
            "backup_unhalters": backups,
            "status": "ACTIVE",
            "active_case_id": 0,
            "halted_at": 0,
            "case_count": 0,
            "created_at": int(time.time()),
        }
        return protocol_id

    def report_exploit(
        self,
        protocol_id: int,
        exploit: bool,
        allegation: str = "Funds are being drained right now.",
        evidence_urls: list[str] | None = None,
        summary: str = "",
        reporter: str = REPORTER,
    ) -> int:
        protocol = self._protocol(protocol_id)
        case_id = len(self.cases) + 1  # case ids are 1-indexed on-chain
        now = int(time.time())
        urls = evidence_urls or ["https://rentry.co/incident"]
        window = int(protocol["appeal_window_seconds"])
        verdict_summary = summary or (
            "Active exploit confirmed" if exploit else "No active exploit"
        )
        if exploit:
            to_status = "ACCEPTED_HALT"
            if window > 0:
                bond_settled = False
                disposition = "ESCROWED"
            else:
                bond_settled = True
                disposition = "REFUND_ACTOR"
            protocol["status"] = "HALTED"
            protocol["active_case_id"] = case_id
            protocol["halted_at"] = now
        else:
            to_status = "REJECTED"
            bond_settled = True
            disposition = "SLASH_GOVERNOR"

        self.cases[case_id] = {
            "id": case_id,
            "protocol_id": protocol_id,
            "reporter": reporter,
            "allegation": allegation,
            "evidence_urls": urls,
            "verdict_exploit": exploit,
            "verdict_summary": verdict_summary,
            "status": to_status,
            "bond_amount": protocol["reporter_bond"],
            "bond_settled": bond_settled,
            "event_count": 0,
            "submitted_at": now,
        }
        protocol["case_count"] += 1
        self._append_event(
            case_id=case_id,
            protocol_id=protocol_id,
            event_type="REPORT_EVALUATED",
            actor=reporter,
            statement=allegation,
            evidence_urls=urls,
            consensus_bool=exploit,
            consensus_summary=verdict_summary,
            from_status="OPEN",
            to_status=to_status,
            bond_amount=protocol["reporter_bond"],
            bond_disposition=disposition,
            created_at=now,
        )
        return case_id

    def request_unhalt(
        self,
        protocol_id: int,
        summary: str = "Patch verified",
        statement: str = "Remediation complete",
        actor: str = GOVERNOR,
        remediated: bool = True,
        evidence_urls: list[str] | None = None,
    ) -> bool:
        protocol = self._protocol(protocol_id)
        active_case_id = protocol["active_case_id"]
        now = int(time.time())
        urls = evidence_urls or ["https://rentry.co/remediation"]
        case = self.cases[active_case_id]
        from_status = case["status"]
        # Report-round verdict_* stay immutable — never concatenate unhalt text.
        if remediated:
            if not case["bond_settled"]:
                disposition = "PAY_REPORTER|REFUND_REPORTER"
                case["bond_settled"] = True
            else:
                disposition = "PAY_REPORTER"
            case["status"] = "CLEARED"
            protocol["status"] = "ACTIVE"
            protocol["active_case_id"] = 0
            protocol["halted_at"] = 0
            to_status = "CLEARED"
        else:
            disposition = "BURNED"
            to_status = from_status
        self._append_event(
            case_id=active_case_id,
            protocol_id=protocol_id,
            event_type="UNHALT_EVALUATED",
            actor=actor,
            statement=statement,
            evidence_urls=urls,
            consensus_bool=remediated,
            consensus_summary=summary,
            from_status=from_status,
            to_status=to_status,
            bond_amount=protocol["reporter_bond"],
            bond_disposition=disposition,
            created_at=now,
        )
        return remediated

    def challenge_halt(
        self,
        protocol_id: int,
        overturn: bool,
        summary: str = "",
        statement: str = "Halt was unjustified",
        actor: str = CHALLENGER,
        evidence_urls: list[str] | None = None,
    ) -> bool:
        protocol = self._protocol(protocol_id)
        active_case_id = protocol["active_case_id"]
        now = int(time.time())
        urls = evidence_urls or ["https://rentry.co/challenge"]
        case = self.cases[active_case_id]
        from_status = case["status"]
        consensus_summary = summary or (
            "Halt overturned" if overturn else "Halt stands"
        )
        if overturn:
            if not case["bond_settled"]:
                disposition = "SLASH_CHALLENGER|REFUND_ACTOR"
                case["bond_settled"] = True
            else:
                disposition = "REFUND_ACTOR"
            case["status"] = "OVERTURNED"
            protocol["status"] = "ACTIVE"
            protocol["active_case_id"] = 0
            protocol["halted_at"] = 0
            to_status = "OVERTURNED"
        else:
            disposition = "SLASH_REPORTER"
            to_status = from_status
        self._append_event(
            case_id=active_case_id,
            protocol_id=protocol_id,
            event_type="CHALLENGE_EVALUATED",
            actor=actor,
            statement=statement,
            evidence_urls=urls,
            consensus_bool=overturn,
            consensus_summary=consensus_summary,
            from_status=from_status,
            to_status=to_status,
            bond_amount=protocol["reporter_bond"],
            bond_disposition=disposition,
            created_at=now,
        )
        return overturn

    def finalize_appeal(self, protocol_id: int, actor: str = GOVERNOR) -> bool:
        protocol = self._protocol(protocol_id)
        active_case_id = protocol["active_case_id"]
        case = self.cases[active_case_id]
        now = int(time.time())
        case["bond_settled"] = True
        self._append_event(
            case_id=active_case_id,
            protocol_id=protocol_id,
            event_type="APPEAL_FINALIZED",
            actor=actor,
            statement="",
            evidence_urls=[],
            consensus_bool=False,
            consensus_summary="",
            from_status=case["status"],
            to_status=case["status"],
            bond_amount=protocol["reporter_bond"],
            bond_disposition="REFUND_REPORTER",
            created_at=now,
        )
        return True

    def _append_event(
        self,
        *,
        case_id: int,
        protocol_id: int,
        event_type: str,
        actor: str,
        statement: str,
        evidence_urls: list[str],
        consensus_bool: bool,
        consensus_summary: str,
        from_status: str,
        to_status: str,
        bond_amount,
        bond_disposition: str,
        created_at: int,
    ) -> int:
        event_id = len(self.events) + 1
        self.events[event_id] = {
            "id": event_id,
            "case_id": case_id,
            "protocol_id": protocol_id,
            "event_type": event_type,
            "actor": actor,
            "statement": statement,
            "evidence_urls_joined": "|".join(evidence_urls),
            "consensus_bool": consensus_bool,
            "consensus_summary": consensus_summary,
            "from_status": from_status,
            "to_status": to_status,
            "bond_amount": bond_amount,
            "bond_disposition": bond_disposition,
            "created_at": created_at,
        }
        self.cases[case_id]["event_count"] = int(
            self.cases[case_id].get("event_count") or 0
        ) + 1
        return event_id

    # -- read ABI (§3.2) ---------------------------------------------------

    def get_protocol_count(self) -> int:
        self._record("get_protocol_count")
        return len(self.protocols)

    def get_case_count(self) -> int:
        self._record("get_case_count")
        return len(self.cases)

    def get_case_event_count(self) -> int:
        self._record("get_case_event_count")
        return len(self.events)

    def get_protocol(self, protocol_id: int) -> dict:
        self._record("get_protocol", protocol_id)
        return dict(self._protocol(protocol_id))

    def get_case(self, case_id: int) -> dict:
        self._record("get_case", case_id)
        return dict(self._case(case_id))

    def get_case_event(self, event_id: int) -> dict:
        self._record("get_case_event", event_id)
        event = self.events.get(int(event_id))
        if event is None:
            raise ContractCallError("RPC error -32000: Case event does not exist")
        return dict(event)

    def list_protocols(self, offset: int, limit: int) -> list[dict]:
        self._record("list_protocols", offset, limit)
        ids = sorted(self.protocols)[offset : offset + limit]
        return [dict(self.protocols[i]) for i in ids]

    def list_cases(self, offset: int, limit: int) -> list[dict]:
        self._record("list_cases", offset, limit)
        ids = sorted(self.cases)[offset : offset + limit]
        return [dict(self.cases[i]) for i in ids]

    def list_protocol_cases(self, protocol_id: int, offset: int, limit: int) -> list[dict]:
        self._record("list_protocol_cases", protocol_id, offset, limit)
        self._protocol(protocol_id)
        ids = [
            case_id
            for case_id in sorted(self.cases)
            if self.cases[case_id]["protocol_id"] == int(protocol_id)
        ]
        return [dict(self.cases[i]) for i in ids[offset : offset + limit]]

    def list_case_events(self, case_id: int, offset: int, limit: int) -> list[dict]:
        self._record("list_case_events", case_id, offset, limit)
        self._case(case_id)
        ids = [
            event_id
            for event_id in sorted(self.events)
            if self.events[event_id]["case_id"] == int(case_id)
        ]
        return [dict(self.events[i]) for i in ids[offset : offset + limit]]

    def is_action_allowed(self, protocol_id: int, action: str) -> bool:
        self._record("is_action_allowed", protocol_id, action)
        protocol = self._protocol(protocol_id)
        if protocol["status"] == "ACTIVE":
            return True
        return action in protocol["allowed_while_halted"]

    # -- internals ---------------------------------------------------------

    def _record(self, method: str, *args) -> None:
        if self.fail_next is not None:
            error, self.fail_next = self.fail_next, None
            raise error
        self.calls.append((method, args))

    def _protocol(self, protocol_id: int) -> dict:
        protocol = self.protocols.get(int(protocol_id))
        if protocol is None:
            raise ContractCallError("RPC error -32000: Protocol does not exist")
        return protocol

    def _case(self, case_id: int) -> dict:
        case = self.cases.get(int(case_id))
        if case is None:
            raise ContractCallError("RPC error -32000: Case does not exist")
        return case

    def call_count(self, method: str) -> int:
        return sum(1 for name, _ in self.calls if name == method)


class UnreachableChain:
    """Reader whose every call fails like a studionet outage / rate limit."""

    contract_address = "0x" + "cd" * 20
    rpc_url = "memory://down"

    def __getattr__(self, _name):
        def _raise(*_args, **_kwargs):
            raise GenLayerError("RPC rate limited: -32006")

        return _raise
