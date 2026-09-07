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

## Trust model

| On-chain (deterministic) | AI-judged (nondet) |
|---|---|
| Registration, bonds, status, `is_action_allowed`, vault balances | Whether fetched evidence proves an active exploit / remediation |

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

See [IMPLEMENTATION_PLAN.md](../IMPLEMENTATION_PLAN.md) for ABI freeze, phases, and milestones.
