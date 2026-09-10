# Backend — ProofHalt thin indexer

Django + DRF + Postgres + Redis + Celery. It caches Halt Module state so the
frontend can read lists and detail pages without hammering studionet.

**Ownership rule:** this service **never invents or overrides halt decisions**.
Every field it serves is a copy of a contract view result
(`IMPLEMENTATION_PLAN.md` §2.2). Writes go straight from the wallet to GenLayer.

---

## Layout

```
backend/
├── manage.py
├── Procfile                  # web / worker / beat process types
├── requirements.txt          # runtime deps
├── requirements-dev.txt      # + pytest, pytest-django
├── config/
│   ├── settings.py           # env-driven settings
│   ├── settings_test.py      # SQLite, no network, eager Celery
│   ├── celery.py             # app + beat schedule
│   ├── urls.py / api_urls.py
│   └── env.py                # tiny env readers
├── apps/
│   ├── common/               # u256 / GEN formatting, offset-limit pagination
│   ├── protocols/            # Protocol model, serializers, read views
│   ├── cases/                # Case model, serializers, read views
│   └── sync/
│       ├── genlayer_client.py  # read-only gen_call JSON-RPC client
│       ├── indexer.py          # poll-and-diff upserts (plain functions)
│       ├── tasks.py            # Celery wrappers
│       ├── models.py           # SyncCursor
│       ├── views.py            # /api/health + fast-path sync
│       └── management/commands/sync_chain.py
└── tests/                    # 69 tests, no network required
```

---

## Run locally

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

cp .env.example .env
# then set at least: DJANGO_SECRET_KEY, DATABASE_URL, REDIS_URL, HALT_MODULE_ADDRESS
```

Postgres + Redis:

```bash
# Postgres (any instance works — Supabase/Neon URLs are fine too)
createdb emergency_halt

# Redis
redis-server            # or: redis-cli ping  → PONG
```

**Redis security:** do not expose Redis on the public internet. Local
`REDIS_URL=redis://localhost:6379/0` (no password) is fine for development.
In production use AUTH and prefer TLS, e.g.
`redis://:password@host:6379/0` or `rediss://:password@host:6379/0`
(same for `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` when set). See
`docs/SECURITY.md`.

Migrate and serve:

```bash
python manage.py migrate
python manage.py runserver 127.0.0.1:8000
```

Indexer processes (**both are required** — worker alone never polls):

```bash
celery -A config worker -l info      # terminal 2
celery -A config beat   -l info      # terminal 3
```

Beat enqueues `apps.sync.tasks.poll_and_diff` every
`SYNC_POLL_INTERVAL_SECONDS` (default 300 / 5 minutes). Verify the wiring with:

```bash
celery -A config inspect registered     # lists apps.sync.tasks.*
celery -A config call config.debug_task
```

One-shot sync without Celery (useful for seeding after a deploy):

```bash
python manage.py sync_chain --counts
python manage.py sync_chain --all
python manage.py sync_chain --protocol 0
```

---

## API

Base path `/api`. Both `/api/protocols` and `/api/protocols/` work.
All ids in request paths and responses are **on-chain ids**, not database rows.

| Method | Route | Notes |
|---|---|---|
| GET | `/api/health` | DB check, chain config, indexed counts, sync cursor |
| GET | `/api/protocols?offset=&limit=&status=&governor=` | Paginated list |
| GET | `/api/protocols/<id>` | Detail + embedded `active_case` |
| GET | `/api/protocols/<id>/cases?offset=&limit=&status=` | Cases for one protocol |
| GET | `/api/cases?offset=&limit=&protocol_id=&status=&reporter=` | Paginated list |
| GET | `/api/cases/<id>` | Detail + embedded `protocol` summary + `events` (oldest-first) |
| POST | `/api/sync/protocols/<id>` | **Fast path** — inline resync, returns fresh protocol |
| POST | `/api/sync/all` | Full poll-and-diff pass (seeding / manual refresh) |

`POST` routes require `X-Sync-Secret: <SYNC_SHARED_SECRET>` when that env var
is set (header only — query-string secrets are rejected). Empty secret is for
local `DEBUG=True` only.

### Pagination envelope

```json
{
  "count": 2,
  "offset": 0,
  "limit": 20,
  "next": "http://host/api/protocols?limit=20&offset=20",
  "previous": null,
  "results": [ ... ]
}
```

`limit` is capped at `API_MAX_PAGE_SIZE` (50), matching the contract's
`MAX_PAGE_LIMIT`.

### Protocol shape

```json
{
  "id": 0,
  "name": "Demo Vault Protocol",
  "status": "HALTED",
  "is_halted": true,
  "governor": "0x1111111111111111111111111111111111111111",
  "backup_unhalters": ["0x3333333333333333333333333333333333333333"],
  "exploit_definition": "Halt if evidence shows an active drain of user funds.",
  "trusted_domains": ["rentry.co"],
  "protected_actions": ["withdraw", "transfer"],
  "allowed_while_halted": [],
  "min_evidence": 1,
  "appeal_window_seconds": 86400,
  "reporter_bond": "1000000000000000000",
  "reporter_bond_gen": "1",
  "active_case_id": 1,
  "case_count": 1,
  "halted_at": "2026-09-08T07:00:30Z",
  "appeal_ends_at": "2026-09-09T07:00:30Z",
  "created_at": "2026-09-08T07:00:00Z",
  "synced_at": "2026-09-08T07:01:00Z",
  "active_case": { "...": "case list shape, detail endpoint only; null when ACTIVE" }
}
```

