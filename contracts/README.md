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
| `demo_vault.py` | Opt-in vault gated by `is_action_allowed` |

## Lint / test (after contracts exist)

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
genvm-lint check halt_module.py
pytest ../tests/direct/ -v
```
