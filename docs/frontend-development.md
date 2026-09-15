# QUORUM frontend development

QUORUM runs as two local processes: the FastAPI backend remains authoritative
for operational state and deterministic decisions, while the Next.js app reads
safe product projections through a same-origin proxy.

## Prerequisites

- Python 3.13 virtual environment installed at `.venv`
- Node.js and npm
- Frontend dependencies installed with `npm install` inside `web/`

The frontend currently uses Next.js 16.3.0, React 19.2.8, TypeScript 5, and
Tailwind CSS 4. Its small source-owned UI primitives follow shadcn/ui component
patterns without adding a runtime component-library dependency.

## Start the backend

From the repository root:

```bash
PYTHONPATH=. .venv/bin/uvicorn quorum.api.app:app --reload --host 127.0.0.1 --port 8000
```

The API is available at `http://127.0.0.1:8000`; health is available at
`http://127.0.0.1:8000/health`.

This local product run does not require a Gemini key and does not send Telegram
messages. Do not run the live agent or messaging scripts to start the web
product. The mutation endpoints are intended only for this local synthetic
workspace and must not be exposed publicly without authentication.

For an isolated Phase 2 QA state containing a RED decision, cancellable PENDING
effect, and GREEN/YELLOW/RED/SILENT ledger entries, start this backend instead:

```bash
PYTHONPATH=. .venv/bin/uvicorn scripts.phase2_qa_app:app --host 127.0.0.1 --port 8000
```

The helper builds state through QUORUM's domain services and is never imported
by normal application startup.

The normal backend also exposes Phase 3 Demo Mode. It uses only the deterministic
classifier and existing coordination services; it does not require or consume a
Gemini key and never calls the Telegram channel.

## Start the frontend

In a second terminal:

```bash
cd web
npm install
npm run dev
```

The web product is available at `http://localhost:3000`. The development script
uses webpack with polling so it remains reliable on hosts with conservative
file-watch limits.

For a production-equivalent local run:

```bash
cd web
npm run build
npm run start
```

## Environment configuration

The only frontend integration setting is server-only:

```dotenv
QUORUM_API_BASE_URL=http://127.0.0.1:8000
```

Copy `web/.env.example` to `web/.env.local` only when the backend is not using
the default address. The browser never receives this value. Next.js rewrites
`/api/quorum/:path*` to the backend, keeping browser requests same-origin and
avoiding permissive CORS. Neither API keys nor channel credentials belong in
the frontend environment.

## Implemented product pages

- `/` — Overview with Attention Budget, operational counts, open human
  decisions, active operations, and recent decision activity. Refreshes every
  10 seconds while the tab is visible.
- `/shifts` — enriched operational shift list with client-side All, Needs
  coverage, and Fully staffed filters.
- `/shifts/[id]` — coverage, assignments, active gaps, deterministic candidate
  ranking, related pending effects, human decisions, and decision records.
  Refreshes every 10 seconds while visible.
- `/human-decisions` — live RED-decision queue, safe evidence and related
  context, backend-provided actions, optional coordinator notes, confirmation,
  conflict handling, and authoritative resolved state. Polls every 5 seconds.
- `/pending-effects` — all pending-effect lifecycle states with backend-provided
  cancelability, display-only settlement timing, confirmed cancellation, and
  settlement-race messaging. Polls every 5 seconds.
- `/decision-feed` — sanitized chronological Decision Ledger with route filters,
  optional shift deep links, and cursor-based older-record loading. Polls every
  7.5 seconds.
- `/demo` — controlled Riverside simulation catalog, confirmed reset/run
  commands, backend-authored workflow timeline, outcome, coverage, Attention
  Budget impact, and links into the real operational pages.
- `/volunteers` — searchable safe synthetic roster with backend role, status,
  and availability filters.
- `/volunteers/[id]` — safe profile, declared synthetic availability,
  capacity-guarded assignments, displayed constraints, and related ledger
  activity. Contact load is explicitly labelled “Not yet tracked.”
- `/interrupts`, `/pending`, and `/feed` redirect to the corresponding Phase 2
  product pages for compatibility.
- Unfinished Analytics and Settings routes are intentionally absent from the
  primary navigation. Current-state counts stay on Overview; configuration
  remains environment-owned and is never exposed to the browser.

All implemented data pages include loading, empty, and backend-error states.
Previously loaded state remains visible with a stale-data notice if a later poll
fails.

## Read APIs used by the product

