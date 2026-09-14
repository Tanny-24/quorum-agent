# QUORUM Product UI Specification

## Product position

QUORUM should look and behave like mission control for community coordination, not a chatbot. The primary question on every screen is: **what is happening, what is QUORUM handling, and what genuinely needs a human?**

The proposed Next.js, TypeScript, Tailwind CSS, and shadcn/ui stack fits the current FastAPI backend. V1 should use REST, schema-generated or hand-validated TypeScript types, and simple polling. No frontend package or application is created during this audit.

## Information architecture

Use one desktop sidebar with grouped navigation rather than eight visually equal links:

1. **Overview**
2. **Operations**
   - Shifts
   - Volunteers
3. **Attention**
   - Human Decisions (the product label for Interrupts)
   - Pending Effects
4. **Observability**
   - Decision Feed
   - Analytics
5. **Administration**
   - Settings

All eight requested destinations are justified, with two qualifications:

- “Interrupts” should be presented as **Human Decisions**. “Interrupt” is an implementation concept; the user task is deciding safely.
- Analytics should ship after durable instrumentation. Until then, the Overview may show honest current-state counts, while the Analytics page is withheld or clearly labeled as limited operational insights.

The global app shell contains the organization switcher/name (one organization in V1), environment badge (`Synthetic Demo`), API health, last refresh time, Demo Mode entry, and a notification badge equal to open RED decisions. Do not add a chat composer.

## Overview

**Purpose:** answer “what needs me, what is the agent doing, and what did it save me from?” in under ten seconds.

**Primary user:** volunteer coordinator or operations lead.

**Key information and components:**

- Attention Budget card: allowance, spent, remaining, overrides. Do not label it “this week” until a budget period exists in backend state.
- Operational summary cards: open gaps, active negotiations, pending effects, open human decisions.
- “Needs Your Attention” queue: top RED items with reason, shift/site context, age, and one clear Review action.
- “Currently Resolving” list: gaps in analyzing/searching/contacting/awaiting states. This remains empty until the backend drives those statuses.
- Recent Agent Activity: latest decision-feed items with route chip, plain-language decision, reason, and time.
- Autonomous outcome card only after resolution provenance exists. Today, “resolved gaps” can be counted, but “resolved without humans” cannot be attributed reliably.

**Actions:** review a RED decision, open a shift, inspect a feed item, manually refresh, enter Demo Mode.

**Backend data:** `DashboardSummary` from budgets, gaps, negotiations, pending, interrupts, assignments, and ledger.

**Existing endpoints:** `/interrupts` and `/feed` provide partial raw data.

**Missing endpoint:** `GET /dashboard`; optionally link to enriched collection endpoints.

**States:**

- Empty: “Operations are clear—no staffing gaps or human decisions.” Keep recent activity visible if it exists.
- Loading: retain card geometry with subtle skeletons; never show zero as a temporary value.
- Error: show which section is stale, last successful refresh, and a Retry action. Other successfully loaded sections remain usable.

## Shifts

**Purpose:** provide the operational workspace for staffing coverage and recovery progress.

**Primary user:** coordinator managing the current roster.

**List view:**

- Date grouping and filters for date, site, role, and status.
- Columns/cards: start time, site, required roles, assigned/required capacity, gap status, recovery status, next action.
- Default sort: unresolved/soonest first, then start time.
- Status is derived server-side from time, role fill, gaps, and negotiation state.

**Shift detail:**

- Header with site, start/end, status, and synthetic badge.
- Role-capacity bars showing assigned versus required.
- Open/resolved gaps with shortfall and lifecycle.
- Confirmed volunteers, joined by safe display name and role.
- Ranked candidates with score explanation, eligibility already decided by backend, contact load, and relevant transport constraint.
- Coordination timeline showing event, ranking, outreach, reply, assignment, and resolution references.
- Related negotiations, pending effects, RED decisions, and feed items.

