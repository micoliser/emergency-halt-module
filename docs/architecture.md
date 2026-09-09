# Emergency Halt Module — Architecture

## Problem

Autonomous protocols need a kill switch that is not a trusted multisig theater. When public evidence of an **active exploit** appears, protected operations should freeze through independently verified judgment.

## Solution (one loop)

1. **Governor** registers a protocol with a **Safety Config** (exploit definition, trusted domains, protected actions, reporter bond, `min_evidence`).
2. **Anyone** submits a **bonded** `report_exploit` with evidence URLs.
3. GenLayer validators **fetch** those pages and run an LLM judgment.
4. **Comparative consensus** agrees on `exploit: bool` (summaries may differ).
5. If `exploit=true` → protocol status **HALTED**; reporter bond **refunded**. If false → stay **ACTIVE**; bond **slashed to governor**.
6. Opt-in **Demo Vault** calls `is_action_allowed(protocol_id, "withdraw")` and refuses withdraw while halted.
7. Governor **request_unhalt** with remediation evidence; validators must clear before **ACTIVE** resumes.

**Halt gate:** `ACTIVE` → all actions allowed. `HALTED` → fail-closed; only `allowed_while_halted` actions permitted (unknown/typos denied).

## Layers

```
Frontend (Next.js)
  wallet writes → GenLayer
  reads → Backend REST

Backend (thin Django indexer)
  poll-and-diff + fast-path sync
  never invents verdicts

GenLayer (studionet)
  halt_module.py  — registry, adjudication, bonds
  demo_vault.py   — halt-aware toy vault
```

| Layer | Owns | Must never |
|---|---|---|
| Contracts | Truth, adjudication, halt, bonds | Depend on backend for decisions |
| Backend | Cached reads, sync | Override or invent halt state |
| Frontend | UX, wallet writes | Be source of truth for halt |

## State machine

```
ACTIVE ──(exploit=true)──► HALTED ──(remediated=true)──► ACTIVE
```

## Indexer API

The backend mirrors the contract's view methods and nothing else. Reads are
paginated with `offset`/`limit` (capped at the contract's page limit); u256
amounts cross the wire as decimal strings.

| Route | Purpose |
|---|---|
| `GET /api/health` | DB + chain config + sync cursor freshness |
| `GET /api/protocols` · `/api/protocols/<id>` | Registry list / detail |
| `GET /api/protocols/<id>/cases` | Cases for one protocol |
| `GET /api/cases` · `/api/cases/<id>` | Reports list / detail with verdict |
| `POST /api/sync/protocols/<id>` | Fast-path resync right after a wallet tx |

A Celery beat task polls the count anchors every 30s and diffs; the fast-path
POST runs the same reads inline so a fresh halt is visible immediately. Full
route and response shapes: [backend/README.md](../backend/README.md).

## Trust model

| On-chain (deterministic) | AI-judged (nondet) |
|---|---|
| Registration, bonds, status, `is_action_allowed`, vault balances | Whether fetched evidence proves an active exploit / remediation |

**Fail-closed on LLM garbage:** missing JSON, a non-boolean `exploit` / `remediated`, or failed consensus raises `UserError`. The protocol stays **ACTIVE**. We do not halt on unparseable leader output.

**Limit:** AI judges **page content** on allowlisted domains, not cryptographic exploit proofs. Bonds, trusted domains, and (P1) challenges are the mitigations.

## Consensus

- Live evidence → `gl.nondet.web.render` + `gl.nondet.exec_prompt` inside a nondet block.
- Validators re-run and must agree on the **decision boolean**.
- Aggregation (locked): majority of successfully fetched trusted-domain pages must vote `exploit=true`, and fetch count ≥ `min_evidence`.
- Side effects (status, `emit_transfer` bond settle) happen **after** consensus.

## Bond economics

Outbound GEN uses Covenant Escrow’s pattern: `_Recipient(addr).emit_transfer(value=...)`.

| Outcome | Bond |
|---|---|
| Rejected report | Slashed to governor |
| Accepted halt | Refunded to reporter |

## Differentiation (vs Latchkey-style courts)

- Three clear states, not a long posture ladder.
- Separate **Demo Vault** governed by the Halt Module (“contracts that govern contracts”).
- Bonded anyone-can-report kill-switch primitive for the Autonomous Protocols track.

## Network

**Studionet only** (RPC `https://studio.genlayer.com/api`, chain id `61999`). Localnet is out of scope for this environment.

See [README.md](../README.md) and [SECURITY.md](SECURITY.md) for setup, honesty, and limitations.
