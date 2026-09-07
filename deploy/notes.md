# Deploy notes — Emergency Halt Module

## Network: Studionet only

| Setting | Value |
|---|---|
| GenLayer RPC | `https://studio.genlayer.com/api` |
| Chain ID | `61999` |
| Currency | GEN |
| Explorer | https://explorer-studio.genlayer.com |
| Studio | https://studio.genlayer.com |

**Faucet:** Studionet does not auto-fund CLI/gltest keys. Use the Studio UI 💧 faucet for payable/bond flows. Zero-value writes and all reads need no funding.

**Localnet:** Not used. Docker/WSL localnet is out of scope for this project.

## Contract addresses (fill after deploy)

| Contract | Address | Deployed at | Notes |
|---|---|---|---|
| Halt Module | _TBD_ | | Deploy first |
| Demo Vault | _TBD_ | | Ctor: `(halt_module_address, protocol_id)` e.g. `(0x…, 0)` |

## Deploy order

1. Deploy `contracts/halt_module.py` (fail-closed halt gate).
2. As governor, `register_protocol(...)` with `protected_actions` including `"withdraw"` and `allowed_while_halted` as `[]` (or `["deposit"]` if you want deposits explicitly allowlisted — vault does not gate deposits either way).
3. Note the returned **protocol_id** (first register → `0`).
4. Deploy `contracts/demo_vault.py` with constructor args `(halt_module_address, protocol_id)`.
5. Smoke: deposit → withdraw (ACTIVE) → `report_exploit` → withdraw fails → unhalt → withdraw works.
6. Update backend + frontend env vars (Phases 4–5).
7. Run indexer sync / health check (Phase 4).

### Studio register args (vault demo)

| Arg | Example |
|---|---|
| `name` | `Demo Vault Protocol` |
| `exploit_definition` | `Halt if evidence shows an active drain of user funds.` |
| `trusted_domains_json` | `["rentry.co"]` (must match evidence URL host) |
| `protected_actions_json` | `["withdraw","transfer"]` |
| `allowed_while_halted_json` | `[]` |
| `reporter_bond` | `1000000000000000000` (1 GEN in wei) |
| `min_evidence` | `1` |
| `appeal_window_seconds` | `86400` |

Vault ctor: paste the Halt Module address + `0` (or the protocol id you registered).

## Hosting (later phases)

| Service | Host | URL |
|---|---|---|
| Frontend | Vercel | _TBD_ |
| Backend | Render (or equiv.) | _TBD_ |
| Postgres | Supabase/Neon | _TBD_ |
| Redis | Upstash (or equiv.) | _TBD_ |
