# QUORUM Interview Guide

Use this guide to learn the project in simple layers. You do not need to memorize every file. First understand the problem, authority boundary, and Scenario B/C stories. Then use [code-walkthrough.md](code-walkthrough.md) to learn the implementation order.

## 30-second pitch

QUORUM is an attention-aware volunteer coordination agent for a synthetic food bank. It detects staffing gaps, ranks eligible replacements, handles ordinary volunteer replies, and updates assignments. The key design is “LLM proposes; deterministic code disposes”: Strands agents can understand language and choose tools, but Python services own eligibility, ranking, capacity, safety, idempotency, and whether a human must be interrupted. A responsive Next.js UI makes the full workflow visible.

## 2-minute project explanation

Volunteer coordinators lose time when one cancellation creates many small decisions. QUORUM turns that recovery into an observable workflow. FastAPI accepts an idempotent event. `GapDetector` calculates shortages. `CandidateRanker` filters policy violations and returns an explainable score. A Coordinator can use those results, while a volunteer-scoped Negotiator interprets a reply.

If the reply is ordinary, deterministic code may resolve it. In Scenario B, “I can do it, but I need a ride” becomes `ACCEPT_IF` with condition `transport`; a shared transport service resolves that condition, an atomic guard confirms the assignment, and the gap is recalculated. No person is interrupted.

If the text mentions injury or complaint, Layer-0 safety overrides model output. QUORUM creates a RED `InterruptRecord`, spends one item from the Attention Budget, and waits in the Human Decision Center. Pending Effects represent YELLOW actions that can still be cancelled before settlement. The Decision Ledger explains what happened.

The agent layer uses Strands with one model factory for Amazon Bedrock or Gemini. The reliable interview demo is deterministic and calls neither provider, avoiding quota, latency, and cost while still exercising the real coordination services.

## Problem Statement

A coordinator should not have to recompute eligibility, contact limits, availability, transport, and coverage after every cancellation. But an LLM should not autonomously decide safety, fairness, or consequential resource allocation. QUORUM aims to automate the repetitive middle while preserving human judgment for genuine risk.

## End-to-End Scenario

Explain Scenario B first:

```text
VOLUNTEER_CANCELLED
  → idempotent event accepted
  → role gaps calculated
  → eligible candidates ranked
  → scoped negotiation opened
  → “I need a ride” classified as ACCEPT_IF:transport
  → synthetic transport option resolved
  → assignment capacity guard succeeds
  → gaps recalculated
  → shift fully staffed
  → Decision Ledger records the path
  → Attention Budget unchanged
```

Then contrast Scenario C: injury/complaint is `OUT_OF_SCOPE`, Layer-0 routes RED, and the workflow waits for a persisted human decision before any consequential action.

## Architecture From Zero

Start with four layers:

1. **UI:** Next.js operations pages.
2. **Product API:** typed FastAPI routes and safe read projections.
3. **Orchestration and agents:** a recovery service plus Coordinator/Negotiator Strands agents.
4. **Deterministic authority:** events, gaps, eligibility, ranking, policy, routing, budget, capacity, settlement, interrupts, and ledger.

Amazon Bedrock and Gemini sit behind one model factory. They do not sit underneath the database or policy layer; they cannot bypass it.

## Main Modules

- `quorum/domain/models.py`: typed states and enums.
- `quorum/persistence/memory.py`: atomic local transitions.
- `quorum/services/gap_detector.py`: staffing arithmetic.
- `quorum/services/candidate_ranker.py`: eligibility and explainable scores.
- `quorum/agents/classifier.py`: reply intent with deterministic safety precedence.
- `quorum/services/escalation.py`: routes and Attention Budget.
- `quorum/services/pending_effects.py`: YELLOW settlement lifecycle.
- `quorum/services/interrupts.py`: RED human-decision lifecycle.
- `quorum/services/workflow.py`: deterministic application workflow.
- `quorum/services/orchestration.py`: Demo A/B/C run coordination.
- `quorum/agents/models.py`: Bedrock/Gemini factory.
- `quorum/api`: typed product boundary.
- `web/src`: operator interface.
- `scripts/run_evaluation.py`: synthetic outcome benchmark.

## Why Strands?

Strands provides an agent abstraction, model interface, tools, hooks, sessions, structured output, and interrupts without tying role code to one provider. QUORUM uses those capabilities but keeps business authority in normal Python services.