**Actions:** inspect candidate explanation, review related decision, cancel a still-pending effect, run a synthetic Demo Mode scenario. Normal production UI should not manually “confirm” an assignment around backend capacity checks.

**Backend data:** joined shift/site/assignment/gap/candidate/thread/pending/interrupt/ledger data.

**Existing endpoint:** `GET /shifts` supplies raw shifts only.

**Missing endpoints:** enriched `GET /shifts`, `GET /shifts/{id}`. Candidate scores should be computed by `CandidateRanker`, never in the browser.

**States:**

- Empty list: “No shifts match these filters.”
- Empty detail section: distinguish “fully staffed,” “no outreach started,” and “no pending action.”
- Loading: table rows and fixed detail-section skeletons.
- Error: 404 returns to Shifts; partial section failures identify stale data and allow retry.

## Volunteers

**Purpose:** show operational eligibility, availability, assignments, and contact load without becoming a sensitive personnel database.

**Primary user:** coordinator planning outreach.

**List:** display name, active state, roles, next available shifts or availability count, current assignments, weekly contact count/cap, concurrent asks/cap, and transport constraint. Support filters for role, active state, availability, and contact capacity.

**Detail:** safe profile summary, roles, availability, travel feasibility, assignments, recent coordination references, and backend-produced eligibility explanations for a selected shift.

Do not expose exact age, raw Telegram identifiers, message payloads, model prompts, or unnecessary background-check details. Prefer a backend field such as `driver_policy_eligible` or contextual rejection reason over sending exact age. Treat reliability and acceptance history as an explainability input, not a public performance score; show it only to authorized coordinators with context.

**Actions:** open an assignment/shift, select a shift to inspect eligibility, view related coordination activity. Direct contact should remain a backend policy-checked action and is not required in the first UI.

**Backend data:** volunteers joined to assignments, shifts, and maintained contact records/counters.

**Existing endpoint:** none.

**Missing endpoints:** `GET /volunteers`, `GET /volunteers/{id}`.

**States:**

- Empty: filter-aware message; for a new organization, explain that roster import is not implemented.
- Loading: table skeleton preserving filters.
- Error: retain selected filters and retry without exposing private backend errors.

## Human Decisions

**Purpose:** make every RED case understandable and safely resolvable.

**Primary user:** an authorized coordinator or duty manager.

**Queue:** reason, safety category, created time/age, shift/site, volunteer display reference when appropriate, attention-budget effect, and status. Open items come first; resolved history is a filter, not a separate product.

**Decision detail:**

- “Why QUORUM stopped” in plain language.
- Structured evidence: classification, safety reason, routing reason, relevant event/shift/thread facts, and model/tool trace only when sanitized.
- Explicit boundary: “No action was taken pending your decision.”
- Allowed resolution actions supplied by backend, such as Approve, Veto, Acknowledge, or Escalate externally. Do not infer action names from arbitrary payloads.
- Optional decision note, actor identity, timestamp, and eventual resume/outcome state.
- Attention Budget context, including whether Layer-0 overrode an exhausted budget.

**Actions:** submit exactly one allowed decision, retry a failed resume, return to related shift. Use a confirmation dialog for consequential approvals, with idempotent retry behavior.

**Backend data:** enriched interrupt, joined context, allowed actions, version/expected status, and decision audit fields.

**Existing endpoints:** `GET /interrupts`, `POST /interrupts/{id}/resolve`.

**Missing/improved endpoints:** status filtering, `GET /interrupts/{id}`, typed resolution enum/note/version, configured Strands resumer, and outcome view.

**States:**

- Empty: “No decisions need your attention.” Emphasize autonomous work elsewhere.
- Loading: prioritize queue skeleton and preserve selected item.
- Error: resolution failures keep the item open, preserve the draft note locally, and show a safe retry message. A 409-style already-resolved outcome should refetch rather than appear as failure.

## Pending Effects

