# QUORUM Frontend API Audit

## Scope and verified baseline

This audit describes repository state at `8921d41` on `main`. It is a product and API assessment only. No FastAPI routes, domain models, agent behavior, dependencies, or frontend code were changed.

The offline suite passes 28 tests. The repository contains a credible deterministic coordination core, real Strands/Gemini agent factories, a Telegram adapter, and durable Strands session/interrupt proofs. The public HTTP API is intentionally much narrower than the core. It is not yet a complete product backend for an operations dashboard.

The most important boundary is:

> LLM proposes; deterministic code disposes.

The frontend must display backend decisions and issue explicit commands. It must never reproduce ranking, classification, routing, attention-budget, capacity, or safety logic.

## What exists today

- One synthetic organization, six sites, 36 volunteers, and six shifts.
- Deterministic gap detection, volunteer eligibility, explainable candidate ranking, assignment capacity, and idempotency.
- Coordinator and per-shift/per-volunteer Negotiator factories backed by a provider-neutral Strands model factory.
- Deterministic reply classification fallback, Layer-0 safety override, and Gemini structured classification in the live demo.
- GREEN, YELLOW, RED, and SILENT/DEFER routing through `RoutingHook`.
- Persistent-in-store Attention Budget, PendingEffect state transitions, InterruptRecord lifecycle, and decision ledger.
- File-backed Strands conversation sessions and a separate process-restart interrupt durability spike.
- Provider-neutral Telegram send/normalize/poll behavior.
- A FastAPI app with ten routes.

Important product limitation: the complete recovery story is assembled in `CoreWorkflow` and the demo scripts. The FastAPI cancellation/no-show endpoints stop after event idempotency and gap detection. The Telegram webhook records a `VOLUNTEER_REPLY` event but does not classify it, bind it to a negotiation, or assign a volunteer. Coordinator, Negotiator, and `RoutingHook` are not wired into an API-level orchestration loop.

## Existing API inventory

FastAPI currently emits useful request schemas only for `StaffingEventRequest` and `DecisionRequest`. Most response schemas are generic `dict[str, Any]` or `list[dict[str, Any]]`, so generated TypeScript clients cannot recover the real domain contract.

| Method | Path | Request | Actual response | Source/service | Frontend readiness |
|---|---|---|---|---|---|
| GET | `/health` | None | `{ status: "ok" }` | Static route | Ready for a health indicator, but it does not report store/model/channel readiness. |
| GET | `/shifts` | None | Raw `Shift[]` | `MemoryStore.list_shifts()` | Partial. Missing site name, assigned counts, gaps, status, and pagination/filtering. |
| POST | `/events/cancel` | `{ shift_id, idempotency_key }` | `{ duplicate, gaps: Gap[] }` | `EventHandler.handle()` → `GapDetector.detect()` | Useful for Demo Mode or ingestion, not a normal dashboard read. It detects gaps but does not start recovery. |
| POST | `/events/no-show` | `{ shift_id, idempotency_key }` | `{ duplicate, gaps: Gap[] }` | Same as cancellation | Same limitation as cancellation. |
| POST | `/events/tick` | None | `{ settled, open_interrupts, closed_negotiations }` | `RecoveryService.recover()` and settlement handlers | Not a normal UI action. It is an operational scheduler/admin command and may execute queued Telegram sends. |
| POST | `/webhooks/messages` | Untyped provider payload | `{ accepted, duplicate, event_id }` | `TelegramChannel.normalise()` → `message_to_event()` → `EventHandler.handle()` | Provider ingress only. It validates/deduplicates a reply but does not advance negotiation workflow. |
| GET | `/interrupts` | None | Open `InterruptRecord[]` | `MemoryStore.list_open_interrupts()` | Partial. No resolved history, joined context, allowed decisions, pagination, or attention cost view. |
| POST | `/interrupts/{interrupt_id}/resolve` | `{ decision: string }` | `{ resolved, status, decision }` | `InterruptService.resolve_once()` | Partial. The decision is unconstrained text; no actor/note/version is recorded. A Strands-linked interrupt returns 503 unless a resumer is configured. |
| GET | `/feed` | None | `LedgerEntry[]` in insertion order | `MemoryStore.list_ledger()` | Partial. Fields are valuable, but there is no cursor, limit, filtering, stable sort contract, or joined display context. |
| POST | `/pending/{pending_id}/cancel` | None | `{ cancelled, reason }` | `PendingEffectService.cancel()` | Partial. Safe/idempotent semantics exist, but there is no endpoint that lists pending effects. |