- `GET /health`
- `GET /dashboard`
- `GET /shifts`
- `GET /shifts/{shift_id}`
- `GET /attention-budget`
- `GET /pending?status=PENDING|SETTLING|SETTLED|CANCELLED|FAILED`
- `POST /pending/{pending_id}/cancel`
- `GET /interrupts?status=OPEN|RESOLVING|RESOLVED`
- `GET /interrupts/{interrupt_id}`
- `POST /interrupts/{interrupt_id}/resolve`
- `GET /feed?route=GREEN|YELLOW|RED|SILENT%2FDEFER&category=...&shift_id=...&cursor=...`
- `GET /demo/scenarios`
- `POST /demo/scenarios/{scenario_id}/run`
- `GET /demo/runs` and `GET /demo/runs/{run_id}`
- `POST /demo/reset`
- `GET /volunteers?role=...&status=...&available=...`
- `GET /volunteers/{volunteer_id}`

UI response models live in `quorum/api/schemas.py`. Backend joins and derived
read state live in `quorum/services/read_models.py`; the frontend never
reimplements eligibility, ranking, safety, routing, capacity, budget, or
settlement rules. A shared representative fixture at
`web/src/lib/fixtures/ui-api.json` is validated by the Pydantic contract tests
and consumed by the TypeScript contract module.

## Validation

Backend, from the repository root:

```bash
PYTHONPATH=. .venv/bin/python -m pytest -q
```

Frontend, from `web/`:

```bash
npm run lint
npm run typecheck
npm run build
```

## Local mutation model

The mutation UI is labelled **Local Demo Coordinator**. This is a truthful
synthetic actor identifier, not an authenticated identity. Human-decision
actions come only from `allowed_actions` returned by the API; pending-effect
cancel buttons come only from `can_cancel`. Both flows require confirmation,
wait for the server response, and immediately refetch authoritative state.

Interrupt resolution is version-guarded and rejects stale or duplicate
resolution. The current API records the decision and an audit ledger entry but
reports `automatic_continuation=false`: no safe runtime agent resumer is wired
in this phase. Pending cancellation uses the backend lifecycle transition, so a
settlement race is displayed rather than overwritten by optimistic UI state.

## Deterministic Demo Mode

Demo Mode operates only on the in-memory synthetic `org:riverside` workspace.
Every run is labelled `deterministic_demo`, is idempotent by a client command
key, and stores a safe recovery-run timeline. The orchestration service composes
the real event handler, gap detector, eligibility/ranking, deterministic reply
classifier, transport-condition service, assignment capacity guard, Layer-0
escalation, Attention Budget, Pending Effects, Interrupt Service, and Decision
Ledger.

- **Scenario A — Autonomous Recovery:** accepts a synthetic cancellation,
  fills role gaps through ranked candidates, and completes without a human
  decision.
- **Scenario B — Conditional Transport:** feeds the exact synthetic response
  “I can do it, but I need a ride.” through the deterministic classifier,
  obtains `ACCEPT_IF` with canonical `transport`, resolves the synthetic
  community-van option, and confirms capacity-guarded assignments.
- **Scenario C — Safety Escalation:** classifies an injury/complaint as
  `OUT_OF_SCOPE`, applies Layer-0 RED routing, spends or overrides the same
  application Attention Budget according to policy, and creates the real
  Human Decision record.

`POST /demo/reset` restores the Riverside fixture and clears only its in-memory
assignments, gaps, negotiations, pending effects, interrupts, Attention Budget,
Decision Ledger, idempotency state, and recovery runs. It does not read or
change credentials, files, provider configuration, or external services.

No real volunteer is contacted. Demo outreach settles through the existing
controlled local effect handler rather than Telegram. Bedrock and Gemini remain
available to separately invoked live scripts but are never constructed by Demo
Mode.

## Current limitations

- Runtime state is in memory and resets when FastAPI restarts.
- Runtime state, human decision resolutions, and cancellations are not durable
  across backend restarts.
- Authentication, role-based authorization, and production identity are
  deferred. Mutation APIs are local-only.
- Automatic workflow continuation after a human decision is not wired. The
  decision record is resolved truthfully and the UI states this limitation.
- Settings remains intentionally deferred. A future `live_model` demo mode is
  not implemented.
- Analytics is omitted because durable historical instrumentation does not yet
  exist; the product does not present in-memory snapshots as performance data.
- Polling is used for live surfaces and pauses while the tab is hidden;
  WebSockets are intentionally absent.
- TypeScript interfaces remain explicit rather than generated from OpenAPI; the
  shared cross-language fixture catches response-shape drift without adding a
  code-generation toolchain in this phase.
- Deployment and production credential handling remain outside this phase.