**Purpose:** expose YELLOW actions during their cancellable settlement window.

**Primary user:** coordinator monitoring or stopping reversible outreach/actions.

**Table:** effect type, plain-language action, created time, settle time/countdown, state, related shift/thread/volunteer, routing reason, and result summary. Use exact lifecycle values: `PENDING`, `SETTLING`, `SETTLED`, `CANCELLED`, `FAILED`.

**Actions:** cancel only while `PENDING`; inspect related entity; retry is not offered until backend defines safe retry semantics.

**Backend data:** safe PendingEffect projections. Raw payload/result dictionaries must be sanitized and converted into display fields server-side.

**Existing endpoint:** `POST /pending/{id}/cancel` only.

**Missing endpoint:** `GET /pending?status=PENDING`. A separate detail endpoint is optional if the list view contains safe context.

**States:**

- Empty: “No actions are waiting to settle.”
- Loading: rows with stable countdown placeholders; synchronize against server time.
- Error: failed cancellation refetches the item because settlement may have won the race.

## Decision Feed

**Purpose:** provide an explainable, append-only operations timeline.

**Primary user:** coordinator, reviewer, or portfolio evaluator.

**Rows:** route chip, category, decision in human-readable text, reason, timestamp, linked shift/gap/interrupt, EV score/threshold when relevant, and attention-budget change. Technical IDs belong in a collapsible details panel.

**Filters:** route, category, shift, time range, and “attention spent.” Default newest first. Do not render raw `details` dictionaries directly.

**Actions:** open related shift/decision, copy a sanitized event reference, load older items.

**Backend data:** ledger with server-side display mapping and cursor pagination.

**Existing endpoint:** `GET /feed`.

**Required improvements:** stable descending order, cursor/limit, filters, joined display references, and typed response.

**States:**

- Empty: “No decisions have been recorded in this demo session.”
- Loading: incremental rows; do not clear existing history during refresh.
- Error: show last successful timestamp and allow retry/load older independently.

## Analytics

**Purpose:** quantify how QUORUM protects human attention and improves recovery, using auditable metrics only.

**Primary user:** operations lead, product evaluator, or nonprofit manager.

**Currently derivable as a present-state snapshot, once read APIs exist:**

- open and resolved gap counts;
- current open interrupt count;
- Attention Budget allowance/spent/overrides;
- pending-effect counts by state;
- assignment count and current role fill;
- ledger counts by route/category/decision;
- current seeded contact-load fields.

These are not durable time-series metrics in the current in-memory API.

**Requires new instrumentation:**

- autonomous fill rate and gaps resolved without humans;
- average and percentile resolution time;
- interruptions per period and false/unnecessary interrupt rate;
- time spent in each gap/negotiation status;
- outreach response time and acceptance conversion;
- contact load over time;
- PendingEffect cancellation/settlement/failure rates;
- RED escalation outcomes.

Required fields include `gap.resolved_at`, resolution actor/mode, status-transition events, period-scoped budgets, decision actor/outcome, and maintained contact history.

**Actions:** choose a period and site, inspect metric definition, drill into the filtered feed. No CSV export in V1 unless users need it.

**Existing endpoint:** none; `/feed` is insufficient for accurate longitudinal metrics.

**Missing endpoint:** `GET /analytics?from=&to=&site_id=` only after durable event instrumentation.

**States:**

- Empty: explain that the chosen period has no completed operations.
- Loading: keep metric definitions available.
- Error: never fall back to invented values; label stale calculation time.

## Settings

**Purpose:** expose safe operational policy configuration and system status.

**Primary user:** organization administrator.

**Read-only V1 sections:** environment, organization/timezone, effective Attention Budget allowance, contact cap, quiet hours, maximum concurrent asks, settlement windows, model provider/model ID, Telegram configured/not-configured, and persistence mode.

Never return Gemini or Telegram secrets, provider URLs containing tokens, AWS credentials, or raw environment variables.

