# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

from genlayer import *
from genlayer.py.storage import TreeMap


WITHDRAW_ACTION = "withdraw"


@gl.evm.contract_interface
class _Recipient:
    class View:
        pass

    class Write:
        pass


@gl.contract_interface
class HaltModuleIface:
    class View:
        def is_action_allowed(self, protocol_id: int, action: str) -> bool: ...

    class Write:
        pass


class DemoVault(gl.Contract):
    """
    Toy vault governed by a Halt Module protocol.
    Deposits are always accepted; withdraws require is_action_allowed(..., "withdraw").
    """

    halt_module: Address
    protocol_id: u256
    balances: TreeMap[str, u256]

    def __init__(self, halt_module: Address, protocol_id: int):
        halt_module = self._parse_address(halt_module)
        pid = int(protocol_id)
        if pid < 0:
            raise gl.vm.UserError("protocol_id must be >= 0")
        self.halt_module = halt_module
        self.protocol_id = u256(pid)

    def _parse_address(self, address) -> Address:
        if isinstance(address, Address):
            return address
        if isinstance(address, (bytes, bytearray)):
            return Address(bytes(address))
        if isinstance(address, int):
            return Address("0x" + format(address, "040x"))
        if isinstance(address, str):
            s = address.strip()
            if not s.startswith(("0x", "0X")):
                s = "0x" + s
            return Address(s)
        if hasattr(address, "as_bytes"):
            return Address(address.as_bytes)
        raise gl.vm.UserError("invalid address")

    def _balance_key(self, address: Address) -> str:
        return address.as_hex

    def _require_withdraw_allowed(self) -> None:
        halt = HaltModuleIface(self.halt_module)
        allowed = halt.view().is_action_allowed(int(self.protocol_id), WITHDRAW_ACTION)
        if not allowed:
            raise gl.vm.UserError(
                "Withdraw blocked: linked Halt Module protocol is halted "
                f"(action '{WITHDRAW_ACTION}' not allowed)"
            )

    @gl.public.write.payable
    def deposit(self) -> None:
        amount = int(gl.message.value)
        if amount <= 0:
            raise gl.vm.UserError("must send a non-zero amount")
        sender = gl.message.sender_address
        key = self._balance_key(sender)
        current = int(self.balances.get(key, u256(0)))
        self.balances[key] = u256(current + amount)

    @gl.public.write
    def withdraw(self, amount: int) -> None:
        self._require_withdraw_allowed()
        amt = int(amount)
        if amt <= 0:
            raise gl.vm.UserError("amount must be > 0")
        sender = gl.message.sender_address
        key = self._balance_key(sender)
        current = int(self.balances.get(key, u256(0)))
        if amt > current:
            raise gl.vm.UserError("insufficient balance")
        self.balances[key] = u256(current - amt)
        _Recipient(sender).emit_transfer(value=u256(amt))

    @gl.public.view
    def get_balance(self, address) -> u256:
        addr = self._parse_address(address)
        return self.balances.get(self._balance_key(addr), u256(0))

    @gl.public.view
    def get_config(self) -> dict:
        return {
            "halt_module": self.halt_module.as_hex,
            "protocol_id": int(self.protocol_id),
        }
