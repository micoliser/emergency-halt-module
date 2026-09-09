"""Direct-mode tests for HaltModule (Phase 1–2 + v1.1 Phase A–C)."""

from __future__ import annotations

import json

import pytest

from helpers import (
    DEFAULT_BOND,
    TRUSTED_DOMAIN,
    address_hex,
    mock_exploit_false,
    mock_exploit_true,
    mock_overturn_false,
    mock_overturn_true,
    mock_remediated_false,
    mock_remediated_true,
    register_default_protocol,
    set_tx_timestamp,
)


def test_register_protocol_success(halt_module, direct_vm, direct_accounts):
    contract = halt_module
    direct_vm.sender = direct_accounts[0]

    pid = register_default_protocol(contract)
    assert pid == 0
    assert contract.get_protocol_count() == 1

    protocol = contract.get_protocol(0)
    assert protocol["name"] == "Demo Protocol"
    assert protocol["status"] == "ACTIVE"
    assert protocol["reporter_bond"] == DEFAULT_BOND
    assert protocol["min_evidence"] == 1
    assert protocol["trusted_domains"] == [TRUSTED_DOMAIN]
    assert "withdraw" in protocol["protected_actions"]
    assert protocol["allowed_while_halted"] == []
    assert protocol["active_case_id"] == 0
    assert int(protocol["halted_at"]) == 0
    assert protocol["backup_unhalters"] == []
    assert isinstance(protocol["governor"], str) and len(protocol["governor"]) > 0


def test_register_bad_domain(halt_module, direct_vm, direct_accounts):
    contract = halt_module
    direct_vm.sender = direct_accounts[0]

    with pytest.raises(Exception) as exc:
        contract.register_protocol(
            "Bad",
            "definition of exploit",
            json.dumps(["ftp://evil.example"]),
            json.dumps(["withdraw"]),
            json.dumps([]),
            DEFAULT_BOND,
            1,
            0,
            json.dumps([]),
        )
    assert "http" in str(exc.value).lower() or "domain" in str(exc.value).lower()

    with pytest.raises(Exception) as exc2:
        contract.register_protocol(
            "Bad",
            "definition of exploit",
            json.dumps(["example.com|evil.com"]),
            json.dumps(["withdraw"]),
            json.dumps([]),
            DEFAULT_BOND,
            1,
            0,
            json.dumps([]),
        )
    assert "|" in str(exc2.value) or "domain" in str(exc2.value).lower()


def test_register_empty_definition(halt_module, direct_vm, direct_accounts):
    contract = halt_module
    direct_vm.sender = direct_accounts[0]
    with pytest.raises(Exception) as exc:
        contract.register_protocol(
            "Name",
            "   ",
            json.dumps([TRUSTED_DOMAIN]),
            json.dumps(["withdraw"]),
            json.dumps([]),
            DEFAULT_BOND,
            1,
            0,
            json.dumps([]),
        )
    assert "exploit_definition" in str(exc.value)


def test_register_duplicate_domains(halt_module, direct_vm, direct_accounts):
    contract = halt_module
    direct_vm.sender = direct_accounts[0]
    with pytest.raises(Exception) as exc:
        contract.register_protocol(
            "Name",
            "definition",
            json.dumps(["https://www.example.com", "example.com"]),
            json.dumps(["withdraw"]),
            json.dumps([]),
            DEFAULT_BOND,
            1,
            0,
            json.dumps([]),
        )
    assert "distinct" in str(exc.value).lower()


def test_register_overlap_allowed_and_protected(halt_module, direct_vm, direct_accounts):
    contract = halt_module
    direct_vm.sender = direct_accounts[0]
    with pytest.raises(Exception) as exc:
        contract.register_protocol(
            "Name",
            "definition",
            json.dumps([TRUSTED_DOMAIN]),
            json.dumps(["withdraw", "transfer"]),
            json.dumps(["withdraw"]),
            DEFAULT_BOND,
            1,
            0,
            json.dumps([]),
        )
    assert "overlap" in str(exc.value).lower()


def test_is_action_allowed_active(halt_module, direct_vm, direct_accounts):
    contract = halt_module
    direct_vm.sender = direct_accounts[0]
    register_default_protocol(contract)
    assert contract.is_action_allowed(0, "withdraw") is True
    assert contract.is_action_allowed(0, "transfer") is True
    assert contract.is_action_allowed(0, "deposit") is True


def test_pagination_empty_and_overflow(halt_module, direct_vm, direct_accounts):
    contract = halt_module
    direct_vm.sender = direct_accounts[0]

    assert contract.list_protocols(0, 10) == []
    assert contract.list_cases(0, 10) == []

    register_default_protocol(contract, name="P0")
    register_default_protocol(contract, name="P1")
    register_default_protocol(contract, name="P2")

    page = contract.list_protocols(0, 2)
    assert len(page) == 2
    assert page[0]["name"] == "P0"
    assert page[1]["name"] == "P1"

    page2 = contract.list_protocols(2, 10)
    assert len(page2) == 1
    assert page2[0]["name"] == "P2"

    assert contract.list_protocols(99, 10) == []
    assert contract.list_protocols(0, 0)  # limit 0 -> default; non-empty
    assert len(contract.list_protocols(0, 1000)) == 3  # capped but still returns all 3


def test_report_bond_mismatch(halt_module, direct_vm, direct_accounts):
    contract = halt_module
    direct_vm.sender = direct_accounts[0]
    register_default_protocol(contract)

    reporter = direct_accounts[1]
    direct_vm.sender = reporter
    direct_vm.value = DEFAULT_BOND - 1
    with pytest.raises(Exception) as exc:
        contract.report_exploit(
            0,
            "Funds are being drained",
            json.dumps([f"https://{TRUSTED_DOMAIN}/incident"]),
        )
    assert "exactly" in str(exc.value).lower() or "bond" in str(exc.value).lower()


