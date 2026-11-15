---
name: backend-cloner
description: Reconstruct a backend and API from a live web app using only observed client-server traffic. Use when asked to clone, reverse-engineer, reimplement or document an undocumented HTTP/JSON API, produce an OpenAPI spec or ER schema from a HAR capture, or rebuild a server that an existing front end can talk to unchanged. Captures HAR plus WebSocket/SSE frames with Playwright, distils endpoints and JSON schemas deterministically, then synthesizes an independent clean-room backend (FastAPI or Node + PostgreSQL + Docker) with mock seed data and parity tests. Enforces observed-vs-inferred labeling, zero copying of proprietary code, data or assets, and authorization-scoped, non-invasive inspection only. Do not use for reading a source repository, security testing, auth or paywall bypass, mass data harvesting, or load and fuzz testing.
compatibility: Python 3.9+. scripts/capture_traffic.py needs the `playwright` package and a Chromium build (`pip install playwright && playwright install chromium`) plus network access to the authorized target. scripts/parse_har.py and scripts/generate_openapi.py are dependency-free (stdlib only) and run fully offline.
metadata:
  version: "1.0.0"
  category: reverse-engineering
  output: openapi-3.0 + er-schema + cleanroom-backend
allowed-tools: Bash Read Write Edit Glob Grep
---

# Backend Cloner

Rebuild a working backend for a web application from the **outside in**: observe how the
front end talks to its server, distil that traffic into a formal contract, then write an
**independent** server implementation against that contract instead of the original code.

The browser is the black box. The HAR file is the ground truth. Everything else is inference,
and must be labeled as such.

## When to use

Trigger this skill when the user wants to:

- "Clone the backend / API" of an existing web app, or make their own front end work against a rebuilt server.
- Recover an undocumented HTTP or JSON API surface, or produce an OpenAPI spec from observed traffic.
- Reconstruct a database schema and business logic from client behaviour alone.
- Document third-party integrations (polling, webhooks, WebSocket, SSE) that are visible in the browser.
- Produce a mock or stub server that is wire-compatible with a live app for testing or migration.

Do **not** use it for: reading or refactoring a source repository they already have; security
assessment, exploitation or fuzzing; bypassing authentication, licensing, paywalls, rate limits
or geo restrictions; bulk extraction of other people's data; or load testing a target they do
not own.

## Non-negotiable rules

These are gates, not advice. Stop the workflow if one cannot be satisfied.

### 1. Authorization before inspection

Capture only when one of these is true, and record which in `recon/00-scope.md`:

- The user owns the application, or has written permission from the owner.
- The user is inspecting their own authenticated session in an app they are legitimately entitled to use, and the target's terms do not prohibit it.
- The traffic is a public, unauthenticated, non-paywalled surface the user is allowed to access.

Prohibited, always: credential or token theft, session hijacking, forced browsing into other
users' resources, MFA or paywall circumvention, vulnerability probing, rate-limit evasion,
scraping personal data at scale, and capturing traffic of accounts that are not the user's own.

Minimize by default: capture one ordinary user journey, use a dedicated test account, and
keep only the traffic needed to describe the contract. `parse_har.py` masks credentials and
PII; that masking is a safety net, not permission to hoard data.

### 2. Seen vs. inferred — never blur the line

Every statement in the deliverable carries one provenance label:

| Label | Meaning | Allowed evidence |
|---|---|---|
| `OBSERVED` | Directly present in a captured HTTP/WS/SSE payload | HAR entry, frame index, status code |
| `DERIVED` | Mechanically computed from observations by a script | Parser output, normalized path, inferred schema |
| `INFERRED` | Your reasoning about unobserved server-side behaviour | Must state the observation it rests on and a test that could falsify it |
| `UNKNOWN` | Not determinable from client traffic | Must stay `UNKNOWN`; never silently fill it in |

Rules that follow from this:

- Response fields you never saw are not "probably there". They are `UNKNOWN`.
- A database table is never `OBSERVED`. The client cannot see tables. Table names, foreign keys, indexes and constraints are `INFERRED` from payload shape and behaviour.
- Status codes, headers, pagination style and error envelopes are `OBSERVED` only if captured; otherwise mark them `INFERRED` with the reasoning.
- Never present an inferred rule as a captured fact to make the spec look complete. A gap labeled `UNKNOWN` is a correct result.

### 3. Cleanroom replication — zero copying

You are rebuilding behaviour, not redistributing an artifact.

