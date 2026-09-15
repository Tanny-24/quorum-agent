# QUORUM Code Walkthrough

Learn the repository in this order. The goal is to understand the authority boundaries before individual implementation details.

## 1. Domain models — `quorum/domain/models.py`

- **Purpose:** names the operational state and legal statuses.
- **Input:** validated Python/Pydantic values.
- **Output:** typed synthetic entities such as `Shift`, `Gap`, `PendingEffect`, `InterruptRecord`, and `RecoveryRun`.
- **Why it exists:** every service shares one vocabulary and APIs avoid untyped dictionaries.
- **Interview question:** why model recovery and human decisions explicitly instead of returning agent text?

## 2. MemoryStore — `quorum/persistence/memory.py`

- **Purpose:** local state plus atomic transitions under one lock.
- **Input:** domain records and expected current states.
- **Output:** copied records, transition winners, and explicit reasons.
- **Why it exists:** idempotency, capacity, settlement, and budget updates need authority independent of the LLM.
- **Interview question:** what changes for distributed persistence? Explain conditional writes and transactions.

## 3. GapDetector — `quorum/services/gap_detector.py`

- **Purpose:** compare required role capacity with confirmed assignments.
- **Input:** shift ID and source event ID.
- **Output:** role-level gaps or terminal resolution.
- **Why it exists:** staffing arithmetic must be deterministic and repeatable.
- **Interview question:** how are duplicate and terminal gaps handled?

## 4. CandidateRanker and PolicyGuard

Files: `quorum/services/candidate_ranker.py`, `quorum/services/policy.py`.

- **Purpose:** reject ineligible candidates, then rank the eligible pool transparently.
- **Input:** volunteer, shift, role, and optional clock.
- **Output:** rejection reasons or sorted score breakdowns.
- **Why it exists:** a model must not invent or unfairly select candidates outside declared policy.
- **Interview question:** why Laplace smoothing, and which weights would require stakeholder review?

## 5. Reply and safety classification — `quorum/agents/classifier.py`

- **Purpose:** interpret replies while enforcing deterministic safety precedence.
- **Input:** one inbound text and optionally a provider-backed model.
- **Output:** structured intent, canonical condition, confidence, and safety reason.
- **Why it exists:** language can be probabilistic, but known safety and injection patterns cannot be downgraded.
- **Interview question:** what if the model says ACCEPT but the text mentions injury?

## 6. Routing and Attention Budget

Files: `quorum/services/escalation.py`, `quorum/hooks/routing.py`.

- **Purpose:** route effects to GREEN, YELLOW, RED, or SILENT/DEFER.
- **Input:** consequence, uncertainty, urgency, reversibility, safety category, and current budget.
- **Output:** route, explanation, threshold, and budget effect.
- **Why it exists:** tool selection does not imply authorization to execute.
- **Interview question:** why does Layer-0 bypass the EV heuristic?

## 7. Pending Effects and interrupts

Files: `quorum/services/pending_effects.py`, `quorum/services/interrupts.py`.

- **Purpose:** represent waiting and human judgment as durable state.
- **Input:** idempotency key, effect payload, settlement time, or decision.
- **Output:** guarded transitions and ledger-visible outcomes.
- **Why it exists:** sleeping is not persistence, and a chat response is not a human-decision record.
- **Interview question:** how do cancel/settle and duplicate resolution races behave?

## 8. CoreWorkflow — `quorum/services/workflow.py`

- **Purpose:** join deterministic events, negotiation state, reply handling, transport, assignment, gaps, interrupts, and ledger entries.
- **Input:** typed event/reply context.
- **Output:** actual domain mutations and structured outcomes.
- **Why it exists:** one application service coordinates the core without moving rules into routes or UI.
- **Interview question:** which parts would remain unchanged if the model provider changed?

## 9. Agent factories and model factory

Files: `quorum/agents/coordinator.py`, `quorum/agents/negotiator.py`, `quorum/agents/models.py`, `quorum/agents/prompts.py`.

- **Purpose:** build fresh Strands agents over stable sessions and a provider-neutral model.
- **Input:** settings, tools, hooks, and optional injected model.
- **Output:** scoped Coordinator or Negotiator agent.
- **Why it exists:** provider configuration stays separate from role prompts and business policy.
- **Interview question:** why two agents, and why inject `Model` in tests?

## 10. Demo orchestration — `quorum/services/orchestration.py`

- **Purpose:** execute A/B/C as server-side workflows and record truthful recovery steps.
- **Input:** scenario ID and idempotency key.
- **Output:** `RecoveryRun` with final shift, budget, and decision references.
- **Why it exists:** browser demos must execute real services rather than insert final UI state.
- **Interview question:** why is `deterministic_demo` still a valid agent-system demonstration?

## 11. FastAPI — `quorum/api/app.py`, `schemas.py`, `read_models.py`

- **Purpose:** expose typed safe commands and read projections.
- **Input:** HTTP parameters and request schemas.
- **Output:** coordinator-facing views without raw internal/private objects.
- **Why it exists:** product APIs need a stable privacy and authority boundary.
- **Interview question:** why not serialize `Volunteer` directly?

## 12. Frontend — `web/src`

- **Purpose:** make backend state operable and understandable.
- **Input:** central API-client responses.
- **Output:** responsive views, confirmations, timelines, and links.
- **Why it exists:** operators need decisions and consequences, not JSON or agent transcripts.
- **Interview question:** which values are deliberately not calculated in the browser?

## 13. Evaluation — `scripts/run_evaluation.py`

- **Purpose:** run a small repeatable safety/authority regression benchmark.
- **Input:** fixed synthetic cases and fresh stores.
- **Output:** honest aggregate metrics plus optional per-case JSON.
- **Why it exists:** unit counts alone do not communicate the expected operational outcomes.
- **Interview question:** what does 20/20 prove, and what does it not prove?

## 14. Tests — `tests/unit`

Read provider factory tests, then gap/ranker/policy, routing/persistence, product APIs, Phase 3 orchestration, and evaluation. Notice that live-provider validation is excluded: normal tests never spend model quota or send Telegram messages.