def test_report_untrusted_url(halt_module, direct_vm, direct_accounts):
    contract = halt_module
    direct_vm.sender = direct_accounts[0]
    register_default_protocol(contract)

    reporter = direct_accounts[1]
    direct_vm.sender = reporter
    direct_vm.value = DEFAULT_BOND
    with pytest.raises(Exception) as exc:
        contract.report_exploit(
            0,
            "Funds are being drained",
            json.dumps(["https://evil.example.org/fake-incident"]),
        )
    assert "trusted" in str(exc.value).lower()


def test_report_userinfo_host_trick(halt_module, direct_vm, direct_accounts):
    """https://trusted@evil.com must not pass the trusted-domain gate."""
    contract = halt_module
    direct_vm.sender = direct_accounts[0]
    register_default_protocol(contract)

    reporter = direct_accounts[1]
    direct_vm.sender = reporter
    direct_vm.value = DEFAULT_BOND
    with pytest.raises(Exception) as exc:
        contract.report_exploit(
            0,
            "Spoofed evidence",
            json.dumps([f"https://{TRUSTED_DOMAIN}@evil.example.org/x"]),
        )
    assert "trusted" in str(exc.value).lower()


def test_report_exploit_true_halts(halt_module, direct_vm, direct_accounts):
    contract = halt_module
    governor = direct_accounts[0]
    direct_vm.sender = governor
    register_default_protocol(contract, allowed_while_halted=["deposit"])

    mock_exploit_true(direct_vm)
    direct_vm.strict_mocks = True

    reporter = direct_accounts[1]
    direct_vm.sender = reporter
    direct_vm.value = DEFAULT_BOND
    case_id = contract.report_exploit(
        0,
        "Active drain observed",
        json.dumps([f"https://{TRUSTED_DOMAIN}/incident"]),
    )
    assert case_id == 1

    protocol = contract.get_protocol(0)
    assert protocol["status"] == "HALTED"
    assert protocol["active_case_id"] == 1
    assert int(protocol["halted_at"]) > 0
    assert protocol["allowed_while_halted"] == ["deposit"]
    # Fail-closed: protected and unknown actions denied; allowlist permitted.
    assert contract.is_action_allowed(0, "withdraw") is False
    assert contract.is_action_allowed(0, "transfer") is False
    assert contract.is_action_allowed(0, "withdraws") is False
    assert contract.is_action_allowed(0, "deposit") is True

    case = contract.get_case(1)
    assert case["status"] == "ACCEPTED_HALT"
    assert case["verdict_exploit"] is True
    # Default appeal_window > 0: reporter bond is escrowed, not refunded.
    assert case["bond_settled"] is False
    assert case["reporter"]
    assert int(case["event_count"]) == 1

    events = contract.list_case_events(1, 0, 10)
    assert len(events) == 1
    assert events[0]["event_type"] == "REPORT_EVALUATED"
    assert events[0]["consensus_bool"] is True
    assert events[0]["from_status"] == "OPEN"
    assert events[0]["to_status"] == "ACCEPTED_HALT"
    assert events[0]["bond_disposition"] == "ESCROWED"
    assert int(events[0]["bond_amount"]) == DEFAULT_BOND
    assert events[0]["actor"] == case["reporter"]
    assert events[0]["statement"] == "Active drain observed"


def test_report_exploit_false_stays_active(halt_module, direct_vm, direct_accounts):
    contract = halt_module
    direct_vm.sender = direct_accounts[0]
    register_default_protocol(contract)

    mock_exploit_false(direct_vm)

    reporter = direct_accounts[1]
    direct_vm.sender = reporter
    direct_vm.value = DEFAULT_BOND
    case_id = contract.report_exploit(
        0,
        "Maybe an exploit?",
        json.dumps([f"https://{TRUSTED_DOMAIN}/clean"]),
    )
    assert case_id == 1

    protocol = contract.get_protocol(0)
    assert protocol["status"] == "ACTIVE"
    assert protocol["active_case_id"] == 0
    assert int(protocol["halted_at"]) == 0
    assert contract.is_action_allowed(0, "withdraw") is True

    case = contract.get_case(1)
    assert case["status"] == "REJECTED"
    assert case["verdict_exploit"] is False
    assert case["bond_settled"] is True

    events = contract.list_case_events(1, 0, 10)
    assert len(events) == 1
    assert events[0]["event_type"] == "REPORT_EVALUATED"
    assert events[0]["consensus_bool"] is False
    assert events[0]["to_status"] == "REJECTED"
    assert events[0]["bond_disposition"] == "SLASH_GOVERNOR"
    assert int(events[0]["bond_amount"]) == DEFAULT_BOND


def test_non_governor_unhalt_reverts(halt_module, direct_vm, direct_accounts):
    contract = halt_module
    direct_vm.sender = direct_accounts[0]
    register_default_protocol(contract)

    mock_exploit_true(direct_vm)
    reporter = direct_accounts[1]
    direct_vm.sender = reporter
    direct_vm.value = DEFAULT_BOND
    contract.report_exploit(
        0,
        "Active drain observed",
        json.dumps([f"https://{TRUSTED_DOMAIN}/incident"]),
    )

    mock_remediated_true(direct_vm)
    direct_vm.sender = reporter
    direct_vm.value = DEFAULT_BOND
    with pytest.raises(Exception) as exc:
        contract.request_unhalt(
            0,
            "We patched it",
            json.dumps([f"https://{TRUSTED_DOMAIN}/fix"]),
        )
    assert "governor" in str(exc.value).lower() or "backup" in str(exc.value).lower()