**Editable later:** period-scoped Attention Budget, timezone/quiet hours, contact limits, and settlement windows, after authentication, validation, persistence, audit logging, and safe reload semantics exist. Model provider changes should remain deployment administration, not a casual dashboard toggle.

**Actions:** initially copy safe diagnostic summary and verify health. Later, save validated organization policy with explicit before/after audit records.

**Existing endpoint:** none. Current values come from environment configuration and module constants.

**Missing endpoints:** safe `GET /settings`; defer `PATCH /settings` until a real config store and authorization exist.

**States:**

- Empty: not applicable; show “not configured” per integration.
- Loading: section skeletons.
- Error: settings remain non-editable and show a retry action.

## Frontend data contracts

The labels indicate provenance, not implementation status of an HTTP endpoint.

```ts
type RouteClass = "GREEN" | "YELLOW" | "RED" | "SILENT/DEFER"; // EXISTS TODAY
type GapStatus =
  | "DETECTED" | "ANALYZING" | "SEARCHING" | "CONTACTING" | "AWAITING"
  | "ESCALATION_REQUIRED" | "WAITING_FOR_HUMAN" | "RESUMING"
  | "DEFERRED" | "RESOLVED" | "FAILED"; // EXISTS TODAY; most transitions unused

interface AttentionBudgetView { // DERIVED FROM EXISTING DATA
  id: string;
  allowance: number;
  spent: number;
  remaining: number;
  overrides: number;
  period: { startsAt: string; endsAt: string } | null; // REQUIRES BACKEND ADDITION
}

interface DashboardSummary { // DERIVED; REQUIRES GET /dashboard
  generatedAt: string;
  attention: AttentionBudgetView;
  counts: {
    openGaps: number;
    activeNegotiations: number;
    pendingEffects: number;
    openHumanDecisions: number;
    resolvedGaps: number;
    autonomouslyResolved: number | null; // null until provenance exists
  };
  needsAttention: InterruptView[];
  activeRecoveries: GapSummary[];
  recentActivity: DecisionFeedItem[];
}

interface RoleCoverage { // DERIVED FROM Shift + Assignment + Gap
  role: "driver" | "sorter";
  required: number;
  assigned: number;
  shortfall: number;
}

interface ShiftSummary { // DERIVED; current GET /shifts is insufficient
  id: string;
  site: { id: string; name: string };
  startsAt: string;
  endsAt: string;
  coverage: RoleCoverage[];
  status: "UPCOMING" | "AT_RISK" | "RECOVERING" | "STAFFED" | "COMPLETED";
  activeGapCount: number;
}

interface GapSummary { // EXISTS TODAY plus display joins
  id: string;
  shiftId: string;
  role: "driver" | "sorter";
  shortfall: number;
  status: GapStatus;
  detectedAt: string;
  resolvedAt: string | null; // REQUIRES BACKEND ADDITION
  resolutionMode: "AUTONOMOUS" | "HUMAN_ASSISTED" | null; // REQUIRES BACKEND ADDITION
}

interface CandidateView { // DERIVED from CandidateScore + safe Volunteer projection
  volunteerId: string;
  displayName: string;
  score: number;
  breakdown: Record<string, number>;
  constraints: string[];
  contactLoad: { weekly: number; concurrent: number };
}

interface ShiftDetail extends ShiftSummary { // DERIVED; REQUIRES GET /shifts/{id}
  organizationId: string;
  gaps: GapSummary[];
  assignments: AssignmentView[];
  rankedCandidates: Record<"driver" | "sorter", CandidateView[]>;
  negotiations: NegotiationSummary[];
  pendingEffectIds: string[];
  interruptIds: string[];
}

interface VolunteerSummary { // SAFE PROJECTION; REQUIRES BACKEND ENDPOINT
  id: string;
  displayName: string;
  roles: Array<"driver" | "sorter">;
  active: boolean;
  availableShiftCount: number;
  weeklyContactCount: number;
  weeklyContactCap: number;
  concurrentAsks: number;
  concurrentAskCap: number;
  needsTransport: boolean;
}

interface AssignmentView { // EXISTS TODAY plus volunteer display join
  id: string;
  shiftId: string;
  volunteer: { id: string; displayName: string };
  role: "driver" | "sorter";
  confirmedAt: string;
}

interface NegotiationSummary { // EXISTS TODAY; no safe transcript model exists
  id: string;
  shiftId: string;
  volunteerId: string;
  status: "OPEN" | "AWAITING_REPLY" | "ACCEPTED" | "DECLINED" | "ESCALATED" | "TIMED_OUT";
  turnIndex: number;
  updatedAt: string;
}

interface InterruptView { // EXISTS TODAY plus required joins/action metadata
  id: string;
  status: "OPEN" | "RESOLVING" | "RESOLVED";
  createdAt: string;
  resolvedAt: string | null;
  decision: string | null;
  safetyReason: string | null;
  routingReason: string;
  attention: { spent: boolean; override: boolean };
  context: { shiftId?: string; shiftLabel?: string; volunteerId?: string; volunteerName?: string };
  evidence: Array<{ label: string; value: string }>;
  allowedActions: string[]; // REQUIRES BACKEND ADDITION
  version: number; // REQUIRES BACKEND ADDITION
}

interface PendingEffectView { // EXISTS TODAY plus safe display projection
  id: string;
  effectType: string;
  description: string;
  status: "PENDING" | "SETTLING" | "SETTLED" | "CANCELLED" | "FAILED";
  createdAt: string;
  settleAt: string;
  updatedAt: string;
  cancellable: boolean;
  context: { shiftId?: string; threadId?: string; volunteerId?: string };
  resultSummary: string | null;
}

interface DecisionFeedItem { // EXISTS TODAY plus display projection/pagination
  id: string;
  timestamp: string;
  route: RouteClass | null;
  category: string;
  decision: string;
  reason: string | null;
  explanation: string;
  context: { eventId?: string; gapId?: string; shiftId?: string; interruptId?: string };
  ev: { score: number; threshold: number } | null;
  budget: { spent?: number; allowance?: number; overrides?: number } | null;
}
```