## Why Amazon Bedrock?

Bedrock fits an AWS-centered agent project and gives Strands a native model path through boto3 and the Converse API. Credentials come from the standard AWS chain. The configured lightweight Nova profile keeps small tool-oriented validation economical. Bedrock is a provider, not the system of record.

## Why Gemini is retained?

Gemini was previously integrated and live-validated. Keeping it proves the architecture is provider-neutral and provides an alternate model path. The same Coordinator and Negotiator factories work with either provider.

## Why two agents?

Organization-level recovery and one volunteer conversation have different context and permissions. Separating them reduces prompt scope, prevents conversation leakage, and makes session identity clear.

## Why not one giant agent?

A giant agent would mix planning, private conversation context, provider setup, safety, and state changes. That makes testing and authority hard to explain. Two narrow roles plus deterministic services are easier to reason about.

## Coordinator vs Negotiator

- **Coordinator:** organization-scoped; reads shifts, gaps, and rankings; plans recovery.
- **Negotiator:** one shift and volunteer; interprets replies and asks concise questions.

Neither owns capacity, eligibility, routing, or safety.

## Why deterministic ranking?

The input factors and weights are visible, stable, and testable. An interviewer can inspect why a candidate ranked first. It also prevents the model from inventing a volunteer or using an undeclared criterion.

## Why not ask the LLM who to select?

Selection affects people and operational coverage. An LLM answer may vary and may contain hidden assumptions. QUORUM lets the model request a ranked list, while code validates eligibility and ordering.

## Attention Budget

The budget limits ordinary RED interruptions. As it is spent, the threshold rises. Layer-0 safety never disappears; after the allowance, it is recorded as an override. Repeating one decision cannot spend twice.

## GREEN / YELLOW / RED / SILENT

- GREEN executes a reversible low-risk action.
- YELLOW persists a delay so a person can cancel before settlement.
- RED persists a case and waits for explicit judgment.
- SILENT/DEFER means doing nothing is the correct action for now.

## PendingEffect

A `PendingEffect` stores effect type, idempotency key, safe payload, settlement time, status, and result. The service uses guarded transitions so cancellation and settlement cannot both win.

## Human Decision / Interrupt

An `InterruptRecord` is a durable local representation of why execution paused. It includes safe evidence, status, version, allowed actions, and resolution outcome. The API resolves it once and records the result.

## Settlement Window

A settlement window makes an action reversible for a period. QUORUM stores `settle_at`; it does not use a long sleep as business state. A separate tick/settlement call claims due work.

## Idempotency

Events, effects, recovery runs, budget decisions, assignments, and human resolutions use stable logical keys or guarded states. Repeating a request returns the existing result instead of causing a second consequence.

## Assignment Concurrency

`MemoryStore.confirm_assignment` holds one lock while checking duplicate assignments, counting filled seats, and inserting. In distributed storage, the same guarantee would need a conditional write or transaction.

## Prompt Injection Defense

Volunteer text is data, not instruction. Known injection-shaped phrases classify as low-confidence `UNCLEAR`, and model prompts repeat the boundary. Even if a model proposed a tool, routing, eligibility, and capacity still run outside the prompt.

## Safety Layer-0

Injury, medical, safeguarding, harassment, discrimination, complaints, service-allocation conflicts, permanent removal, money/employment, contracts, and unsafe-minor cases bypass the normal score and route RED.

## Demo Mode

`deterministic_demo` is not a fake UI. It triggers real events, gaps, ranking, pending effects, reply classification, transport, assignments, routing, budget, interrupts, and ledger records. It intentionally omits external model inference so the full system is reliable in an interview.

## Evaluation

The runner executes 20 fixed synthetic cases against the same deterministic services. Current output is 20/20 expected outcomes, four critical safety cases with zero misses, and zero incorrect autonomous actions. These numbers are regression evidence only, not real-world performance.

## What happens when model API fails?

Provider-backed turns fail closed; QUORUM does not invent success. The deterministic Demo Mode still works because it has no model dependency. A production version would add bounded retries, circuit breaking, and an operator-visible degraded mode.

## What happens on process restart?

The in-memory operational workspace resets. Local Strands sessions use `FileSessionManager`, and a separate durability spike proves interrupt-resume mechanics, but the product API is not wired to a production database.

## What remains in-memory?