def test_governor_unhalt_success(halt_module, direct_vm, direct_accounts):
    contract = halt_module
    governor = direct_accounts[0]
    direct_vm.sender = governor
    register_default_protocol(contract)

    mock_exploit_true(direct_vm)
    reporter = direct_accounts[1]
    direct_vm.sender = reporter
    direct_vm.value = DEFAULT_BOND
    contract.report_exploit(
        0,
        "Active drain observed",
        json.dumps([f"https://{TRUSTED_DOMAIN}/incident"]),
    )
    assert contract.get_protocol(0)["status"] == "HALTED"
    report_summary = contract.get_case(1)["verdict_summary"]
    assert report_summary

    mock_remediated_true(direct_vm)
    direct_vm.sender = governor
    direct_vm.value = DEFAULT_BOND
    ok = contract.request_unhalt(
        0,
        "Patch deployed; drains stopped",
        json.dumps([f"https://{TRUSTED_DOMAIN}/remediation"]),
    )
    assert ok is True

    protocol = contract.get_protocol(0)
    assert protocol["status"] == "ACTIVE"
    assert protocol["active_case_id"] == 0
    assert int(protocol["halted_at"]) == 0
    assert contract.is_action_allowed(0, "withdraw") is True

    case = contract.get_case(1)
    assert case["status"] == "CLEARED"
    assert case["bond_settled"] is True
    # Report-round verdict stays immutable; unhalt is an appended event.
    assert case["verdict_summary"] == report_summary
    assert "Unhalt:" not in case["verdict_summary"]

    events = contract.list_case_events(1, 0, 10)
    assert len(events) == 2
    unhalt_event = events[1]
    assert unhalt_event["event_type"] == "UNHALT_EVALUATED"
    assert unhalt_event["consensus_bool"] is True
    assert unhalt_event["to_status"] == "CLEARED"
    assert unhalt_event["bond_disposition"] == "PAY_REPORTER|REFUND_REPORTER"
    assert int(unhalt_event["bond_amount"]) == DEFAULT_BOND


def test_governor_unhalt_not_remediated(halt_module, direct_vm, direct_accounts):
    contract = halt_module
    governor = direct_accounts[0]
    direct_vm.sender = governor
    register_default_protocol(contract)

    mock_exploit_true(direct_vm)
    reporter = direct_accounts[1]
    direct_vm.sender = reporter
    direct_vm.value = DEFAULT_BOND
    contract.report_exploit(
        0,
        "Active drain observed",
        json.dumps([f"https://{TRUSTED_DOMAIN}/incident"]),
    )
    report_summary = contract.get_case(1)["verdict_summary"]

    mock_remediated_false(direct_vm)
    direct_vm.sender = governor
    direct_vm.value = DEFAULT_BOND
    ok = contract.request_unhalt(
        0,
        "Please unhalt",
        json.dumps([f"https://{TRUSTED_DOMAIN}/still-broken"]),
    )
    assert ok is False
    protocol = contract.get_protocol(0)
    assert protocol["status"] == "HALTED"
    assert int(protocol["halted_at"]) > 0
    assert protocol["active_case_id"] == 1

    case = contract.get_case(1)
    assert case["status"] == "ACCEPTED_HALT"
    assert case["bond_settled"] is False
    assert case["verdict_summary"] == report_summary
    assert int(case["event_count"]) == 2

    events = contract.list_case_events(1, 0, 10)
    assert events[0]["event_type"] == "REPORT_EVALUATED"
    unhalt_event = events[1]
    assert unhalt_event["event_type"] == "UNHALT_EVALUATED"
    assert unhalt_event["consensus_bool"] is False
    assert unhalt_event["bond_disposition"] == "BURNED"
    assert unhalt_event["from_status"] == "ACCEPTED_HALT"
    assert unhalt_event["to_status"] == "ACCEPTED_HALT"
    assert int(unhalt_event["bond_amount"]) == DEFAULT_BOND


def test_list_protocol_cases(halt_module, direct_vm, direct_accounts):
    contract = halt_module
    direct_vm.sender = direct_accounts[0]
    register_default_protocol(contract)

    mock_exploit_false(direct_vm)
    reporter = direct_accounts[1]
    direct_vm.sender = reporter
    direct_vm.value = DEFAULT_BOND
    contract.report_exploit(
        0,
        "False alarm",
        json.dumps([f"https://{TRUSTED_DOMAIN}/a"]),
    )

    mock_exploit_false(direct_vm)
    direct_vm.value = DEFAULT_BOND
    contract.report_exploit(
        0,
        "Still false",
        json.dumps([f"https://{TRUSTED_DOMAIN}/b"]),
    )

    cases = contract.list_protocol_cases(0, 0, 10)
    assert len(cases) == 2
    assert cases[0]["id"] == 1
    assert cases[1]["id"] == 2
    assert contract.list_protocol_cases(0, 10, 10) == []


def test_domain_url_normalization_on_register(halt_module, direct_vm, direct_accounts):
    contract = halt_module
    direct_vm.sender = direct_accounts[0]
    pid = contract.register_protocol(
        "Norm",
        "definition",
        json.dumps([f"https://www.{TRUSTED_DOMAIN}/path"]),
        json.dumps(["withdraw"]),
        json.dumps([]),
        DEFAULT_BOND,
        1,
        0,
        json.dumps([]),
    )
    protocol = contract.get_protocol(pid)
    assert protocol["trusted_domains"] == [TRUSTED_DOMAIN]