Never copy, vendor, decompile into, or paste in: the original server code, minified or
bundled client code, source maps as implementation input, database dumps, seed fixtures,
media or font assets, icon sets, or long verbatim UI copy. Never reuse their schema
definitions, comments or docstrings wholesale.

You may use: HTTP methods, paths, parameter names, field names, status codes, content types,
error shapes, and the *facts* of the protocol — these are functional interface requirements,
not creative expression. Field names are the contract; their implementation is yours.

Everything below the contract is your own design: ORM models, migrations, service layout,
validation, logging, auth implementation, and test code. Write it from
[references/architecture_template.md](references/architecture_template.md), not from anything
you saw in a bundle. Run [references/cleanroom_checklist.md](references/cleanroom_checklist.md)
before you call the work finished.

### 4. Deterministic tooling

`parse_har.py` and `generate_openapi.py` must be byte-reproducible: same input files in, same
bytes out. No timestamps, no UUIDs, no iteration-order dependence, no randomness, no network
calls. Sort every collection before writing. If you extend the scripts, preserve this property
— it is what makes spec diffs reviewable.

Capture itself is a recording, not a computation: it is non-deterministic by nature and its
raw output is treated as input data, never regenerated to "fix" a diff.

## Workflow

Work the phases in order. Each phase writes to `recon/` (or the workdir the user names) so the
next phase and a human reviewer can audit the trail. Do not skip Phase 0, and do not start
Phase 5 until Phase 3 is reviewed.

### Phase 0 — Scope and authorize

Write `recon/00-scope.md` with: target origin(s), the authorization basis from Rule 1, the
account(s) used, the user journeys in scope, and an explicit out-of-scope list. Set
`--origin` accordingly so the capture script refuses to leave that origin.

### Phase 1 — Capture traffic

Drive the app through the flows that matter (sign-in, primary CRUD, pagination, search,
polling, realtime, sign-out) with the browser recorder:

```bash
python3 scripts/capture_traffic.py \
  --url https://app.example.com \
  --out recon/capture \
  --origin https://app.example.com \
  --headed \
  --duration 900
```

Use `--flow recon/flows.json` to replay a deterministic step list instead of navigating by
hand. The script writes `network.har`, `websocket.jsonl`, `sse.jsonl`, `console.jsonl`,
`storage_state.json` and `session.json`. See `python3 scripts/capture_traffic.py --help`.

Treat `recon/capture/` as sensitive: it contains live cookies in `storage_state.json` and
unmasked bodies. Never commit it, never upload it, add it to `.gitignore`, and mask before
sharing. If a session token leaks into the workspace, say so and rotate it.

### Phase 2 — Distil endpoints and schemas

```bash
python3 scripts/parse_har.py \
  --har recon/capture/network.har \
  --ws recon/capture/websocket.jsonl \
  --sse recon/capture/sse.jsonl \
  --out recon/distilled
```

Outputs: `endpoints.json` (deduplicated, path-templated, secrets masked), `schemas.json`
(inferred JSON Schema per request/response), `js_routes.json` (routes found only in bundles or
`.map` files — these are `INFERRED`, never `OBSERVED`), and `parse_report.json` (counts,
dropped resources, masking events, input hashes).

Read `parse_report.json` before trusting the output. If endpoints you saw in the browser are
missing, the flow was not captured — go back to Phase 1 rather than inventing them.

### Phase 3 — Synthesize the specification

```bash
python3 scripts/generate_openapi.py \
  --endpoints recon/distilled/endpoints.json \
  --schemas recon/distilled/schemas.json \
  --routes recon/distilled/js_routes.json \
  --title "Example API (reconstructed)" \
  --server https://api.example.com \
  --out recon/openapi.yaml
```

Result is an OpenAPI 3.0 document where every operation carries `x-evidence` and
`x-observed-count`. Routes that appear only in bundles land under `x-inferred-routes`, kept
separate on purpose: they are hypotheses, not contracts. Review the YAML by hand — the
generator describes what was seen, it does not judge what is correct.

### Phase 4 — Architecture, state machines, ER model

Fill in [references/architecture_template.md](references/architecture_template.md) as
`recon/architecture.md`. This is where `OBSERVED` contracts become your `INFERRED` design:

- **Contract table** — one row per operation, with evidence reference and confidence.
- **ER schema** — entities, attributes, relationships, cardinality, and the payload field each attribute is inferred from. Columns with no observed source are `UNKNOWN`, not guessed.
- **State machines** — one per flow: `auth` (anonymous → authenticated → refreshed → expired → signed out), `CRUD` (create → read → update → delete, incl. optimistic updates), `polling` (interval, backoff, terminal condition), `webhooks`/`realtime` (connect → subscribe → message → reconnect → close). Use mermaid `stateDiagram-v2` so the doc renders.
- **Server-side logic hypotheses** — each with its supporting observation and a falsifying test.
- **Unknowns** — an explicit list of what the client could not reveal (server-side jobs, admin surfaces, deletion semantics, storage layout).

### Phase 5 — Build the independent backend

Implement strictly from `recon/openapi.yaml` + `recon/architecture.md`. Never open the
original bundle "just to check" an implementation detail — if it is not in the spec, it is
`UNKNOWN` and belongs in the unknown list or behind a documented assumption.

Target stack (substitute only if the user asks): FastAPI + SQLAlchemy + Alembic +
PostgreSQL 16 + Docker Compose, or Express/Fastify + Prisma + PostgreSQL if the user prefers
Node. Requirements:

- Every operation in the spec is routed, typed and validated; unobserved routes are not silently invented.
- Response shapes, field names, status codes and error envelopes match the spec exactly, including nullability, so the existing front end can talk to it unmodified.
- Config via environment variables with a committed `.env.example`; no secrets in the repo.
- Idempotent seed script producing **synthetic** mock data that matches observed shapes — never copied rows, never real user data.
- Real auth implementation (own password hashing, own token issuance) matching the *observed* scheme, not a bypass.
- Migrations that build the schema from empty.

### Phase 6 — Prove parity

Generate contract tests from the spec, not from memory: for each operation, assert status
codes, required fields, types, nullability and auth enforcement against the rebuilt server.
Then add flow tests from the state machines (sign-in, refresh, expiry, pagination loop,
reconnect) using the sanitized captures as golden fixtures. Record results in
`recon/parity-report.md`, including tests that fail because behaviour was `UNKNOWN`.

Parity means *observable equivalence for captured flows*, not byte-identical internals. Say
plainly which flows are covered, which are inferred-only, and which were never observed.

### Phase 7 — Cleanroom audit

Run [references/cleanroom_checklist.md](references/cleanroom_checklist.md) end to end and
attach the completed attestation. If any check fails — copied snippet, vendored asset,
redistributed fixture, unmasked secret — fix it before reporting completion.

## Output layout

```
recon/
├── 00-scope.md              # authorization, origins, accounts, in/out of scope
├── capture/                 # SENSITIVE raw recording (gitignored)
│   ├── network.har  websocket.jsonl  sse.jsonl  console.jsonl
│   ├── storage_state.json   # live cookies — never commit
│   └── session.json
├── distilled/               # deterministic parser output
│   ├── endpoints.json  schemas.json  js_routes.json  parse_report.json
├── openapi.yaml             # OpenAPI 3.0 contract, evidence-tagged
├── architecture.md          # contracts vs. inferred logic, ER model, state machines
├── parity-report.md         # what passes, what is inferred-only, what is unknown
└── cleanroom-attestation.md # signed-off checklist
```

## Reading map

Load only what the current phase needs:

- Phase 0 and Phase 7 → [references/cleanroom_checklist.md](references/cleanroom_checklist.md)
- Phase 4 → [references/architecture_template.md](references/architecture_template.md)
- Any script flag or failure → `python3 scripts/<script>.py --help`, then the script source
- Exact output fields → `recon/distilled/parse_report.json`, then `endpoints.json`

## Stop conditions

Halt and report instead of proceeding when:

- Authorization is unclear or the target's terms forbid inspection.
- The capture requires bypassing a login, paywall, CAPTCHA, MFA prompt or rate limit.
- The user asks you to copy source, assets, or a database rather than reconstruct behaviour.
- Traffic is encrypted end-to-end by a client-side scheme the browser will not reveal — you cannot observe it, so it is `UNKNOWN`; do not guess a protocol.
- The spec would need invented endpoints to look complete. Ship the honest partial spec.

## Anti-patterns

- Calling an inferred Postgres table "observed", or filling unobserved fields with plausible types.
- Treating `x-inferred-routes` from a bundle as implemented contract.
- Writing tests that assert your implementation against itself instead of against the spec.
- Committing `recon/capture/`, or pasting a token into a report, an issue or a chat.
- Reusing the original's OpenAPI/GraphQL schema text or seed fixtures verbatim.
- Expanding scope from "one user journey" to "all data on the site".
