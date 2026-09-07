"""Shared helpers for direct HaltModule tests (imported by test modules)."""

from __future__ import annotations

import json

DEFAULT_BOND = 100
DEFAULT_MIN_EVIDENCE = 1
TRUSTED_DOMAIN = "evidence.example.com"


def register_default_protocol(
    contract,
    *,
    name: str = "Demo Protocol",
    definition: str = "Halt if evidence shows an active drain of user funds.",
    domains: list[str] | None = None,
    actions: list[str] | None = None,
    allowed_while_halted: list[str] | None = None,
    bond: int = DEFAULT_BOND,
    min_evidence: int = DEFAULT_MIN_EVIDENCE,
    appeal_window_seconds: int = 86400,
) -> int:
    if domains is None:
        domains = [TRUSTED_DOMAIN]
    if actions is None:
        actions = ["withdraw", "transfer"]
    if allowed_while_halted is None:
        allowed_while_halted = []
    return contract.register_protocol(
        name,
        definition,
        json.dumps(domains),
        json.dumps(actions),
        json.dumps(allowed_while_halted),
        bond,
        min_evidence,
        appeal_window_seconds,
    )


def mock_exploit_true(vm, summary: str = "Active exploit confirmed") -> None:
    vm.clear_mocks()
    vm.mock_web(r".*", {"status": 200, "body": "INCIDENT: funds are being drained"})
    vm.mock_llm(r".*", json.dumps({"exploit": True, "summary": summary}))


def mock_exploit_false(vm, summary: str = "No active exploit") -> None:
    vm.clear_mocks()
    vm.mock_web(r".*", {"status": 200, "body": "All systems normal"})
    vm.mock_llm(r".*", json.dumps({"exploit": False, "summary": summary}))


def mock_remediated_true(vm, summary: str = "Patch deployed and verified") -> None:
    vm.clear_mocks()
    vm.mock_web(r".*", {"status": 200, "body": "Remediation complete; exploit closed"})
    vm.mock_llm(r".*", json.dumps({"remediated": True, "summary": summary}))


def mock_remediated_false(vm, summary: str = "Exploit still active") -> None:
    vm.clear_mocks()
    vm.mock_web(r".*", {"status": 200, "body": "Exploit still ongoing"})
    vm.mock_llm(r".*", json.dumps({"remediated": False, "summary": summary}))
