"""
In-memory stand-in for the deployed Halt Module.

It returns the exact view dict shapes produced by
`contracts/halt_module.py` (`_protocol_to_dict` / `_case_to_dict`), so indexer
tests exercise the real mapping without studionet. Keep this in sync with the
ABI freeze in IMPLEMENTATION_PLAN.md §3.2–3.5.
"""

from __future__ import annotations

import time

from apps.sync.genlayer_client import ContractCallError, GenLayerError

GOVERNOR = "0x" + "11" * 20
REPORTER = "0x" + "22" * 20
ONE_GEN = 10**18


class FakeHaltModule:
    """Duck-typed replacement for `HaltModuleReader`."""

    def __init__(self, contract_address: str = "0x" + "ab" * 20) -> None:
        self.contract_address = contract_address
        self.rpc_url = "memory://fake"
        self.protocols: dict[int, dict] = {}
        self.cases: dict[int, dict] = {}
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
        governor: str = GOVERNOR,
    ) -> int:
        protocol_id = len(self.protocols)
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
            "status": "ACTIVE",
            "active_case_id": 0,
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
        self.cases[case_id] = {
            "id": case_id,
            "protocol_id": protocol_id,
            "reporter": reporter,
            "allegation": allegation,
            "evidence_urls": evidence_urls or ["https://rentry.co/incident"],
            "verdict_exploit": exploit,
            "verdict_summary": summary
            or ("Active exploit confirmed" if exploit else "No active exploit"),
            "status": "ACCEPTED_HALT" if exploit else "REJECTED",
            "bond_amount": protocol["reporter_bond"],
            "bond_settled": True,
            "submitted_at": int(time.time()),
        }
        protocol["case_count"] += 1
        if exploit:
            protocol["status"] = "HALTED"
            protocol["active_case_id"] = case_id
        return case_id

    def request_unhalt(self, protocol_id: int, summary: str = "Patch verified") -> bool:
        protocol = self._protocol(protocol_id)
        active_case_id = protocol["active_case_id"]
        protocol["status"] = "ACTIVE"
        protocol["active_case_id"] = 0
        if active_case_id:
            case = self.cases[active_case_id]
            case["status"] = "CLEARED"
            case["verdict_summary"] = f"{case['verdict_summary']} | Unhalt: {summary}"
        return True

    # -- read ABI (§3.2) ---------------------------------------------------

    def get_protocol_count(self) -> int:
        self._record("get_protocol_count")
        return len(self.protocols)

    def get_case_count(self) -> int:
        self._record("get_case_count")
        return len(self.cases)

    def get_protocol(self, protocol_id: int) -> dict:
        self._record("get_protocol", protocol_id)
        return dict(self._protocol(protocol_id))

    def get_case(self, case_id: int) -> dict:
        self._record("get_case", case_id)
        case = self.cases.get(int(case_id))
        if case is None:
            raise ContractCallError("RPC error -32000: Case does not exist")
        return dict(case)

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