## Demo Mode

Demo Mode must be unmistakably synthetic, resettable, isolated from production credentials, and safe to repeat.

### UX

- A top-bar `Demo Mode` button opens a scenario drawer.
- A persistent `Synthetic Demo` badge and banner identify the data.
- `Reset Demo Data` requires confirmation and explains that only the current demo workspace is reset.
- Scenario cards show initial condition, expected autonomous/human boundary, approximate duration, and Run action.
- While running, a stepper follows persisted backend state: Event → Gap → Ranking → Outreach/Reply → Assignment or Human Decision.
- Completion links to the affected shift, Human Decision, and filtered Decision Feed rather than displaying a scripted success toast alone.

### Scenarios

- **A — Autonomous recovery:** cancellation, eligible candidate, YELLOW outreach settlement, acceptance, capacity-safe assignment, resolved gap, zero RED decisions.
- **B — Transport condition:** no-show/cancellation, `ACCEPT_IF`, deterministic transport option, capacity-safe assignment, resolved gap.
- **C — Safety escalation:** injury/complaint, deterministic `OUT_OF_SCOPE`, Layer-0 RED, persisted human decision; the scenario pauses until the user resolves it.

### Backend contract

- `POST /demo/reset` creates a fresh seeded demo workspace and returns its generation ID and dashboard summary.
- `POST /demo/scenarios/{scenario}` accepts an idempotency key and returns a run ID plus affected entity IDs.
- Normal read endpoints reflect the scenario state; no separate fake UI data store is allowed.
- Run deterministic scenarios without Telegram. If a portfolio deployment offers live Gemini, make it a server-controlled optional mode and label whether a run used deterministic or live-model classification. Never pretend simulated output is live inference.
- Isolate demo workspaces by session or tenant key with a TTL. Do not use a process-global mutable singleton once multiple visitors are supported.

