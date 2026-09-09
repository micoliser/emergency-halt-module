# Emergency Halt Module

Anyone can prove an active exploit. GenLayer validators decide. Opt-in apps freeze until the owner proves the issue is fixed.

Studionet demo for the GenLayer Agent Tank **Autonomous Protocols** track: a reusable halt registry that judges public evidence, plus a Demo Vault that refuses withdrawals while halted.

## How it works

1. An owner registers a protocol with a safety config (what counts as an exploit, which websites evidence may come from, which actions freeze, reporter bond).
2. Anyone posts a **bonded** report with public evidence URLs.
3. Validators fetch those pages and agree on whether an **active exploit** is proven.
4. If yes: protocol is **HALTED**, bond refunded. If no: stay **ACTIVE**, bond slashed to the owner.
5. Linked contracts (this repo’s Demo Vault) call `is_action_allowed(protocol_id, "withdraw")` and refuse the action while halted.
6. Only the owner can request an unhalt, with remediation evidence. Validators must agree before **ACTIVE** resumes.

Halt gate: **ACTIVE** allows every action. **HALTED** is fail-closed (only listed exceptions; unknown names are denied).

## Studionet contracts (this demo)

| Contract | Address |
|---|---|
| Halt Module | `0x125431c66F877424Dd4db6315fC30079C933B124` |
| Demo Vault | `0x7d27628a35171c9DE6F6684252a3e2500A7E856D` |

- RPC: `https://studio.genlayer.com/api`
- Chain id: `61999`
- Studio: https://studio.genlayer.com
- Explorer: https://explorer-studio.genlayer.com

The Demo Vault is constructed with `(halt_module, protocol_id)`. Registering a new protocol in the UI does **not** retarget that vault. When the app is running, open `/guide`, or read [contracts/README.md](contracts/README.md).

## Trust model (honesty)

| On-chain (deterministic) | AI-judged (nondeterministic) |
|---|---|
| Registration, exact bond, status, `is_action_allowed`, vault balances | Whether fetched **page content** proves an active exploit or a successful remediation |

This is **not** a cryptographic exploit detector. Validators read allowlisted web pages with an LLM. A weak definition, a captured trusted host, or a convincing fake page can still produce a halt. Bonds, host allowlists, and the unhalt vote are the brakes, not omniscience.

**Fail-closed garbage:** if the leader output is missing, not JSON, or lacks a boolean `exploit` / `remediated`, the transaction reverts. The protocol does **not** halt on unparseable model output.

**Governor risk:** whoever registers a protocol chooses trusted domains. Registering `attacker.example` and posting a fake page is a self-grief of *that* protocol, not of others.

**Studionet only.** This project does not target localnet or mainnet.

More: [docs/architecture.md](docs/architecture.md), [docs/SECURITY.md](docs/SECURITY.md).

## Known limitations

- AI judges page text on owner-allowlisted domains, not on-chain traces or bytecode diffs.
- One convincing page on an allowlisted host can halt if `min_evidence` is 1 and the definition is loose (mitigate with a stricter definition, higher `min_evidence`, and the reporter bond). Challenge / overturn is not in v1.
- Evidence URLs must be publicly fetchable. `localhost` will not work.
- The Halt Module never seizes a contract that does not call `is_action_allowed`.
- Indexer and UI are caches and wallets. The contracts are the source of truth.

## Repo layout

| Path | Role |
|---|---|
| `contracts/` | `halt_module.py`, `demo_vault.py` |
| `backend/` | Thin Django indexer (Postgres, Redis, Celery) |
| `frontend/` | Next.js demo (MetaMask, Studionet) |
| `docs/` | Architecture, demo script, security notes, sample evidence |
| `tests/direct/` | Contract tests without live LLM |

## Local setup

You need Postgres, Redis, Python 3.12, Node 20 (webpack dev server; see [frontend/README.md](frontend/README.md) if native SWC crashes on WSL).

```bash
# Backend
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env   # set DATABASE_URL, REDIS_URL, HALT_MODULE_ADDRESS, DEMO_VAULT_ADDRESS
python manage.py migrate
python manage.py runserver 127.0.0.1:8000
# other terminals:
celery -A config worker -l info
celery -A config beat -l info

# Frontend
cd frontend
cp .env.example .env.local   # NEXT_PUBLIC_* addresses + API URL
nvm use 20
npm install
npm run dev                  # http://localhost:3000
```

Never put `SYNC_SHARED_SECRET` in a `NEXT_PUBLIC_*` variable. The Next `/api/sync` proxy attaches it server-side.

Demo click-through: [docs/demo_script.md](docs/demo_script.md). Fund GEN from the Studio faucet.

## Tests

```bash
# Contracts (from repo root, with the project venv that has genlayer)
pytest tests/direct/ -v

# Indexer
cd backend && pytest -q
```

## License

[MIT](LICENSE)
