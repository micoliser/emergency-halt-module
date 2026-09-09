"""Shared helpers for direct HaltModule tests (imported by test modules)."""

from __future__ import annotations

import functools
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from gltest.direct.loader import (
    _allocate_contract,
    _make_contract_proxy,
    _patch_run_nondet_for_direct_mode,
    load_contract_class,
)
from gltest.direct.vm import InmemManager

DEFAULT_BOND = 100
DEFAULT_MIN_EVIDENCE = 1
TRUSTED_DOMAIN = "evidence.example.com"


class MultiContractHost:
    """
    Direct-mode host for two+ contracts with isolated storage and
    CallContract / PostMessage routing (needed for vault → halt view calls).
    """

    def __init__(self, vm: Any):
        self.vm = vm
        self._instances: dict[str, Any] = {}
        self._storages: dict[str, InmemManager] = {}
        self._seq = 0
        self.vm._gl_call_hook = self._gl_call_hook

    @staticmethod
    def _addr_key(address: Any) -> str:
        from genlayer.py.types import Address

        if isinstance(address, Address):
            return "0x" + address.as_bytes.hex()
        if isinstance(address, (bytes, bytearray)):
            return "0x" + bytes(address).hex()
        s = str(address).lower()
        if not s.startswith("0x"):
            s = "0x" + s
        return s

    @staticmethod
    def _reset_contract_registry() -> None:
        mod = sys.modules.get("genlayer.gl.genvm_contracts")
        if mod is None:
            return
        for attr in ("__known_contact__", "__known_contract__"):
            if hasattr(mod, attr):
                setattr(mod, attr, None)

    def _activate(self, addr_key: str) -> None:
        storage = self._storages[addr_key]
        addr_bytes = bytes.fromhex(addr_key[2:])
        self.vm._storage = storage
        self.vm._contract_address = addr_bytes
        self._sync_message_contract_address(addr_bytes)

    def _sync_message_contract_address(self, addr_bytes: bytes) -> None:
        try:
            from genlayer.py.types import Address
            import genlayer.gl as gl

            addr = Address(addr_bytes)
            if hasattr(gl, "message_raw") and gl.message_raw is not None:
                gl.message_raw["contract_address"] = addr
            if hasattr(gl, "message") and gl.message is not None:
                gl.message = gl.MessageType(
                    contract_address=addr,
                    sender_address=gl.message.sender_address,
                    origin_address=gl.message.origin_address,
                    value=gl.message.value,
                    chain_id=gl.message.chain_id,
                )
        except Exception:
            pass

    def _wrap(self, addr_key: str, instance: Any) -> Any:
        host = self
        proxy = _make_contract_proxy(instance)

        class BoundContract:
            __slots__ = ("_proxy", "_addr_key", "address")

            def __init__(self) -> None:
                from genlayer.py.types import Address

                self._proxy = proxy
                self._addr_key = addr_key
                self.address = Address(bytes.fromhex(addr_key[2:]))

            def __getattr__(self, name: str) -> Any:
                host._activate(self._addr_key)
                attr = getattr(self._proxy, name)
                if callable(attr):

                    @functools.wraps(attr)
                    def _call(*args: Any, **kwargs: Any) -> Any:
                        host._activate(self._addr_key)
                        return attr(*args, **kwargs)

                    return _call
                return attr

            def __repr__(self) -> str:
                return f"<BoundContract {addr_key}>"

        return BoundContract()

    def deploy(self, contract_path: str | Path, *args: Any, **kwargs: Any) -> Any:
        path = Path(contract_path).resolve()
        self._seq += 1
        addr_bytes = hashlib.sha256(f"{path}:{self._seq}".encode()).digest()[:20]
        addr_key = "0x" + addr_bytes.hex()

        storage = InmemManager()
        self._storages[addr_key] = storage
        self.vm._storage = storage
        self.vm._contract_address = addr_bytes

        self._reset_contract_registry()
        contract_cls = load_contract_class(path, self.vm)
        _patch_run_nondet_for_direct_mode()

        # Roundtrip constructor args like deploy_contract does
        from gltest.direct.loader import _calldata_roundtrip_args

        args, kwargs = _calldata_roundtrip_args(args, kwargs)
        instance = _allocate_contract(contract_cls, self.vm, *args, **kwargs)

        # Keep our address (load/allocate may touch message context)
        self.vm._contract_address = addr_bytes
        self._instances[addr_key] = instance
        return self._wrap(addr_key, instance)

    def _gl_call_hook(self, vm: Any, request: dict) -> Any:
        if "CallContract" in request:
            return self._handle_call(vm, request["CallContract"])
        if "PostMessage" in request:
            # emit_transfer / write posts — no-op ok in direct tests
            return {"ok": None}
        if "DeployContract" in request:
            return None
        return None

    def _handle_call(self, vm: Any, data: dict) -> bytes:
        from genlayer.py import calldata

        addr_key = self._addr_key(data.get("address"))
        instance = self._instances.get(addr_key)
        if instance is None:
            return bytes([1]) + f"Contract not found at {addr_key}".encode()

        calldata_obj = data.get("calldata") or {}
        method_name = calldata_obj.get("method")
        args = list(calldata_obj.get("args") or [])
        kwargs = dict(calldata_obj.get("kwargs") or {})

        parent_storage = vm._storage
        parent_contract_address = vm._contract_address
        target_storage = self._storages.get(addr_key)
        if target_storage is not None:
            vm._storage = target_storage
        vm._contract_address = bytes.fromhex(addr_key[2:])

        try:
            method = getattr(instance, method_name)
            result = method(*args, **kwargs)
            return bytes([0]) + calldata.encode(result)
        except Exception as exc:
            return bytes([1]) + str(exc).encode()
        finally:
            vm._storage = parent_storage
            vm._contract_address = parent_contract_address


