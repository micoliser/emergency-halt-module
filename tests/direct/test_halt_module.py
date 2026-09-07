"""Direct-mode tests for HaltModule (Phase 1 + Phase 2)."""

from __future__ import annotations

import json

import pytest

from helpers import (
    DEFAULT_BOND,
    TRUSTED_DOMAIN,
    mock_exploit_false,
    mock_exploit_true,
    mock_remediated_false,
    mock_remediated_true,
    register_default_protocol,
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
    assert protocol["allowed_while_halted"] == ["deposit"]
    # Fail-closed: protected and unknown actions denied; allowlist permitted.
    assert contract.is_action_allowed(0, "withdraw") is False
    assert contract.is_action_allowed(0, "transfer") is False
    assert contract.is_action_allowed(0, "withdraws") is False
    assert contract.is_action_allowed(0, "deposit") is True

    case = contract.get_case(1)
    assert case["status"] == "ACCEPTED_HALT"
    assert case["verdict_exploit"] is True
    assert case["bond_settled"] is True
    assert case["reporter"]


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
    assert contract.is_action_allowed(0, "withdraw") is True

    case = contract.get_case(1)
    assert case["status"] == "REJECTED"
    assert case["verdict_exploit"] is False
    assert case["bond_settled"] is True


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
    direct_vm.value = 0
    with pytest.raises(Exception) as exc:
        contract.request_unhalt(
            0,
            "We patched it",
            json.dumps([f"https://{TRUSTED_DOMAIN}/fix"]),
        )
    assert "governor" in str(exc.value).lower()


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

    mock_remediated_true(direct_vm)
    direct_vm.sender = governor
    direct_vm.value = 0
    ok = contract.request_unhalt(
        0,
        "Patch deployed; drains stopped",
        json.dumps([f"https://{TRUSTED_DOMAIN}/remediation"]),
    )
    assert ok is True

    protocol = contract.get_protocol(0)
    assert protocol["status"] == "ACTIVE"
    assert protocol["active_case_id"] == 0
    assert contract.is_action_allowed(0, "withdraw") is True

    case = contract.get_case(1)
    assert case["status"] == "CLEARED"


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

    mock_remediated_false(direct_vm)
    direct_vm.sender = governor
    direct_vm.value = 0
    with pytest.raises(Exception) as exc:
        contract.request_unhalt(
            0,
            "Please unhalt",
            json.dumps([f"https://{TRUSTED_DOMAIN}/still-broken"]),
        )
    assert "remediat" in str(exc.value).lower()
    assert contract.get_protocol(0)["status"] == "HALTED"


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