def test_halted_fail_closed_empty_allowlist(halt_module, direct_vm, direct_accounts):
    """With empty allowed_while_halted, every action is denied while HALTED."""
    contract = halt_module
    direct_vm.sender = direct_accounts[0]
    register_default_protocol(contract)  # allowed_while_halted defaults to []

    mock_exploit_true(direct_vm)
    direct_vm.sender = direct_accounts[1]
    direct_vm.value = DEFAULT_BOND
    contract.report_exploit(
        0,
        "Active drain",
        json.dumps([f"https://{TRUSTED_DOMAIN}/incident"]),
    )

    assert contract.get_protocol(0)["status"] == "HALTED"
    assert contract.is_action_allowed(0, "withdraw") is False
    assert contract.is_action_allowed(0, "deposit") is False
    assert contract.is_action_allowed(0, "anything") is False


def test_report_true_window_zero_refunds_reporter(halt_module, direct_vm, direct_accounts):
    contract = halt_module
    direct_vm.sender = direct_accounts[0]
    register_default_protocol(contract, appeal_window_seconds=0)

    mock_exploit_true(direct_vm)
    reporter = direct_accounts[1]
    direct_vm.sender = reporter
    direct_vm.value = DEFAULT_BOND
    contract.report_exploit(
        0,
        "Active drain observed",
        json.dumps([f"https://{TRUSTED_DOMAIN}/incident"]),
    )

    protocol = contract.get_protocol(0)
    assert protocol["status"] == "HALTED"
    assert int(protocol["halted_at"]) > 0

    case = contract.get_case(1)
    assert case["status"] == "ACCEPTED_HALT"
    assert case["bond_settled"] is True

    events = contract.list_case_events(1, 0, 10)
    assert len(events) == 1
    assert events[0]["event_type"] == "REPORT_EVALUATED"
    assert events[0]["bond_disposition"] == "REFUND_ACTOR"
    assert int(events[0]["bond_amount"]) == DEFAULT_BOND


def test_list_case_events_oldest_first_and_pagination(
    halt_module, direct_vm, direct_accounts
):
    contract = halt_module
    governor = direct_accounts[0]
    direct_vm.sender = governor
    register_default_protocol(contract)

    mock_exploit_true(direct_vm)
    reporter = direct_accounts[1]
    direct_vm.sender = reporter
    direct_vm.value = DEFAULT_BOND
    contract.report_exploit(
        0,
        "Active drain observed",
        json.dumps([f"https://{TRUSTED_DOMAIN}/incident"]),
    )

    mock_remediated_true(direct_vm)
    direct_vm.sender = governor
    direct_vm.value = DEFAULT_BOND
    contract.request_unhalt(
        0,
        "Patch deployed; drains stopped",
        json.dumps([f"https://{TRUSTED_DOMAIN}/remediation"]),
    )

    assert int(contract.get_case_event_count()) == 2
    assert int(contract.get_case(1)["event_count"]) == 2

    events = contract.list_case_events(1, 0, 10)
    assert [e["event_type"] for e in events] == [
        "REPORT_EVALUATED",
        "UNHALT_EVALUATED",
    ]
    assert events[0]["id"] < events[1]["id"]
    assert events[0]["to_status"] == "ACCEPTED_HALT"
    assert events[1]["to_status"] == "CLEARED"
    assert events[1]["consensus_bool"] is True
    assert events[1]["bond_disposition"] == "PAY_REPORTER|REFUND_REPORTER"

    page0 = contract.list_case_events(1, 0, 1)
    assert len(page0) == 1
    assert page0[0]["event_type"] == "REPORT_EVALUATED"

    page1 = contract.list_case_events(1, 1, 1)
    assert len(page1) == 1
    assert page1[0]["event_type"] == "UNHALT_EVALUATED"

    assert contract.list_case_events(1, 99, 10) == []
    # limit 0 → default; oversize limit is capped at MAX_PAGE_LIMIT.
    assert len(contract.list_case_events(1, 0, 0)) == 2
    assert len(contract.list_case_events(1, 0, 1000)) == 2

    fetched = contract.get_case_event(page0[0]["id"])
    assert fetched["event_type"] == "REPORT_EVALUATED"
    assert fetched["id"] == page0[0]["id"]

    with pytest.raises(Exception) as exc:
        contract.get_case_event(99)
    assert "event" in str(exc.value).lower()

    with pytest.raises(Exception) as exc2:
        contract.list_case_events(99, 0, 10)
    assert "case" in str(exc2.value).lower()


ZERO_ADDRESS = "0x" + "00" * 20
BACKUP_A = "0x" + "11" * 20
BACKUP_B = "0x" + "22" * 20
BACKUP_C = "0x" + "33" * 20
BACKUP_D = "0x" + "44" * 20


