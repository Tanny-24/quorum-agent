# QUORUM Product UI Roadmap

## Delivery principles

- Preserve the deterministic authority boundary and current regression suite.
- Treat frontend mocks as schema fixtures, never evidence that a backend capability exists.
- Add typed read models before connecting production pages.
- Keep V1 on REST plus polling.
- Use only synthetic data in Demo Mode.
- Add durable, tenant-safe state before deploying to multiple visitors or multiple API workers.
- Do not expose secrets, raw provider identifiers, unsafe volunteer fields, prompts, or unfiltered payload dictionaries.

## Phase 1 — Frontend skeleton and contract fixtures

**Scope:** create a Next.js/TypeScript application with Tailwind and shadcn/ui, route groups, accessible app shell, sidebar/top bar, theme tokens, error boundary, API client boundary, and fixtures matching the proposed contracts. Pages are clearly labeled as mock/fixture-backed.

**Likely files:** new `web/` directory (`app/`, `components/`, `lib/api/`, `lib/contracts/`, `fixtures/`, tests), root developer scripts/documentation as needed.

**Acceptance criteria:** all eight routes render inside the shared shell; no chatbot composer; responsive sidebar; synthetic badge; loading/empty/error component states; no duplicated business logic.

**Tests:** TypeScript check, lint, component tests for navigation/state components, accessibility smoke, viewport snapshots.

**Dependencies:** approved frontend package versions and a decision to proxy API calls through Next.js or configure FastAPI CORS.

**Risk:** Low. Main risk is allowing fixtures to drift from planned backend contracts.

## Phase 2 — Backend product read surface

**Scope:** add explicit Pydantic response/view models; expand the store protocol; implement joined queries for dashboard, shifts, volunteers, pending effects, budgets, enriched interrupts, and paginated feed. Standardize errors and timestamps. Keep all existing routes compatible or version the API deliberately.

**Likely files:** `quorum/api/app.py` split into `quorum/api/routes/` and `quorum/api/schemas/`; `quorum/persistence/base.py`; `quorum/persistence/memory.py`; new query/read-model service modules; API tests.

**Acceptance criteria:** OpenAPI contains concrete response schemas; `GET /dashboard`, enriched `GET /shifts`, `GET /shifts/{id}`, volunteer reads, `GET /pending`, `GET /attention-budget`, interrupt detail/filtering, and cursor-based feed work against synthetic state; no secret fields appear.

**Tests:** response-schema snapshots, route success/404/filter/pagination tests, privacy allowlist tests, deterministic rank/join tests, existing 28-test regression.

**Dependencies:** final data contracts from the UI spec; policy on API prefix/versioning.

**Risk:** Medium. Current services access `MemoryStore` internals and the protocol is incomplete.

## Phase 3 — Overview integration

**Scope:** connect the Overview to `DashboardSummary`, polling, section-level retries, stale indicators, open RED queue, active recovery list, and recent feed.

**Likely files:** `web/app/page.tsx`, overview components, query hooks, API client, contract adapters, tests.

**Acceptance criteria:** no hard-coded metrics; counts reconcile with collection endpoints; last refresh is visible; partial failures do not blank the page; Attention Budget never implies a weekly period unless the API supplies one.

**Tests:** contract/mock-server tests, polling/refocus tests, empty/error/partial-data tests, accessibility checks.

**Dependencies:** Phase 2 dashboard and read contracts.

**Risk:** Low–Medium. Mislabeling derived metrics is the primary product risk.

## Phase 4 — Shift and volunteer workspaces

**Scope:** build shift list/detail and safe volunteer list/detail. Add filters, role coverage, gaps, assignments, ranked candidate explanations, negotiations, and related state links.

**Likely files:** `web/app/shifts/`, `web/app/volunteers/`, reusable coverage/table/filter components; backend query services if joins need refinement.

**Acceptance criteria:** capacity and shortfall exactly match backend data; candidate order and eligibility are never recomputed client-side; volunteer API/UI omits exact age and provider identifiers; deep links are stable.

**Tests:** join/coverage API tests, filter URL-state tests, candidate-order contract tests, privacy tests, responsive table/detail tests.

**Dependencies:** Phase 2 shift/volunteer endpoints and maintained relationship queries.

**Risk:** Medium. Ranking explanations and volunteer data need careful privacy/fairness presentation.

## Phase 5 — Human Decision Center

**Scope:** enrich interrupt backend semantics, configure safe resume behavior, define allowed decision enums, actor/note/version audit fields, then build queue/detail/resolution UX.

**Likely files:** `quorum/domain/models.py`, interrupt/query services, `quorum/api/routes/interrupts.py`, authentication/audit modules, `web/app/interrupts/`, decision components and tests.

**Acceptance criteria:** a RED item contains sufficient safe context; only backend-allowed actions render; duplicate/concurrent resolution is idempotent; failed resume leaves the item actionable; resolution actor and outcome are auditable; safety remains Layer-0 authoritative.

**Tests:** authorization, allowed-action validation, optimistic concurrency, idempotent double submit, failed-resume retry, Phase 0 restart regression, keyboard/screen-reader flows.

**Dependencies:** identity/authentication, durable domain state, Phase 2 interrupt reads, a configured `StrandsInterruptResumer` path.

**Risk:** High. This surface performs consequential actions and crosses durable agent-resume boundaries.

## Phase 6 — Pending Effects and Decision Feed

**Scope:** build active/history pending views, safe payload projections, cancel UX, cursor-paginated feed, route/category/entity filters, and cross-links.

**Likely files:** pending/feed API routes and schemas, read-model services, `web/app/pending/`, `web/app/feed/`, timeline/chip/filter components.

**Acceptance criteria:** cancel is available only for `PENDING`; settlement/cancel races reconcile from server state; feed loads newest-first and appends via cursor; raw payload/details JSON is never rendered by default.

