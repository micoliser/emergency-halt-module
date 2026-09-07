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
| Demo Vault | _TBD_ | | Pass halt module address + protocol_id |

## Deploy order

1. Deploy `contracts/halt_module.py`
2. `register_protocol(...)` (governor wallet)
3. Deploy `contracts/demo_vault.py` with `(halt_module_address, protocol_id)`
4. Update backend + frontend env vars
5. Run indexer sync / health check

## Hosting (later phases)

| Service | Host | URL |
|---|---|---|
| Frontend | Vercel | _TBD_ |
| Backend | Render (or equiv.) | _TBD_ |
| Postgres | Supabase/Neon | _TBD_ |
| Redis | Upstash (or equiv.) | _TBD_ |