def address_hex(account: Any) -> str:
    if hasattr(account, "as_hex"):
        return str(account.as_hex)
    if isinstance(account, (bytes, bytearray)):
        return "0x" + bytes(account).hex()
    return str(account)


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
    backup_unhalters: list | None = None,
) -> int:
    if domains is None:
        domains = [TRUSTED_DOMAIN]
    if actions is None:
        actions = ["withdraw", "transfer"]
    if allowed_while_halted is None:
        allowed_while_halted = []
    if backup_unhalters is None:
        backup_unhalters = []
    backups_json = [address_hex(b) for b in backup_unhalters]
    return contract.register_protocol(
        name,
        definition,
        json.dumps(domains),
        json.dumps(actions),
        json.dumps(allowed_while_halted),
        bond,
        min_evidence,
        appeal_window_seconds,
        json.dumps(backups_json),
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


def mock_overturn_true(vm, summary: str = "Halt was unjustified; no active exploit") -> None:
    vm.clear_mocks()
    vm.mock_web(r".*", {"status": 200, "body": "False alarm: no active exploit matching definition"})
    vm.mock_llm(r".*", json.dumps({"overturn": True, "summary": summary}))


def mock_overturn_false(vm, summary: str = "Exploit still active; halt stands") -> None:
    vm.clear_mocks()
    vm.mock_web(r".*", {"status": 200, "body": "Active exploit still draining funds"})
    vm.mock_llm(r".*", json.dumps({"overturn": False, "summary": summary}))


def set_tx_timestamp(monkeypatch, timestamp: int, contract=None) -> None:
    """Force HaltModule._tx_timestamp after halt (appeal-window tests).

    Patches the loaded contract class method and `datetime` in that module
    (the method body is `datetime.now`). Optionally also patches the live
    instance class used by the GenVM storage wrapper.
    """
    import sys
    from datetime import datetime as real_datetime, timezone

    mod = sys.modules.get("_contract_halt_module")
    if mod is None:
        raise RuntimeError("HaltModule contract module is not loaded")

    ts = int(timestamp)

    def _fake_tx_timestamp(self):
        return mod.u256(ts)

    monkeypatch.setattr(mod.HaltModule, "_tx_timestamp", _fake_tx_timestamp)

    class FrozenDateTime(real_datetime):
        @classmethod
        def now(cls, tz=None):
            dt = real_datetime.fromtimestamp(ts, tz=timezone.utc)
            if tz is None:
                return dt.replace(tzinfo=None)
            return dt.astimezone(tz)

    monkeypatch.setattr(mod, "datetime", FrozenDateTime)

    inst = None
    if contract is not None:
        try:
            inst = object.__getattribute__(contract, "_instance")
        except Exception:
            proxy = getattr(contract, "_proxy", None)
            if proxy is not None:
                try:
                    inst = object.__getattribute__(proxy, "_instance")
                except Exception:
                    inst = None
    if inst is not None:
        cls = type(inst)
        if cls is not mod.HaltModule:
            monkeypatch.setattr(cls, "_tx_timestamp", _fake_tx_timestamp)