def test_backup_unhalt_success(halt_module, direct_vm, direct_accounts):
    contract = halt_module
    governor = direct_accounts[0]
    backup = direct_accounts[2]
    direct_vm.sender = governor
    register_default_protocol(contract, backup_unhalters=[backup])

    protocol = contract.get_protocol(0)
    assert [b.lower() for b in protocol["backup_unhalters"]] == [
        address_hex(backup).lower()
    ]

    mock_exploit_true(direct_vm)
    reporter = direct_accounts[1]
    direct_vm.sender = reporter
    direct_vm.value = DEFAULT_BOND
    contract.report_exploit(
        0,
        "Active drain observed",
        json.dumps([f"https://{TRUSTED_DOMAIN}/incident"]),
    )
    report_summary = contract.get_case(1)["verdict_summary"]

    mock_remediated_true(direct_vm)
    direct_vm.sender = backup
    direct_vm.value = DEFAULT_BOND
    ok = contract.request_unhalt(
        0,
        "Patch deployed by backup",
        json.dumps([f"https://{TRUSTED_DOMAIN}/remediation"]),
    )
    assert ok is True

    protocol = contract.get_protocol(0)
    assert protocol["status"] == "ACTIVE"
    assert protocol["active_case_id"] == 0
    assert int(protocol["halted_at"]) == 0

    case = contract.get_case(1)
    assert case["status"] == "CLEARED"
    assert case["bond_settled"] is True
    assert case["verdict_summary"] == report_summary

    events = contract.list_case_events(1, 0, 10)
    unhalt_event = events[1]
    assert unhalt_event["event_type"] == "UNHALT_EVALUATED"
    assert unhalt_event["consensus_bool"] is True
    assert unhalt_event["actor"].lower() == address_hex(backup).lower()
    assert unhalt_event["bond_disposition"] == "PAY_REPORTER|REFUND_REPORTER"
    assert int(unhalt_event["bond_amount"]) == DEFAULT_BOND


def test_unhalt_wrong_bond_reverts(halt_module, direct_vm, direct_accounts):
    contract = halt_module
    governor = direct_accounts[0]
    direct_vm.sender = governor
    register_default_protocol(contract)

    mock_exploit_true(direct_vm)
    reporter = direct_accounts[1]
    direct_vm.sender = reporter
    direct_vm.value = DEFAULT_BOND
    contract.report_exploit(
        0,
        "Active drain observed",
        json.dumps([f"https://{TRUSTED_DOMAIN}/incident"]),
    )

    mock_remediated_true(direct_vm)
    direct_vm.sender = governor
    direct_vm.value = DEFAULT_BOND - 1
    with pytest.raises(Exception) as exc:
        contract.request_unhalt(
            0,
            "Patch deployed; drains stopped",
            json.dumps([f"https://{TRUSTED_DOMAIN}/remediation"]),
        )
    assert "exactly" in str(exc.value).lower() or "bond" in str(exc.value).lower()
    assert contract.get_protocol(0)["status"] == "HALTED"
    assert int(contract.get_case(1)["event_count"]) == 1


def test_unhalt_success_window_zero_pays_reporter_only(
    halt_module, direct_vm, direct_accounts
):
    contract = halt_module
    governor = direct_accounts[0]
    direct_vm.sender = governor
    register_default_protocol(contract, appeal_window_seconds=0)

    mock_exploit_true(direct_vm)
    reporter = direct_accounts[1]
    direct_vm.sender = reporter
    direct_vm.value = DEFAULT_BOND
    contract.report_exploit(
        0,
        "Active drain observed",
        json.dumps([f"https://{TRUSTED_DOMAIN}/incident"]),
    )
    assert contract.get_case(1)["bond_settled"] is True
    report_summary = contract.get_case(1)["verdict_summary"]

    mock_remediated_true(direct_vm)
    direct_vm.sender = governor
    direct_vm.value = DEFAULT_BOND
    ok = contract.request_unhalt(
        0,
        "Patch deployed; drains stopped",
        json.dumps([f"https://{TRUSTED_DOMAIN}/remediation"]),
    )
    assert ok is True
    assert contract.get_protocol(0)["status"] == "ACTIVE"

    case = contract.get_case(1)
    assert case["status"] == "CLEARED"
    assert case["bond_settled"] is True
    assert case["verdict_summary"] == report_summary

    events = contract.list_case_events(1, 0, 10)
    assert events[1]["event_type"] == "UNHALT_EVALUATED"
    assert events[1]["bond_disposition"] == "PAY_REPORTER"
    assert "REFUND_REPORTER" not in events[1]["bond_disposition"]


def test_unhalt_llm_failure_reverts_without_burn(
    halt_module, direct_vm, direct_accounts
):
    contract = halt_module
    governor = direct_accounts[0]
    direct_vm.sender = governor
    register_default_protocol(contract)

    mock_exploit_true(direct_vm)
    reporter = direct_accounts[1]
    direct_vm.sender = reporter
    direct_vm.value = DEFAULT_BOND
    contract.report_exploit(
        0,
        "Active drain observed",
        json.dumps([f"https://{TRUSTED_DOMAIN}/incident"]),
    )

    direct_vm.clear_mocks()
    direct_vm.mock_web(r".*", {"status": 200, "body": "Remediation notes"})
    direct_vm.mock_llm(r".*", "not-json garbage")
    direct_vm.sender = governor
    direct_vm.value = DEFAULT_BOND
    with pytest.raises(Exception):
        contract.request_unhalt(
            0,
            "Please unhalt",
            json.dumps([f"https://{TRUSTED_DOMAIN}/remediation"]),
        )
    protocol = contract.get_protocol(0)
    assert protocol["status"] == "HALTED"
    case = contract.get_case(1)
    assert case["status"] == "ACCEPTED_HALT"
    assert int(case["event_count"]) == 1
    assert case["bond_settled"] is False


