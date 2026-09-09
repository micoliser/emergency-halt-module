"""Direct-mode tests for DemoVault (Phase 3)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from helpers import (
    DEFAULT_BOND,
    TRUSTED_DOMAIN,
    MultiContractHost,
    mock_exploit_true,
    mock_overturn_true,
    register_default_protocol,
)

ROOT = Path(__file__).resolve().parents[2]
HALT_PATH = ROOT / "contracts" / "halt_module.py"
VAULT_PATH = ROOT / "contracts" / "demo_vault.py"


@pytest.fixture
def vault_stack(direct_vm, direct_accounts):
    """Deploy HaltModule + DemoVault with cross-contract CallContract support."""
    host = MultiContractHost(direct_vm)
    governor = direct_accounts[0]
    direct_vm.sender = governor
    direct_vm.value = 0

    halt = host.deploy(HALT_PATH)
    pid = register_default_protocol(
        halt,
        actions=["withdraw", "transfer"],
        allowed_while_halted=[],
    )
    assert pid == 0

    vault = host.deploy(VAULT_PATH, halt.address, pid)
    return host, halt, vault, pid


def test_get_config(vault_stack, direct_vm, direct_accounts):
    _host, halt, vault, pid = vault_stack
    direct_vm.sender = direct_accounts[0]
    cfg = vault.get_config()
    assert cfg["protocol_id"] == pid
    assert cfg["halt_module"].lower() == halt.address.as_hex.lower()


def test_deposit_and_withdraw_while_active(vault_stack, direct_vm, direct_accounts):
    _host, _halt, vault, _pid = vault_stack
    user = direct_accounts[1]
    direct_vm.sender = user

    direct_vm.value = 500
    vault.deposit()
    direct_vm.value = 0
    assert int(vault.get_balance(user)) == 500

    vault.withdraw(200)
    assert int(vault.get_balance(user)) == 300

    vault.withdraw(300)
    assert int(vault.get_balance(user)) == 0


def test_withdraw_blocked_when_halted(vault_stack, direct_vm, direct_accounts):
    _host, halt, vault, _pid = vault_stack
    governor = direct_accounts[0]
    user = direct_accounts[1]

    direct_vm.sender = user
    direct_vm.value = 1000
    vault.deposit()
    direct_vm.value = 0

    mock_exploit_true(direct_vm)
    reporter = direct_accounts[2]
    direct_vm.sender = reporter
    direct_vm.value = DEFAULT_BOND
    halt.report_exploit(
        0,
        "Active drain observed",
        json.dumps([f"https://{TRUSTED_DOMAIN}/incident"]),
    )
    direct_vm.value = 0

    assert halt.get_protocol(0)["status"] == "HALTED"
    assert halt.is_action_allowed(0, "withdraw") is False

    direct_vm.sender = user
    with pytest.raises(Exception) as exc:
        vault.withdraw(100)
    msg = str(exc.value).lower()
    assert "withdraw" in msg or "halt" in msg or "blocked" in msg
    assert int(vault.get_balance(user)) == 1000


def test_zero_deposit_reverts(vault_stack, direct_vm, direct_accounts):
    _host, _halt, vault, _pid = vault_stack
    direct_vm.sender = direct_accounts[1]
    direct_vm.value = 0
    with pytest.raises(Exception) as exc:
        vault.deposit()
    assert "non-zero" in str(exc.value).lower() or "amount" in str(exc.value).lower()


def test_over_withdraw_reverts(vault_stack, direct_vm, direct_accounts):
    _host, _halt, vault, _pid = vault_stack
    user = direct_accounts[1]
    direct_vm.sender = user
    direct_vm.value = 50
    vault.deposit()
    direct_vm.value = 0

    with pytest.raises(Exception) as exc:
        vault.withdraw(51)
    assert "insufficient" in str(exc.value).lower()
    assert int(vault.get_balance(user)) == 50


def test_get_balance_address_coercion(vault_stack, direct_vm, direct_accounts):
    _host, _halt, vault, _pid = vault_stack
    user = direct_accounts[1]
    direct_vm.sender = user
    direct_vm.value = 77
    vault.deposit()
    direct_vm.value = 0

    # create_address may surface as Address or raw bytes depending on SDK path
    if hasattr(user, "as_hex"):
        user_hex = user.as_hex
        user_bytes = user.as_bytes
    else:
        user_bytes = bytes(user)
        user_hex = "0x" + user_bytes.hex()

    assert int(vault.get_balance(user)) == 77
    assert int(vault.get_balance(user_hex)) == 77
    hex_no_prefix = user_hex[2:] if user_hex.startswith("0x") else user_hex
    assert int(vault.get_balance(hex_no_prefix)) == 77
    assert int(vault.get_balance(int(hex_no_prefix, 16))) == 77
    assert int(vault.get_balance(user_bytes)) == 77


def test_withdraw_restored_after_overturn(vault_stack, direct_vm, direct_accounts):
    """T18 / Phase C: halt blocks withdraw; successful overturn restores it."""
    _host, halt, vault, _pid = vault_stack
    user = direct_accounts[1]
    reporter = direct_accounts[2]
    challenger = direct_accounts[3]

    direct_vm.sender = user
    direct_vm.value = 1000
    vault.deposit()
    direct_vm.value = 0

    mock_exploit_true(direct_vm)
    direct_vm.sender = reporter
    direct_vm.value = DEFAULT_BOND
    halt.report_exploit(
        0,
        "Active drain observed",
        json.dumps([f"https://{TRUSTED_DOMAIN}/incident"]),
    )
    direct_vm.value = 0

    assert halt.get_protocol(0)["status"] == "HALTED"
    direct_vm.sender = user
    with pytest.raises(Exception):
        vault.withdraw(100)
    assert int(vault.get_balance(user)) == 1000

    mock_overturn_true(direct_vm)
    direct_vm.sender = challenger
    direct_vm.value = DEFAULT_BOND
    ok = halt.challenge_halt(
        0,
        "Halt was a false alarm; no active exploit",
        json.dumps([f"https://{TRUSTED_DOMAIN}/overturn"]),
    )
    assert ok is True
    direct_vm.value = 0

    assert halt.get_protocol(0)["status"] == "ACTIVE"
    assert halt.get_case(1)["status"] == "OVERTURNED"
    assert halt.is_action_allowed(0, "withdraw") is True

    direct_vm.sender = user
    vault.withdraw(100)
    assert int(vault.get_balance(user)) == 900