**Tests:** cancel-versus-settle concurrency, failed effects, pagination stability, filter combinations, incremental polling, route chip accessibility.

**Dependencies:** Phase 2 reads; server-time metadata; stable feed cursor design.

**Risk:** Medium. Race conditions are correct in the core but must be represented accurately in UX.

## Phase 7 — API orchestration lifecycle and Demo Mode

**Scope:** connect event ingestion to a server-side recovery orchestrator that advances Gap statuses and invokes Coordinator/Negotiator through controlled tools/hooks. Add isolated demo reset/scenario commands and an in-product scenario stepper. Keep deterministic demo execution as the default; make live Gemini explicitly labeled and optional.

**Likely files:** new `quorum/services/orchestrator.py` or job module, event handlers, workflow/query services, demo API routes/schemas, demo workspace/session store, `web/app/demo/` or drawer components, integration tests.

**Acceptance criteria:** cancellation automatically progresses observable backend state; Telegram replies correlate to one volunteer/thread before classification; scenario A resolves with no RED item, B resolves transport condition, C pauses on persisted RED; reset affects only the caller’s synthetic workspace; no Telegram messages are sent.

**Tests:** end-to-end API scenarios with mocked external model/channel, idempotent repeated commands, cross-session isolation, status transition tests, prompt-injection/safety regressions, optional separately gated live-provider smoke.

**Dependencies:** durable/workspace-scoped state, correlation mapping, read APIs, Human Decision Center semantics.

**Risk:** High. The current complete flow exists in demos/services but not as one production orchestration loop.

## Phase 8 — Analytics instrumentation and UI

**Scope:** define metric semantics, persist status-transition events and outcome provenance, add period-scoped aggregations, then build analytics filters/cards/charts with definitions.

**Likely files:** domain event/metric models, persistence migrations, instrumentation in gap/assignment/interrupt/pending/contact services, analytics query/API modules, `web/app/analytics/`.

**Acceptance criteria:** every metric has a documented numerator, denominator, time basis, and source; autonomous-versus-human resolution is explicit; no metric is inferred from absence of a record; results reconcile against fixture scenarios.

**Tests:** metric fixtures, boundary dates/timezones, attribution cases, empty periods, aggregation performance, chart accessibility/table fallback.

**Dependencies:** durable historical storage and orchestration lifecycle instrumentation.

**Risk:** Medium–High. Incorrect attribution would undermine the product thesis.

## Phase 9 — Settings, security, accessibility, and responsive polish

**Scope:** ship safe read-only settings, then narrowly editable organization policy after authorization and audit logging. Complete security headers, request IDs, CORS/proxy configuration, keyboard flows, responsive behavior, and content polish.

**Likely files:** settings schemas/store/routes, auth middleware, audit logging, frontend settings route, design tokens, shared components, end-to-end accessibility tests.

**Acceptance criteria:** no secrets ever reach browser payloads; every mutation is authorized and audited; policy changes validate bounds and show before/after; WCAG-oriented automated and manual checks pass; primary flows work at mobile/tablet/desktop widths.

**Tests:** auth matrix, secret-field denylist, settings validation/audit, security-header checks, axe tests, keyboard/manual screen-reader checklist, responsive visual tests.

**Dependencies:** authentication/roles, durable config store, deployment-origin decision.

**Risk:** High for editable policy; Medium for presentation polish.

## Phase 10 — Deployment readiness

**Scope:** choose and implement durable application storage, background scheduling/worker model, migrations, health/readiness checks, logs/metrics, backups, environment separation, and deploy frontend/API. A simple local or managed relational store is acceptable before any cloud-specific migration.

**Likely files:** persistence implementation/migrations, application lifespan/wiring, worker entry point, deployment manifests, CI workflows, environment documentation.

**Acceptance criteria:** restart and multi-worker tests preserve state/idempotency; `/health` separates liveness/readiness; pending settlement runs outside manual UI ticks; demo tenants are isolated; rollback/backup procedure is exercised; frontend and API use HTTPS with restricted origins.

**Tests:** migration, restart, concurrent worker, idempotency, readiness failure, backup/restore, deployment smoke, synthetic load test.

**Dependencies:** hosting and database decision, auth, Phase 7 orchestration.

**Risk:** High. In-memory state and manual tick behavior are not deployable product foundations.

## Phase 11 — Optional AWS migration

**Scope:** only after account access and deployment needs justify it, complete a production `Store` implementation, conditional queries/writes, scheduler/event integration, and observability on selected AWS services. Keep Strands provider abstraction intact and do not make cloud migration a frontend dependency.

**Likely files:** full persistence adapter, infrastructure-as-code, deployment/config modules, cloud integration tests and runbooks.

**Acceptance criteria:** contract tests pass identically across stores; conditional assignment, budget, pending, and interrupt operations retain semantics; no claim is made before live validation.

**Tests:** shared store contract suite, local emulator where useful, gated live integration, failure/retry/idempotency tests.

**Dependencies:** AWS account activation, architecture/cost/security review, successful provider validation.

**Risk:** High and optional.

## Recommended next implementation slice

Start with Phase 1 and Phase 2 in parallel only at the contract boundary: establish final Pydantic/TypeScript shapes first, then let the frontend use schema-faithful fixtures while backend read queries are implemented. Do not connect UI mutation flows until authentication, durable state, and Human Decision semantics are specified.

The first reviewable milestone should be:

1. an accessible app shell with Overview and Shifts fixture states;
2. concrete OpenAPI response models;
3. working read-only `/dashboard`, enriched `/shifts`, and `/shifts/{id}` endpoints;
4. contract tests proving frontend fixtures match backend JSON;
5. the original 28 backend tests still passing.

