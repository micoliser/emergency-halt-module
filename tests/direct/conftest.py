"""Pytest fixtures for ProofHalt Halt Module direct-mode tests."""

from __future__ import annotations

from pathlib import Path

import pytest

CONTRACT_PATH = Path(__file__).resolve().parents[2] / "contracts" / "halt_module.py"


@pytest.fixture
def halt_module(direct_vm, direct_deploy, direct_accounts):
    """Deploy a fresh HaltModule with account[0] as deployer/sender."""
    governor = direct_accounts[0]
    direct_vm.sender = governor
    direct_vm.value = 0
    return direct_deploy(str(CONTRACT_PATH))
