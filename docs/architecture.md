# QUORUM Core Architecture

The current local core keeps natural-language interpretation separate from deterministic authority.

```text
Telegram / API event
        ↓
provider-neutral normalization + event idempotency
        ↓
Coordinator (fresh Strands Agent, org:riverside session)
        ↓
deterministic gap detection and ranked candidates
        ↓
Negotiator (fresh Strands Agent, nego:{shift}:{volunteer} session)
        ↓
registered tool call
        ↓
BeforeToolCallEvent RoutingHook
        ↓
hard policy → static reversibility → EV heuristic → attention budget
        ↓
GREEN execute | YELLOW PendingEffect | RED InterruptRecord | SILENT/DEFER ledger
        ↓
append-only logical decision feed
```

## Deterministic authority

Code—not a model—owns staffing arithmetic, eligibility, candidate scores, contact limits, quiet hours, assignment capacity, stable idempotency keys, routing thresholds, attention spending, pending transitions, interrupt resolution, and ledger records. An empty candidate pool raises observable uncertainty to its maximum. Model concern may raise uncertainty but cannot lower observable concern.

The EV formula `(consequence × uncertainty × urgency) / reversibility` is a named policy heuristic, not a claim of mathematical optimality. Layer-0 injury, safeguarding, vulnerable-person, harassment, discrimination, complaint, service-allocation, permanent-removal, money/employment, and unsafe-minor cases bypass EV and route directly to RED.

## Persistence and concurrency

`MemoryStore` provides locked atomic behavior for tests/local development. `DynamoDBStore` expresses conditional writes for idempotency, status transitions, assignment seat capacity, and attention spending; it does not require live AWS for tests. Strands conversation state uses explicit `FileSessionManager` paths and stable session IDs.

YELLOW timers persist `settle_at`; no long-running sleep represents business state. Settlement claims `PENDING → SETTLING` conditionally before execution. Cancellation competes with the same transition, so only one wins. RED resolution is idempotent, and the Phase 0 spike remains the process-restart proof for Strands interrupt state and exactly-once side effects.

## Current boundary

The local deterministic workflow and test doubles exercise the whole roster-recovery path. Real Bedrock execution and live DynamoDB validation are separate external checks. No Evals, AgentCore, EventBridge, dashboard, or production deployment is claimed.