Current errors use a mixture of FastAPI validation responses and `HTTPException.detail` objects. A frontend contract should standardize `{ code, message, details?, request_id? }` without leaking provider exceptions.

## Domain and persistence inventory

| Object | Important fields and relationships | Lifecycle | Current storage | UI access today |
|---|---|---|---|---|
| `Organisation` | `id`, `name` | Static fixture | `MemoryStore.organisations` | None |
| `Site` | `id`, `organisation_id`, `name`, `travel_zone` | Static fixture | `MemoryStore.sites` | Only `site_id` appears on a shift; no site endpoint |
| `Shift` | `id`, organization/site IDs, start/end, `required_by_role` | Static fixture; staffing derived from assignments/gaps | `MemoryStore.shifts` | Raw list via `GET /shifts` |
| `Volunteer` | ID/display name, roles, active, age, background check, availability, travel zones, reliability counters, contact load, transport need, archetype | Mostly static fixture | `MemoryStore.volunteers` | None; tools can read one volunteer or rank candidates |
| `Assignment` | ID, shift, volunteer, role, confirmation time | Created atomically; duplicate returns existing; capacity can reject | `MemoryStore.assignments` | None |
| `Gap` | ID, shift, role, shortfall, status, detected time, source event | `DETECTED` plus a broad status enum; current code only creates/updates and marks `RESOLVED`/respects `FAILED` | `MemoryStore.gaps` | Returned only from cancellation/no-show requests |
| `CandidateScore` | Volunteer ID, score, weighted breakdown, eligibility flags/reasons | Computed on demand, not persisted | `CandidateRanker` return value | None; available only as an agent tool result |
| `NegotiationThread` | ID, shift, volunteer, Strands session ID, status, turn index, updated time | Open/awaiting → accepted, declined, escalated, or timed out | `MemoryStore.negotiations`; conversation state separately in `FileSessionManager` | None |
| `ContactRecord` | Volunteer, thread, direction, contact time | Model exists only | Not stored or updated | None |
| `PendingEffect` | ID/type, idempotency key, payload, settle time, status, timestamps, result | `PENDING → SETTLING → SETTLED/FAILED`, or `PENDING → CANCELLED` | `MemoryStore.pending` | Cancel by known ID only |
| `InterruptRecord` | ID/session/idempotency key, reason, optional Strands interrupt ID, status, timestamps, decision | `OPEN → RESOLVING → RESOLVED`; failed resume releases to `OPEN` | `MemoryStore.interrupts` | Open list and resolve command |
| `AttentionBudget` | ID, allowance, spent, overrides, decision history | Created lazily; spending is idempotent per decision ID | `MemoryStore.budgets` | None |
| `LedgerEntry` | Timestamp, category/decision, event/gap IDs, route, EV data, budget snapshot, reason, details | Append-only logical record with ID dedupe | `MemoryStore.ledger` | Full unpaginated list via `/feed` |
| `ReplyClassification` | Intent, optional condition, confidence, safety reason | Computed; deterministic safety can override model output | Ephemeral | None |
| `RoutingDecision` | Route, EV score/threshold, reason, budget-spend/override flags | Computed; selected routes create ledger/pending/interrupt state | Partially embedded in interrupt reason and ledger | Indirectly through feed/interrupt payloads |
| `QuorumEvent` | ID, kind, idempotency key, occurred time, untyped payload | Processed once by idempotency key | Only idempotency marker and ledger entry persist | Event response gives ID; no event read API |
| Transport option | `{ available, option }` dictionary | Computed from the fixed synthetic tool/workflow branch | Not modeled or persisted | None |

All domain records are marked synthetic. `MemoryStore` is thread-safe inside one process but is not durable across API restarts and cannot support multiple API workers. `DynamoDBStore` demonstrates four conditional primitives but does not implement the `Store` protocol or the read/query surface needed by the app.

Several services read concrete `MemoryStore` dictionaries directly (`assignments`, `sites`, `interrupts`, `negotiations`). The current `Store` protocol declares only a small subset of operations. Before adding a durable store, the protocol needs to represent the real service boundary.

