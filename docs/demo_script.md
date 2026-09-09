# Demo script — Emergency Halt Module (cold path)

Studionet only: chain id **61999**, RPC `https://studio.genlayer.com/api`,
Studio `https://studio.genlayer.com`, faucet 💧 in the Studio UI.

Contract addresses live in [`deploy/notes.md`](../deploy/notes.md). Put them in
`frontend/.env.local` and `backend/.env`.

**Evidence URLs must be public.** Validators cannot fetch `localhost`. Use
[rentry.co](https://rentry.co) (or, after Vercel, `https://<app>.vercel.app/evidence/*.html`
with that host in `trusted_domains`).

---

## 0. One-time setup

1. Start Postgres + Redis, then the indexer (`backend/README.md`):
   `migrate`, `runserver 127.0.0.1:8000`, Celery worker + beat.
2. `cd frontend && cp .env.example .env.local` and set:
   - `NEXT_PUBLIC_API_URL=http://localhost:8000`
   - `NEXT_PUBLIC_HALT_MODULE_ADDRESS` / `NEXT_PUBLIC_DEMO_VAULT_ADDRESS`
   - `NEXT_PUBLIC_CHAIN_ID=61999`
   - Server: `SYNC_SHARED_SECRET` if the backend has one (never `NEXT_PUBLIC_*`)
3. `npm install && npm run dev` → http://localhost:3000
4. MetaMask: Connect on the demo, then **Switch to studionet**. Fund GEN from Studio 💧
   (needed for reporter bond + vault deposit).
5. Confirm `GET http://localhost:8000/api/health` is `ok`.

### Studio / UI values (copy-paste)

| Field | Value |
|---|---|
| Protocol name | `Demo Vault Protocol` |
| Exploit definition | `Halt if evidence shows an active drain of user funds.` |
| Trusted domains | `rentry.co` |
| Protected actions | `withdraw, transfer` |
| Allowed while halted | _(empty)_ |
| Reporter bond | `1` GEN (`1000000000000000000` wei) |
| Min evidence | `1` |
| Appeal window | `86400` |
| Vault deposit / withdraw | `0.1` GEN |

**Evidence (host on rentry.co, then paste the public URL):**

- Incident (halt): body of `docs/demo_evidence/incident.html` — must say an **active exploit is draining funds**.
- Clean / false report (optional): `docs/demo_evidence/clean.html`.
- Remediation (unhalt): `docs/demo_evidence/remediation.html`.

Vault ctor (Studio, after protocol `0` exists): Halt Module address + protocol id `0`.

---

## Cold path (browser)

Use the **vault’s linked protocol** (Demo Vault → protocol id from `get_config`).
A newly registered protocol is **not** wired to an already-deployed vault unless
you redeploy the vault with that id.

1. **Connect** MetaMask on http://localhost:3000. Banner should not complain
   about missing addresses.
2. **Register** (optional if protocol 0 already exists): Overview → Register.
   Submit with the table values. Wait pending → accepted → indexer sync.
   Detail page should show **ACTIVE**.
3. **Vault while ACTIVE:** Demo Vault → deposit `0.1` GEN → withdraw `0.1` GEN.
   Both should confirm. Banner: withdraw allowed.
4. **Report:** Protocol detail → Report exploit.
   - Allegation: `Funds are being drained right now.`
   - Evidence URL: your **public** incident rentry (host `rentry.co`).
   - Confirm in MetaMask: value **exactly** `1` GEN.
   Copy: “Validators are reviewing evidence…” (30–60s+).
   After sync, status **HALTED**, case `ACCEPTED_HALT` (ids 1-indexed).
5. **Withdraw fails:** Demo Vault should show the on-chain gate
   `is_action_allowed(id, "withdraw") = false`. Click Withdraw anyway — tx
   reverts with `Withdraw blocked: linked Halt Module protocol is halted`.
   Spinner must stop (error state, not infinite pending).
6. **Unhalt:** As governor, Request unhalt with remediation rentry URL.
   After consensus + sync, status **ACTIVE**, `active_case_id == 0`.
7. **Withdraw works:** Demo Vault withdraw `0.1` GEN succeeds again.

If a report is **REJECTED** (clean page / weak evidence), status stays ACTIVE and
the 1 GEN bond is slashed to the governor — try again with the incident page.

---

## Studio-only (if the UI write path is blocked)

Same values, against the Halt Module ABI in Studio:

1. `register_protocol(...)` → protocol id `0` (first register).
2. Deploy / confirm Demo Vault `(halt_module, 0)`.
3. Vault `deposit` then `withdraw`.
4. `report_exploit(0, allegation, '["https://rentry.co/<incident>"]')` with value = bond.
5. `is_action_allowed(0, "withdraw")` → false; vault `withdraw` reverts.
6. `request_unhalt(0, statement, '["https://rentry.co/<remediation>"]')`.
7. Withdraw works; `POST /api/sync/protocols/0` then `GET /api/protocols/0` shows ACTIVE.

---

## Fail-closed UI

On revert, user-reject, or ~4 minute poll timeout the toast/status goes to
**Failed** / **Outcome unclear**. There is no infinite spinner. Refresh and/or
`Refresh from chain` on the protocol page.