def test_register_backup_unhalters_bounds(halt_module, direct_vm, direct_accounts):
    contract = halt_module
    governor = direct_accounts[0]
    direct_vm.sender = governor

    pid0 = register_default_protocol(contract, name="Zero backups")
    assert contract.get_protocol(pid0)["backup_unhalters"] == []

    pid3 = contract.register_protocol(
        "Three backups",
        "definition",
        json.dumps([TRUSTED_DOMAIN]),
        json.dumps(["withdraw"]),
        json.dumps([]),
        DEFAULT_BOND,
        1,
        0,
        json.dumps([BACKUP_A, BACKUP_B, BACKUP_C]),
    )
    stored = [b.lower() for b in contract.get_protocol(pid3)["backup_unhalters"]]
    assert stored == [BACKUP_A.lower(), BACKUP_B.lower(), BACKUP_C.lower()]

    with pytest.raises(Exception) as exc4:
        contract.register_protocol(
            "Four backups",
            "definition",
            json.dumps([TRUSTED_DOMAIN]),
            json.dumps(["withdraw"]),
            json.dumps([]),
            DEFAULT_BOND,
            1,
            0,
            json.dumps([BACKUP_A, BACKUP_B, BACKUP_C, BACKUP_D]),
        )
    assert "backup" in str(exc4.value).lower() or "at most" in str(exc4.value).lower()

    with pytest.raises(Exception) as exc0:
        contract.register_protocol(
            "Zero addr",
            "definition",
            json.dumps([TRUSTED_DOMAIN]),
            json.dumps(["withdraw"]),
            json.dumps([]),
            DEFAULT_BOND,
            1,
            0,
            json.dumps([ZERO_ADDRESS]),
        )
    assert "zero" in str(exc0.value).lower()

    pid_ignore = contract.register_protocol(
        "Ignore governor",
        "definition",
        json.dumps([TRUSTED_DOMAIN]),
        json.dumps(["withdraw"]),
        json.dumps([]),
        DEFAULT_BOND,
        1,
        0,
        json.dumps([address_hex(governor), BACKUP_A, BACKUP_A]),
    )
    stored_ignore = [
        b.lower() for b in contract.get_protocol(pid_ignore)["backup_unhalters"]
    ]
    assert stored_ignore == [BACKUP_A.lower()]
    assert address_hex(governor).lower() not in stored_ignore


def _halt_default(contract, direct_vm, reporter, *, pid: int = 0) -> int:
    mock_exploit_true(direct_vm)
    direct_vm.sender = reporter
    direct_vm.value = DEFAULT_BOND
    return contract.report_exploit(
        pid,
        "Active drain observed",
        json.dumps([f"https://{TRUSTED_DOMAIN}/incident"]),
    )


def test_challenge_success_in_window(halt_module, direct_vm, direct_accounts):
    """T8: overturn in window → OVERTURNED, ACTIVE, escrow to challenger."""
    contract = halt_module
    governor = direct_accounts[0]
    reporter = direct_accounts[1]
    challenger = direct_accounts[2]
    direct_vm.sender = governor
    register_default_protocol(contract)

    _halt_default(contract, direct_vm, reporter)
    assert contract.get_protocol(0)["status"] == "HALTED"
    assert contract.get_case(1)["bond_settled"] is False
    report_summary = contract.get_case(1)["verdict_summary"]

    mock_overturn_true(direct_vm)
    direct_vm.sender = challenger
    direct_vm.value = DEFAULT_BOND
    ok = contract.challenge_halt(
        0,
        "Halt was a false alarm; no active exploit",
        json.dumps([f"https://{TRUSTED_DOMAIN}/overturn"]),
    )
    assert ok is True

    protocol = contract.get_protocol(0)
    assert protocol["status"] == "ACTIVE"
    assert protocol["active_case_id"] == 0
    assert int(protocol["halted_at"]) == 0
    assert contract.is_action_allowed(0, "withdraw") is True

    case = contract.get_case(1)
    assert case["status"] == "OVERTURNED"
    assert case["bond_settled"] is True
    assert case["verdict_summary"] == report_summary

    events = contract.list_case_events(1, 0, 10)
    assert len(events) == 2
    challenge_event = events[1]
    assert challenge_event["event_type"] == "CHALLENGE_EVALUATED"
    assert challenge_event["consensus_bool"] is True
    assert challenge_event["from_status"] == "ACCEPTED_HALT"
    assert challenge_event["to_status"] == "OVERTURNED"
    assert challenge_event["bond_disposition"] == "SLASH_CHALLENGER|REFUND_ACTOR"
    assert int(challenge_event["bond_amount"]) == DEFAULT_BOND
    assert challenge_event["actor"].lower() == address_hex(challenger).lower()

    mock_overturn_true(direct_vm)
    direct_vm.sender = challenger
    direct_vm.value = DEFAULT_BOND
    with pytest.raises(Exception) as exc:
        contract.challenge_halt(
            0,
            "Try again after overturn",
            json.dumps([f"https://{TRUSTED_DOMAIN}/overturn"]),
        )
    assert "halted" in str(exc.value).lower()


def test_challenge_fail_pays_reporter(halt_module, direct_vm, direct_accounts):
    """T9: overturn=false → still HALTED; challenger B → reporter, not governor."""
    contract = halt_module
    governor = direct_accounts[0]
    reporter = direct_accounts[1]
    challenger = direct_accounts[2]
    direct_vm.sender = governor
    register_default_protocol(contract)

    _halt_default(contract, direct_vm, reporter)
    halted_at = int(contract.get_protocol(0)["halted_at"])

    mock_overturn_false(direct_vm)
    direct_vm.sender = challenger
    direct_vm.value = DEFAULT_BOND
    ok = contract.challenge_halt(
        0,
        "This halt is wrong",
        json.dumps([f"https://{TRUSTED_DOMAIN}/still-exploited"]),
    )
    assert ok is False

    protocol = contract.get_protocol(0)
    assert protocol["status"] == "HALTED"
    assert protocol["active_case_id"] == 1
    assert int(protocol["halted_at"]) == halted_at

    case = contract.get_case(1)
    assert case["status"] == "ACCEPTED_HALT"
    assert case["bond_settled"] is False

    events = contract.list_case_events(1, 0, 10)
    assert len(events) == 2
    challenge_event = events[1]
    assert challenge_event["event_type"] == "CHALLENGE_EVALUATED"
    assert challenge_event["consensus_bool"] is False
    assert challenge_event["bond_disposition"] == "SLASH_REPORTER"
    assert "SLASH_GOVERNOR" not in challenge_event["bond_disposition"]
    assert int(challenge_event["bond_amount"]) == DEFAULT_BOND
    assert challenge_event["to_status"] == "ACCEPTED_HALT"


