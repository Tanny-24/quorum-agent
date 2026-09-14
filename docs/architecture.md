# QUORUM Core Architecture

QUORUM separates probabilistic language reasoning from deterministic authority. A small provider factory supplies a configured Strands Model to both agent roles and the structured classifier. Google Gemini is the active submission provider.

~~~text
Events / Telegram
        ↓
provider-neutral normalizer + event idempotency
        ↓
Coordinator Agent — Strands (org:riverside session)
        ↓
Google Gemini 3.6 Flash — language reasoning + tool selection
        ↓
QUORUM tools + deterministic gap/ranking services
        ↓
Negotiator Agent — Strands (nego:{shift}:{volunteer} session)
        ↓
BeforeToolCallEvent RoutingHook
        ↓
hard policy → static reversibility → EV heuristic → Attention Budget
        ↓
GREEN execute | YELLOW PendingEffect | RED InterruptRecord | SILENT/DEFER ledger
        ↓
assignment capacity + append-only logical decision feed
~~~

## Model boundary

Settings reads QUORUM_MODEL_PROVIDER, QUORUM_MODEL_ID, and GEMINI_API_KEY without logging them. quorum.agents.models.create_model owns provider-specific construction; Coordinator and Negotiator only receive the generic Strands Model interface. The Gemini key is passed in memory through client_args and never enters a prompt or result.

Gemini uses thinking_level=minimal, temperature zero, and bounded output for short operational turns. The classifier uses Strands' provider-native JSON-schema output. Deterministic code canonicalizes known conditions such as transport and overrides injury, complaint, and prompt-injection-shaped replies. A model can raise concern but cannot lower an observable safety signal.

## Deterministic authority

Code—not Gemini—owns staffing arithmetic, eligibility, age and background-check rules, candidate scores, contact limits, quiet hours, assignment capacity and race resolution, stable idempotency keys, routing thresholds, Attention Budget spending, PendingEffect transitions, interrupt resolution, and ledger records.

The heuristic (consequence × uncertainty × urgency) / reversibility is named policy, not model judgment. Layer-0 injury, safeguarding, vulnerable-person, harassment, discrimination, complaint, service-allocation, permanent-removal, money/employment, and unsafe-minor cases bypass the heuristic and route directly to RED.

## Persistence and concurrency

MemoryStore provides locked atomic behavior for tests and the demo. DynamoDBStore expresses conditional writes for a future deployment; it is not claimed as live. Strands conversation state uses FileSessionManager and stable session IDs.

YELLOW timers persist settle_at; no sleep represents business state. Settlement conditionally claims PENDING → SETTLING, while cancellation competes with the same transition. RED resolution is idempotent. The Phase 0 restart spike proves Strands interrupt state and exactly-once side effects survive a process restart.

## Real submission evidence

scripts.run_agent_demo fails closed unless it observes:

- a Gemini-backed Coordinator call to get_shift;
- a two-turn Gemini-backed Negotiator call to find_transport_option;
- structured conditional, unclear, safety, and injection classifications;
- deterministic transport canonicalization, assignment, and resolved gap state;
- Layer-0 RED routing with one persisted human interrupt.

Model provider selection remains configurable. Amazon Bedrock integration is planned once AWS account activation is resolved; it is not an active component or completed deployment.