Organizations, sites, volunteers, shifts, assignments, gaps, negotiations, pending effects, interrupts, budgets, ledger entries, executed-effect keys, and recovery runs.

## Current limitations

Local-only, synthetic data, no authentication, no production deployment, no durable product database, synchronous demo runs, and no trustworthy historical contact-load view.

## What would you change for production?

Add authenticated tenant boundaries, durable transactional storage, least-privilege IAM, encrypted configuration, asynchronous workers, retries, rate limits, observability, migrations, backups, audit retention, privacy review, and stakeholder-validated policy/fairness testing.

## Why no deployment?

The portfolio scope intentionally prioritized architecture, safety boundaries, complete local workflows, evaluation, and explainability. It does not pretend to be production SaaS.

## Likely interviewer questions

### 1. What is the most important design decision?

**Short answer:** The LLM never owns operational authority.

**Deeper follow-up:** Models interpret language and select tools, but deterministic code validates eligibility, ranking, capacity, safety, routing, budget, and idempotency before a consequence can occur.

### 2. Why call it attention-aware?

**Short answer:** Human interruption is modeled as a limited resource.

**Deeper follow-up:** The Attention Budget records actual RED interruptions and changes thresholds as allowance is consumed, while Layer-0 safety still reaches a human through recorded overrides.

### 3. Is deterministic Demo Mode fake AI?

**Short answer:** No; it removes external inference, not the workflow.

**Deeper follow-up:** The demo invokes real backend services and state transitions. It uses the deterministic classifier for controlled replies so interviews are not dependent on quota or network variance.

### 4. Why use an LLM at all?

**Short answer:** Natural-language replies and negotiation are variable.

**Deeper follow-up:** A model is useful for understanding wording, asking concise questions, and choosing tools. Arithmetic, policy, and consequential decisions are better expressed as deterministic code.

### 5. Why Strands instead of calling a model SDK directly?

**Short answer:** It provides provider-neutral agents, tools, hooks, sessions, structured output, and interrupts.

**Deeper follow-up:** Those abstractions let QUORUM swap Bedrock and Gemini without changing its agent roles or deterministic services.

### 6. How does Bedrock integration work?

**Short answer:** The factory creates a Strands `BedrockModel` from region and model ID.

**Deeper follow-up:** boto3 supplies standard-chain credentials; agents receive only the generic model interface. `scripts/validate_bedrock.py` performs bounded smoke, tool, Coordinator, and Negotiator checks outside pytest.

### 7. Why keep Gemini?

**Short answer:** It is a verified alternate and proves provider neutrality.

**Deeper follow-up:** Only factory configuration changes. Prompts, tools, sessions, workflow, policy, and UI stay the same.

### 8. What prevents the model from choosing an ineligible volunteer?

**Short answer:** The model only sees candidates returned by deterministic eligibility and ranking.

**Deeper follow-up:** Tool and assignment paths revalidate role/background requirements, while the core ranker checks availability, age, conflicts, contact limits, and travel feasibility.

### 9. How is candidate ranking explainable?

**Short answer:** Every score has a named numeric breakdown.

**Deeper follow-up:** Reliability and acceptance use Laplace smoothing; travel, availability, contact load, and recent contact contribute explicit weights. Stable volunteer ID breaks ties.

### 10. Why Laplace smoothing?

**Short answer:** It avoids treating tiny histories as perfectly reliable or unreliable.

**Deeper follow-up:** Adding one synthetic success and failure prior keeps a newcomer near 0.5 and reduces extreme estimates from one observation.

### 11. How do you prevent overbooking?

**Short answer:** Assignment confirmation is atomic.

**Deeper follow-up:** One lock covers duplicate detection, seat counting, and insertion. The test races two volunteers for one driver seat and proves only one wins.

### 12. How do duplicate events behave?

**Short answer:** The second request is suppressed by its idempotency key.

**Deeper follow-up:** The handler records the key before processing and writes a duplicate-suppressed ledger entry instead of creating new gaps or effects.

### 13. How are external side effects made safe?

**Short answer:** QUORUM reserves a stable effect key before calling a provider.

**Deeper follow-up:** A second attempt sees the reservation/result and returns duplicate-suppressed. Failures are stored explicitly instead of silently retried as success.

### 14. What makes YELLOW different from a queue?

**Short answer:** It represents a reversible settlement window with product meaning.