def test_challenge_after_window_reverts(
    halt_module, direct_vm, direct_accounts, monkeypatch
):
    """T10: challenge after halted_at + window reverts."""
    contract = halt_module
    governor = direct_accounts[0]
    reporter = direct_accounts[1]
    challenger = direct_accounts[2]
    window = 100
    direct_vm.sender = governor
    register_default_protocol(contract, appeal_window_seconds=window)

    _halt_default(contract, direct_vm, reporter)
    halted_at = int(contract.get_protocol(0)["halted_at"])
    set_tx_timestamp(monkeypatch, halted_at + window, contract)

    mock_overturn_true(direct_vm)
    direct_vm.sender = challenger
    direct_vm.value = DEFAULT_BOND
    with pytest.raises(Exception) as exc:
        contract.challenge_halt(
            0,
            "Too late",
            json.dumps([f"https://{TRUSTED_DOMAIN}/overturn"]),
        )
    assert "window" in str(exc.value).lower() or "closed" in str(exc.value).lower()
    assert contract.get_protocol(0)["status"] == "HALTED"
    assert int(contract.get_case(1)["event_count"]) == 1
    assert contract.get_case(1)["bond_settled"] is False


def test_challenge_when_active_reverts(halt_module, direct_vm, direct_accounts):
    """T11: challenge while ACTIVE reverts."""
    contract = halt_module
    governor = direct_accounts[0]
    challenger = direct_accounts[2]
    direct_vm.sender = governor
    register_default_protocol(contract)

    mock_overturn_true(direct_vm)
    direct_vm.sender = challenger
    direct_vm.value = DEFAULT_BOND
    with pytest.raises(Exception) as exc:
        contract.challenge_halt(
            0,
            "Nothing to challenge",
            json.dumps([f"https://{TRUSTED_DOMAIN}/overturn"]),
        )
    assert "halted" in str(exc.value).lower()


def test_unhalt_during_window_then_challenge_reverts(
    halt_module, direct_vm, direct_accounts
):
    """T12: unhalt during window is allowed; later challenge reverts."""
    contract = halt_module
    governor = direct_accounts[0]
    reporter = direct_accounts[1]
    challenger = direct_accounts[2]
    direct_vm.sender = governor
    register_default_protocol(contract)

    _halt_default(contract, direct_vm, reporter)

    mock_remediated_true(direct_vm)
    direct_vm.sender = governor
    direct_vm.value = DEFAULT_BOND
    ok = contract.request_unhalt(
        0,
        "Patch deployed; drains stopped",
        json.dumps([f"https://{TRUSTED_DOMAIN}/remediation"]),
    )
    assert ok is True
    assert contract.get_protocol(0)["status"] == "ACTIVE"
    assert contract.get_case(1)["status"] == "CLEARED"

    mock_overturn_true(direct_vm)
    direct_vm.sender = challenger
    direct_vm.value = DEFAULT_BOND
    with pytest.raises(Exception) as exc:
        contract.challenge_halt(
            0,
            "Too late, already unhalted",
            json.dumps([f"https://{TRUSTED_DOMAIN}/overturn"]),
        )
    assert "halted" in str(exc.value).lower()


def test_finalize_appeal_after_window(
    halt_module, direct_vm, direct_accounts, monkeypatch
):
    """T13: finalize after window refunds reporter escrow; stays HALTED."""
    contract = halt_module
    governor = direct_accounts[0]
    reporter = direct_accounts[1]
    anyone = direct_accounts[3]
    window = 100
    direct_vm.sender = governor
    register_default_protocol(contract, appeal_window_seconds=window)

    _halt_default(contract, direct_vm, reporter)
    halted_at = int(contract.get_protocol(0)["halted_at"])
    set_tx_timestamp(monkeypatch, halted_at + window, contract)

    direct_vm.sender = anyone
    direct_vm.value = 0
    ok = contract.finalize_appeal(0)
    assert ok is True

    protocol = contract.get_protocol(0)
    assert protocol["status"] == "HALTED"
    assert protocol["active_case_id"] == 1
    assert int(protocol["halted_at"]) == halted_at
    assert contract.is_action_allowed(0, "withdraw") is False

    case = contract.get_case(1)
    assert case["status"] == "ACCEPTED_HALT"
    assert case["bond_settled"] is True

    events = contract.list_case_events(1, 0, 10)
    assert len(events) == 2
    final_event = events[1]
    assert final_event["event_type"] == "APPEAL_FINALIZED"
    assert final_event["bond_disposition"] == "REFUND_REPORTER"
    assert int(final_event["bond_amount"]) == DEFAULT_BOND
    assert final_event["to_status"] == "ACCEPTED_HALT"
    assert final_event["actor"].lower() == address_hex(anyone).lower()

    with pytest.raises(Exception) as exc:
        contract.finalize_appeal(0)
    assert "settled" in str(exc.value).lower()


