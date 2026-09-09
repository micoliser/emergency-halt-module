# Security notes

This is a Studionet hackathon demo, not a production incident-response product. The notes below match what the contracts actually do.

## Prompt injection

Definition, allegation, statement, and fetched evidence are wrapped in tagged blocks and labeled untrusted. Angle brackets are escaped before they enter `exec_prompt`. Model output must be JSON with a boolean decision; anything else reverts (fail-closed). This reduces instruction-following from the page; it does not make the LLM immune to a page that *looks like* a real exploit.

## Trusted domains

Hosts are lowercased. Scheme, path, query, fragment, userinfo (`user@host`), port, and a leading `www.` are stripped before allowlist match. Evidence URLs must be `http://` or `https://` and the normalized host must equal a registered domain. Direct tests cover the `https://trusted@evil.example` trick.

## Input caps

Names, definitions, allegations, statements, domains, URLs, action strings, and list counts are bounded on-chain (`DEFINITION_MAX`, `ALLEGATION_MAX`, `MAX_EVIDENCE_URLS`, page limit 50, and similar constants in `contracts/halt_module.py`).

## Bonds

`report_exploit` is payable. The attached value must equal `reporter_bond` exactly. Wrong amount reverts; no partial credit.

## Nondet isolation

Evidence fetch and LLM calls run inside `run_nondet_unsafe`. Protocol status and `emit_transfer` (refund or slash) run **after** consensus returns. Locals are copied out of storage before the nondet block.

## Fail-closed LLM garbage

Missing JSON, missing `exploit` / `remediated` booleans, or consensus failure raises `UserError`. The protocol stays **ACTIVE**. We do not halt on unparseable leader output.

## Governor-only unhalt

`request_unhalt` requires `msg.sender == protocol.governor`.

## Pagination

Contract views and the Django API cap `limit` at 50 (`MAX_PAGE_LIMIT` / `API_MAX_PAGE_SIZE`).

## Rate limits

The indexer throttles and retries GenLayer RPC (`-32006` / 429). The UI reads lists from the indexer, not by hammering `readContract` for every card. Sync POSTs can be gated with `X-Sync-Secret`.

## Secrets

`.env` and `.env.local` are gitignored. Use `.env.example` files. Rotate `DJANGO_SECRET_KEY` and `SYNC_SHARED_SECRET` if they ever land in git or a screenshot. Contract addresses are public.

## Adversarial review (v1)

| Question | Answer |
|---|---|
| Halt with one fake page on an allowlisted domain? | Yes, if `min_evidence` is 1 and the definition is loose. Mitigate with a stricter definition, higher `min_evidence`, and the reporter bond. Challenge/overturn is P1, not shipped. |
| Register `attacker.com` and self-halt? | Yes. That is the governor’s protocol. Other protocols are unaffected. |
| Partial fetch outages → false halt? | No. Fetch count must be ≥ `min_evidence`, then a strict majority of **successfully fetched** pages must vote `exploit=true`. Too few fetches error; the report reverts. |
| UI hammers Studionet into 429? | Writes go through the wallet. Reads go through the indexer (Celery poll + optional fast-path sync). RPC client retries rate limits. |
| Direct tests hide Address bugs? | Direct tests mock nondet. Studio smoke and the live Demo Vault were used for Address / payable paths. |