## Real-time strategy

REST plus polling is sufficient for V1:

| View | Polling | Notes |
|---|---|---|
| Overview | 10 seconds; 3–5 seconds during an active demo | Pause when tab is hidden; refetch on focus |
| Human Decisions | 5 seconds | Immediately refetch after resolution |
| Pending Effects | 5 seconds | Use server timestamps for countdown; refetch after cancel |
| Shift detail | 10 seconds; 3 seconds while recovering | Refetch after related actions |
| Decision Feed | 5 seconds using newest cursor | Append new items; never reload the entire feed |
| Volunteers | 30–60 seconds or on focus | Mostly stable reference data |
| Analytics | 60 seconds or manual refresh | Calculated view, not operational control |
| Settings | No polling | Refetch only after navigation/save |

Use request cancellation and deduplication so route changes do not apply stale responses. Display `generatedAt`/last-updated time and stale indicators.

WebSockets or server-sent events become justified only if QUORUM gains concurrent operators, long-running recoveries requiring sub-second transitions, provider token streaming that users genuinely need, or polling load that is measured to be wasteful. Agent prose streaming alone is not a product requirement.

## Frontend/backend boundary

The frontend owns layout, filtering of already-returned collections, navigation, optimistic visual feedback, form validation for usability, polling, and accessible presentation.

The backend remains authoritative for:

- staffing arithmetic and gap status;
- volunteer eligibility and rank scores;
- safety classification and Gemini interaction;
- route selection and thresholds;
- Attention Budget spending/overrides;
- contact caps, quiet hours, and policy;
- settlement state transitions;
- idempotency, assignment capacity, and race resolution;
- allowed human decisions and interrupt resume;
- analytics definitions and aggregation.

The frontend may optimistically disable a button but must render the returned backend state. A cancellation/settlement race, duplicate event, already-filled assignment, or already-resolved interrupt is a normal state transition, not a client-calculated error.

## Visual direction

### Layout

- Light neutral canvas (`slate-50`) with white surfaces and restrained borders.
- Desktop: fixed 248px sidebar, 64px top bar, fluid content up to approximately 1440px.
- Use a 12-column content grid; summary cards span three columns, active operations eight, attention rail four.
- Keep tables for dense operational data and cards for summaries/decisions. Avoid card grids for every row.

### Color and status

- Primary navy: `#0F172A`; action blue: `#2563EB`.
- GREEN: dark green text/icon on pale green surface.
- YELLOW: amber text/icon on pale amber surface.
- RED: strong red reserved for decisions and safety, not decorative emphasis.
- SILENT/DEFER: slate/indigo neutral treatment.
- Every state includes text and an icon; color is never the only signal.

### Components

- Rounded cards at 10–12px radius, subtle shadow only for raised interactive surfaces.
- Compact route/status chips, always using exact human labels.
- Attention Budget uses a numeric fraction and progress bar, with overrides shown separately—not a gamified score.
- Human Decision cards use a clear reason, evidence hierarchy, and one primary action.
- Timeline rows align route, action, explanation, context, and time; technical JSON is collapsed.

### Typography

- Use Inter or a high-quality system sans-serif.
- 14–16px body, tabular numerals for capacities/time, compact uppercase only for small status labels.
- Prefer sentence case and direct operational language.

### Responsive behavior

- Below 1024px, collapse the sidebar to a drawer and stack the Overview attention rail beneath active operations.
- Below 768px, turn wide tables into deliberate summary rows with detail drawers; do not rely on horizontal scrolling for primary actions.
- Keep Human Decision actions sticky within the mobile detail view.
- Meet keyboard navigation, visible focus, semantic heading, contrast, reduced-motion, and screen-reader status requirements.