**Deeper follow-up:** The record includes what will happen and when; a coordinator can cancel it, while a guarded transition lets only cancellation or settlement win.

### 15. What happens when the Attention Budget is exhausted?

**Short answer:** Ordinary escalation becomes harder, but critical safety is not hidden.

**Deeper follow-up:** Thresholds rise. Critical/Layer-0 cases still route RED and increment the override count rather than normal spend.

### 16. Can a model downgrade an injury?

**Short answer:** No.

**Deeper follow-up:** The deterministic classifier checks safety first and replaces an unsafe model answer with `OUT_OF_SCOPE`. Escalation then recognizes the safety category as Layer-0.

### 17. How is prompt injection handled?

**Short answer:** The reply is treated as untrusted data and no action is taken.

**Deeper follow-up:** Known patterns return low-confidence `UNCLEAR`; prompts reinforce the boundary; and deterministic policy still gates any tool call.

### 18. Why persist a Human Decision separately from agent history?

**Short answer:** Operational review needs a typed lifecycle and audit record.

**Deeper follow-up:** Agent text alone cannot enforce allowed actions, idempotent resolution, versions, or reliable cross-page status.

### 19. How does interrupt resolution avoid duplicates?

**Short answer:** The service atomically claims OPEN before resolving.

**Deeper follow-up:** Only the winner moves to RESOLVING and then RESOLVED. Later requests return the existing state and do not resume twice.

### 20. Why is the Decision Ledger useful?

**Short answer:** It explains decisions without exposing private payloads.

**Deeper follow-up:** Entries connect events, routes, assignments, pending effects, gaps, and interrupts to safe reasons and related product resources.

### 21. Why not calculate coverage in React?

**Short answer:** Coverage affects decisions and belongs to backend authority.

**Deeper follow-up:** The API derives coverage from required roles and confirmed assignments; the frontend only presents typed results.

### 22. What does the evaluation result prove?

**Short answer:** It proves 20 implemented synthetic expectations currently regress correctly.

**Deeper follow-up:** It does not prove production safety, fairness, uptime, or real-world impact. It is deterministic regression evidence with explicit limits.

### 23. How would you replace MemoryStore?

**Short answer:** Preserve service interfaces and implement transactional/conditional operations.

**Deeper follow-up:** Event keys, capacity checks, pending claims, interrupt claims, budget spends, and run idempotency need database-level atomicity. The DynamoDB adapter sketches conditional writes but is not production wiring.

### 24. Why are demo runs synchronous?

**Short answer:** The three local scenarios finish quickly and do not need worker complexity.

**Deeper follow-up:** If recovery became slow, the API could return RUNNING and a worker would update the run; the UI could poll that resource. WebSockets are unnecessary for this scope.

### 25. How do you protect volunteer privacy?

**Short answer:** API-specific projections expose only operational fields.

**Deeper follow-up:** Raw messages, provider IDs, exact age, background-check internals, archetypes, secrets, and unreliable metrics are excluded. Contact load says `Not yet tracked` rather than fabricating history.

### 26. What is the hardest race condition here?

**Short answer:** Preventing capacity, settlement, or resolution from winning twice.

**Deeper follow-up:** Each operation combines an expected-state check and mutation under one lock; a distributed version needs equivalent conditional writes or transactions.

### 27. What would fail after a restart?

**Short answer:** Product state in `MemoryStore` would reset.

**Deeper follow-up:** The architecture separates persistence so a durable store can replace it. Local Strands sessions are file-backed, but that is not a substitute for a product database.

### 28. How would you test model variability?

**Short answer:** Add a separate opt-in provider evaluation, never normal pytest.

**Deeper follow-up:** Use a fixed labeled dataset, repeated bounded runs, structured-output accuracy, tool-call validity, cost/latency capture, and deterministic safety checks around every result.

### 29. Why not deploy this now?

**Short answer:** Production needs identity, durability, policy review, and operations work beyond a portfolio sprint.

**Deeper follow-up:** A deployment without tenant isolation, least-privilege IAM, persistence, monitoring, backups, privacy review, and stakeholder validation would overstate readiness.

### 30. What are you most proud of?

**Short answer:** The product demonstrates autonomy without confusing model fluency with authority.

**Deeper follow-up:** Scenario B finishes useful work without interruption, while Scenario C reliably stops. Both paths are visible through the same backend state, UI, and audit model.