def test_finalize_appeal_too_early_reverts(halt_module, direct_vm, direct_accounts):
    """T14: finalize before window expiry reverts."""
    contract = halt_module
    governor = direct_accounts[0]
    reporter = direct_accounts[1]
    direct_vm.sender = governor
    register_default_protocol(contract)

    _halt_default(contract, direct_vm, reporter)

    direct_vm.sender = governor
    direct_vm.value = 0
    with pytest.raises(Exception) as exc:
        contract.finalize_appeal(0)
    msg = str(exc.value).lower()
    assert "window" in msg or "open" in msg or "early" in msg
    assert contract.get_protocol(0)["status"] == "HALTED"
    assert contract.get_case(1)["bond_settled"] is False
    assert int(contract.get_case(1)["event_count"]) == 1


def test_appeal_window_zero_refunds_and_challenge_reverts(
    halt_module, direct_vm, direct_accounts
):
    """T16: window=0 halt refunds reporter; challenge reverts."""
    contract = halt_module
    governor = direct_accounts[0]
    reporter = direct_accounts[1]
    challenger = direct_accounts[2]
    direct_vm.sender = governor
    register_default_protocol(contract, appeal_window_seconds=0)

    _halt_default(contract, direct_vm, reporter)

    protocol = contract.get_protocol(0)
    assert protocol["status"] == "HALTED"
    case = contract.get_case(1)
    assert case["bond_settled"] is True
    assert contract.list_case_events(1, 0, 10)[0]["bond_disposition"] == "REFUND_ACTOR"

    mock_overturn_true(direct_vm)
    direct_vm.sender = challenger
    direct_vm.value = DEFAULT_BOND
    with pytest.raises(Exception) as exc:
        contract.challenge_halt(
            0,
            "Challenges disabled",
            json.dumps([f"https://{TRUSTED_DOMAIN}/overturn"]),
        )
    msg = str(exc.value).lower()
    assert "window" in msg or "disabled" in msg
    assert contract.get_protocol(0)["status"] == "HALTED"
    assert int(contract.get_case(1)["event_count"]) == 1

    direct_vm.sender = governor
    direct_vm.value = 0
    with pytest.raises(Exception) as exc_fin:
        contract.finalize_appeal(0)
    fin_msg = str(exc_fin.value).lower()
    assert "window" in fin_msg or "disabled" in fin_msg
    assert contract.get_case(1)["bond_settled"] is True


def test_multiple_failed_challenges_each_pay_reporter(
    halt_module, direct_vm, direct_accounts
):
    contract = halt_module
    governor = direct_accounts[0]
    reporter = direct_accounts[1]
    challenger = direct_accounts[2]
    direct_vm.sender = governor
    register_default_protocol(contract)

    _halt_default(contract, direct_vm, reporter)

    mock_overturn_false(direct_vm)
    for _ in range(2):
        direct_vm.sender = challenger
        direct_vm.value = DEFAULT_BOND
        ok = contract.challenge_halt(
            0,
            "Still wrong",
            json.dumps([f"https://{TRUSTED_DOMAIN}/still-exploited"]),
        )
        assert ok is False

    protocol = contract.get_protocol(0)
    assert protocol["status"] == "HALTED"
    case = contract.get_case(1)
    assert case["status"] == "ACCEPTED_HALT"
    assert case["bond_settled"] is False
    assert int(case["event_count"]) == 3

    events = contract.list_case_events(1, 0, 10)
    assert [e["event_type"] for e in events] == [
        "REPORT_EVALUATED",
        "CHALLENGE_EVALUATED",
        "CHALLENGE_EVALUATED",
    ]
    assert events[1]["bond_disposition"] == "SLASH_REPORTER"
    assert events[2]["bond_disposition"] == "SLASH_REPORTER"
    assert events[1]["consensus_bool"] is False
    assert events[2]["consensus_bool"] is False


def test_challenge_wrong_bond_reverts(halt_module, direct_vm, direct_accounts):
    contract = halt_module
    governor = direct_accounts[0]
    reporter = direct_accounts[1]
    challenger = direct_accounts[2]
    direct_vm.sender = governor
    register_default_protocol(contract)

    _halt_default(contract, direct_vm, reporter)

    mock_overturn_true(direct_vm)
    direct_vm.sender = challenger
    direct_vm.value = DEFAULT_BOND - 1
    with pytest.raises(Exception) as exc:
        contract.challenge_halt(
            0,
            "Halt was a false alarm",
            json.dumps([f"https://{TRUSTED_DOMAIN}/overturn"]),
        )
    assert "exactly" in str(exc.value).lower() or "bond" in str(exc.value).lower()
    assert contract.get_protocol(0)["status"] == "HALTED"
    assert int(contract.get_case(1)["event_count"]) == 1
    assert contract.get_case(1)["bond_settled"] is False


def test_challenge_llm_garbage_reverts_without_slash(
    halt_module, direct_vm, direct_accounts
):
    contract = halt_module
    governor = direct_accounts[0]
    reporter = direct_accounts[1]
    challenger = direct_accounts[2]
    direct_vm.sender = governor
    register_default_protocol(contract)

    _halt_default(contract, direct_vm, reporter)

    direct_vm.clear_mocks()
    direct_vm.mock_web(r".*", {"status": 200, "body": "Challenge notes"})
    direct_vm.mock_llm(r".*", "not-json garbage")
    direct_vm.sender = challenger
    direct_vm.value = DEFAULT_BOND
    with pytest.raises(Exception):
        contract.challenge_halt(
            0,
            "Please overturn",
            json.dumps([f"https://{TRUSTED_DOMAIN}/overturn"]),
        )
    protocol = contract.get_protocol(0)
    assert protocol["status"] == "HALTED"
    case = contract.get_case(1)
    assert case["status"] == "ACCEPTED_HALT"
    assert case["bond_settled"] is False
    assert int(case["event_count"]) == 1