## Workflow mapping

### Cancellation and recovery

| Transition | Responsible code | Persisted state | Visible through API | Missing visibility/integration |
|---|---|---|---|---|
| Cancellation/no-show received | `quorum.api.app.handle_staffing()` or `CoreWorkflow.staffing_event()` | Processed idempotency key; event ledger entry | Event response and `/feed` | No event history endpoint or actor/source display |
| Gap detection | `EventHandler.handle()` → `GapDetector.detect()` | `Gap` per shift/role | New gaps only in mutation response | No gap list/detail; most Gap statuses are never driven |
| Eligibility/ranking | `CandidateRanker.eligibility()` and `.rank()` | None | None | Shift detail needs joined, on-demand ranked candidates and score explanations |
| Coordinator reasoning | `create_coordinator_agent()`; exercised by `scripts/run_agent_demo.py` | File-backed `org:riverside` Strands session | None | Not called by API workflow; no coordination-run status or safe trace |
| Negotiator reasoning | `create_negotiator_agent()` with `nego:{shift}:{volunteer}` | File-backed Strands session plus optional `NegotiationThread` metadata | None | No list/detail endpoint; session conversation is not normalized for safe UI display |
| Conditional reply | `ReplyClassifier`/`ModelReplyClassifier`; `CoreWorkflow.reply_and_assign()` | Thread may change; ledger only after assignment/escalation | None | Webhook does not map sender to volunteer/thread or invoke classification |
| Transport resolution | `find_transport_option` tool and a fixed branch in `reply_and_assign()` | None | None | Not a domain record; unavailable on shift/thread detail |
| Assignment | `MemoryStore.confirm_assignment()` | `Assignment`; thread becomes `ACCEPTED`; assignment ledger entry | None | No assignment endpoint or joined capacity counts |
| Gap resolution | `GapDetector.detect()` after confirmation | Existing nonterminal gap becomes `RESOLVED` | None | No `resolved_at`, resolution source, autonomous/human attribution, or gap endpoint |

The demo proves each component, but `scripts/run_agent_demo.py` deliberately coordinates them: it detects/ranks, invokes the Coordinator and Negotiator, observes model classifications, and replays those classifications through deterministic `CoreWorkflow`. That is execution evidence, not yet a continuously running product orchestration service.

### Injury or complaint

1. `ReplyClassifier` detects an injury/complaint deterministically; `classify_with_model()` never lets model output downgrade it.
2. `CoreWorkflow.reply_and_assign()` sends `OUT_OF_SCOPE` to `EscalationEngine.route()` with the safety category.
3. `EscalationEngine` treats recognized Layer-0 categories as RED and spends Attention Budget or records a safety override when the allowance is exhausted.
4. `InterruptService.create()` persists an idempotent `InterruptRecord`; the thread becomes `ESCALATED`; a RED ledger entry is appended.
5. `GET /interrupts` exposes the raw open record and `POST /interrupts/{id}/resolve` claims/resolves it once.

Missing product context includes the joined shift and volunteer, a concise explanation, allowed decisions, attention-cost presentation, who resolved it, a resolution note, and a reliable resume/outcome view. Telegram replies do not currently enter this path through the API.

## Minimal API additions

Use explicit Pydantic response models and either keep the existing paths or introduce a consistent `/api/v1` prefix before a public deployment. Do not duplicate routes solely for the frontend.