### Case shape

```json
{
  "id": 1,
  "protocol_id": 0,
  "reporter": "0x2222222222222222222222222222222222222222",
  "allegation": "Funds are being drained right now.",
  "evidence_urls": ["https://rentry.co/incident"],
  "verdict_exploit": true,
  "verdict_summary": "Active exploit confirmed",
  "status": "ACCEPTED_HALT",
  "bond_amount": "1000000000000000000",
  "bond_amount_gen": "1",
  "bond_settled": false,
  "event_count": 1,
  "submitted_at": "2026-09-08T07:00:30Z",
  "synced_at": "2026-09-08T07:01:00Z",
  "protocol": { "id": 0, "name": "...", "status": "HALTED", "governor": "0x..." },
  "events": [
    {
      "id": 1,
      "case_id": 1,
      "protocol_id": 0,
      "event_type": "REPORT_EVALUATED",
      "actor": "0x2222222222222222222222222222222222222222",
      "statement": "Funds are being drained right now.",
      "evidence_urls": ["https://rentry.co/incident"],
      "consensus_bool": true,
      "consensus_summary": "Active exploit confirmed",
      "from_status": "OPEN",
      "to_status": "ACCEPTED_HALT",
      "bond_amount": "1000000000000000000",
      "bond_disposition": "ESCROWED",
      "created_at": "2026-09-08T07:00:30Z"
    }
  ]
}
```

**u256 note:** `reporter_bond` / `bond_amount` are decimal **strings** (they
exceed `Number.MAX_SAFE_INTEGER`). `*_gen` fields are pre-formatted
18-decimal display strings. Case ids are 1-indexed; `active_case_id == 0`
means "no active case".

**v1.1 additive fields:** `backup_unhalters` is a list of addresses (0–3).
`halted_at` and `appeal_ends_at` are ISO-8601 UTC datetimes (`appeal_ends_at`
= `halted_at + appeal_window_seconds`); both are `null` when the protocol is
not halted. Case **list** omits `events`; case **detail** includes
`events` oldest-first. Report-round `verdict_summary` is immutable — later
rounds live only on events (`bond_disposition`, `consensus_summary`).

Unknown protocol/case ids return `404`. A studionet outage on a `POST /sync/*`
returns `502` with a `detail` message; a contract revert (bad id or wrong
`HALT_MODULE_ADDRESS`) returns `404`.

---

## Fast path after a wallet tx

The demo loop needs `HALTED` visible seconds after `report_exploit` is
accepted, so the frontend should do:

1. `writeContract(...)` → wait for the receipt
2. `POST /api/sync/protocols/<id>` (runs 2–3 reads **inline**, no queue wait)
3. Render the `protocol` object from that response, or re-`GET` the detail route

`sync_protocol` reads `get_protocol` plus every page of
`list_protocol_cases` and, for each case, `list_case_events` until
exhausted, so the new case detail and timeline land in the same call.

---

## How the indexer works

`poll_and_diff` (beat, every `SYNC_POLL_INTERVAL_SECONDS`, default 5 minutes):

1. `get_protocol_count()` / `get_case_count()` / `get_case_event_count()` —
   the diff anchors
2. Refresh **all** protocol pages: protocols mutate in place
   (`HALTED → ACTIVE` on unhalt does not bump any counter)
3. Page in the new case tail from the cursor's `case_count` (each case also
   pages `list_case_events`)
4. Re-read the cases of any protocol whose fields changed (an unhalt flips its
   case to `CLEARED`)
5. Page **new** global events via `get_case_event(id)` for ids
   `(cursor.case_event_count+1)…count` — catches events that do not change
   protocol status (failed challenge/unhalt, `finalize_appeal`)
6. Persist counts + `last_success_at` on `SyncCursor`, or `last_error` on failure

Event rows are upserted by on-chain id and **never rewritten**.

Every RPC call is throttled by `GENLAYER_RPC_THROTTLE_SECONDS` and retries
rate limits (`-32006`, HTTP 429/5xx) with backoff. Contract reverts are
permanent and are surfaced instead of retried.

---

## Tests

```bash
cd backend
.venv/bin/python -m pytest -q
```

Tests use `config.settings_test`: SQLite in memory, eager Celery, and an
in-memory `FakeHaltModule` (`tests/fakes.py`) that reproduces the exact view
dict shapes from `contracts/halt_module.py`. No Postgres, Redis or network
needed. Run the same suite against Postgres with:

```bash
TEST_DATABASE_URL=postgres://user:pass@localhost:5432/emergency_halt_test \
  .venv/bin/python -m pytest -q
```

---

## Deploy (Render or equivalent)

Three process types (see `Procfile`) — **all three must exist**, or nothing
polls the chain:

| Process | Command |
|---|---|
| web | `python manage.py migrate --noinput && gunicorn config.wsgi:application --bind 0.0.0.0:$PORT` |
| worker | `celery -A config worker -l info --concurrency=2` |
| beat | `celery -A config beat -l info` |

Build command: `pip install -r backend/requirements.txt`
(root directory `backend`).

Env vars are listed in `.env.example` and in `deploy/notes.md`. After the
first deploy, seed the cache once:

```bash
curl -X POST -H "X-Sync-Secret: $SYNC_SHARED_SECRET" https://<api-host>/api/sync/all
curl https://<api-host>/api/health
```
