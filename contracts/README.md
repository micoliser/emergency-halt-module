# Contracts

## Pinned GenVM runner (copy into every contract file)

```python
# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
```

- **Never** use `py-genlayer:test`, `latest`, or an unversioned alias.
- Re-verify this hash against a working Studio starter contract before the first studionet deploy (Phase 2).

## SDK generation

Use the **namespaced** API matching this runner:

```python
gl.nondet.web.render(...)
gl.nondet.exec_prompt(...)
gl.eq_principle.strict_eq(...)
gl.eq_principle.prompt_comparative(...)
gl.vm.run_nondet_unsafe(...)
gl.vm.UserError(...)
```

Outbound GEN (bonds): Covenant-style `_Recipient(addr).emit_transfer(value=u256(...))`.

## Network

**Studionet only** for deploy and smoke tests. Localnet is not used in this project.

## ABI freeze

Method surface, storage shape, and state machine are locked in [IMPLEMENTATION_PLAN.md](../IMPLEMENTATION_PLAN.md) Sections 3.1–3.5.

| File (Phase 1+) | Role |
|---|---|
| `halt_module.py` | Registry, bonded reports, adjudication, halt/unhalt |
| `demo_vault.py` | Opt-in vault gated by `is_action_allowed(..., "withdraw")` |

**Demo Vault action string:** `withdraw` is hardcoded in the vault. Register the protocol with `"withdraw"` in `protected_actions` and **not** in `allowed_while_halted`, or the demo gate will not match.

## Lint / test (after contracts exist)

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
genvm-lint check halt_module.py
genvm-lint check demo_vault.py
cd .. && pytest tests/direct/ -v
```

## Phase 1–2 surface (`halt_module.py`)

| Method | Notes |
|---|---|
| `register_protocol(...)` | Caller = governor; domains normalized; `allowed_while_halted_json` (may be `[]`); no overlap with protected |
| `report_exploit(...)` | Payable exact bond; majority D3 aggregation; refund/slash via `_Recipient.emit_transfer` |
| `request_unhalt(...)` | Governor only; remediation majority |
| Views | counts, get/list protocols & cases, `is_action_allowed` (fail-closed when HALTED) |

**Halt gate:** While `ACTIVE`, all actions allowed. While `HALTED`, only actions in `allowed_while_halted` return `true` (typos/unknown → `false`).

Case IDs are **1-indexed** so `active_case_id == 0` means none.

## Phase 3 surface (`demo_vault.py`)

| Method | Notes |
|---|---|
| `__init__(halt_module, protocol_id)` | Coerce address; `protocol_id >= 0` |
| `deposit()` | Payable; credits sender balance; **not** halt-gated |
| `withdraw(amount)` | View-calls halt `is_action_allowed(pid, "withdraw")`; debit; `emit_transfer` |
| `get_balance(address)` / `get_config()` | Views; address coercion on balance lookup |