| Method/path | Purpose and response | Source of truth | Why the current API is insufficient |
|---|---|---|---|
| `GET /dashboard` | `DashboardSummary`: attention snapshot, open/active/resolved counts, open RED items, pending count, recent feed | Budgets, gaps, negotiations, interrupts, pending, ledger | Overview currently requires unavailable collections and many client-side joins |
| `GET /shifts` (enrich) | Paginated/filterable `ShiftSummary[]` with site, role fill, gaps, and status | Shifts + sites + assignments + gaps | Raw shifts contain requirements only |
| `GET /shifts/{shift_id}` | `ShiftDetail` with requirements, assignments, open gaps, ranked eligible candidates, threads, related pending/interrupt/feed references | Existing store plus on-demand `CandidateRanker` | No current entity endpoint can support the shift workspace |
| `GET /volunteers` | Safe, filterable `VolunteerSummary[]` | Volunteers + assignment/contact aggregates | Volunteers are not exposed |
| `GET /volunteers/{volunteer_id}` | Safe profile, availability, current assignments, load, and eligibility facts; omit exact age unless policy requires it | Volunteer + shifts + assignments | No current endpoint; raw domain fields are broader than UI needs |
| `GET /pending` | Filterable `PendingEffectView[]`, defaulting to active | Pending effects | The UI can cancel only if it somehow already knows an ID |
| `GET /attention-budget` | `AttentionBudgetView` with allowance/spent/remaining/overrides and period semantics | AttentionBudget | Budget is central to the product but invisible |
| `GET /interrupts` (enrich) | Filter by status; return `InterruptView` with safe joined context and allowed actions | Interrupts + shifts/volunteers/threads + ledger | Current response is raw and open-only |
| `GET /interrupts/{interrupt_id}` | Full Human Decision Center record | Same sources | List payload alone should not carry every evidence field |
| `POST /interrupts/{id}/resolve` (harden) | Enum action, optional note, expected status/version; return updated `InterruptView` | InterruptService and audit ledger | Arbitrary text, no actor/note/version, incomplete Strands resume wiring |
| `GET /feed` (enrich) | Cursor pagination and filters by route/category/shift/time; `DecisionFeedPage` | Ledger | Current unbounded list will not scale and lacks display joins |
| `GET /settings` | Non-secret effective operational settings and which values are editable | Settings/config store | Environment config is not safely inspectable in UI |

`GET /analytics` should wait for event instrumentation and durable history. A dashboard can compute current snapshots, but average resolution time, autonomous fill rate, and false-interrupt rate are not trustworthy today.

The backend also needs an orchestration service, not just more routes. Event ingestion should enqueue or invoke a deterministic recovery lifecycle that updates existing `Gap.status` values and calls the agents through controlled tools/hooks. The UI should observe that lifecycle; it should not orchestrate it. For V1, an explicit `POST /gaps/{id}/recover` may support Demo Mode/manual retry, but normal cancellation processing should start recovery server-side.

## Product-critical backend gaps

1. **API orchestration:** core/demo pieces are not an API-connected recovery loop.
2. **Durable domain state:** API state resets on restart; multiple workers would diverge.
3. **Typed read contracts:** OpenAPI responses are mostly generic dictionaries.
4. **Entity read surface:** no gaps, assignments, volunteers, negotiations, pending list, budget, or joined detail APIs.
5. **Authentication and authorization:** every mutation is currently unauthenticated; webhooks are not signature/secret validated in this module.
6. **Lifecycle observability:** gaps lack resolution timestamps/provenance; broad status enums are mostly unused.
7. **Reply correlation:** Telegram sender IDs are not mapped to volunteer/thread state, and reply events do not advance workflow.
8. **Interrupt semantics:** decisions are free text; actor, note, allowed actions, and resume outcome are missing.
9. **Contact accounting:** `ContactRecord` is not stored, and weekly/concurrent counters are not updated by send/close paths.
10. **Portability boundary:** services depend on concrete `MemoryStore` internals; the DynamoDB adapter is only a conditional-write spike.
11. **API operations:** no CORS/proxy decision, pagination, request IDs, structured logging, or standardized error envelope.
12. **Analytics:** no durable event history, gap `resolved_at`, decision actor, or explicit autonomous-versus-human outcome attribution.
13. **Gap semantics:** `Gap.shortfall` must remain greater than zero, so a resolved gap retains its previous positive shortfall. Terminal gaps are also never reopened, meaning a later real shortfall for the same shift/role would need a new lifecycle/identity rule.
14. **Conditional acceptance:** `CoreWorkflow.reply_and_assign()` resolves the known `transport` condition, but any other `ACCEPT_IF` condition can currently continue to assignment without an explicit condition-resolution record.
15. **Final assignment guard:** the agent `confirm_assignment` tool checks role membership and background check but does not re-run all `CandidateRanker.eligibility()` rules (age, availability, contact caps, conflicts, and travel). Final confirmation should call one centralized authoritative eligibility policy.
16. **Configuration wiring:** `Settings.attention_budget` exists, but the API/CoreWorkflow construction shown here does not pass it into `EscalationEngine`/`RoutingHook`; the effective allowance remains the service default unless a caller wires it explicitly.
