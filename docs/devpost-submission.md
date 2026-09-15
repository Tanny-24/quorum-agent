# QUORUM — Devpost submission draft

**Project title:** QUORUM

**Tagline:** Resolve the coordination gap without creating an attention crisis.

**Track:** Good Neighbor Agents — AWS Agents for Humans Hackathon

## Inspiration

Volunteer operations often fail in the final mile. A coordinator notices a cancellation, searches a roster, messages several people, waits, reconciles conditional replies, and decides when a situation deserves human attention. The burden is not missing data; it is repeated, interruption-heavy coordination. We built QUORUM to recover staffing while treating human attention as a limited resource.

## What it does

QUORUM monitors a synthetic Riverside Food Bank roster for cancellations and no-shows. It detects role-level gaps, filters and ranks eligible volunteers, opens one scoped negotiation per volunteer and shift, interprets replies, checks constraints such as transport, and confirms an assignment only while capacity remains.

Every action follows one of four routes: GREEN executes, YELLOW enters a cancellable settlement window, RED creates a durable human interrupt, and SILENT/DEFER records why no interruption was warranted. Injury, safeguarding, harassment, complaints, and comparable high-consequence topics always escalate.

## How we built it

QUORUM uses Python 3.13 and Strands Agents SDK 1.53.0. A shared provider factory supports Amazon Bedrock as the primary configured provider and Google Gemini as an alternate, supplying the same Strands `Model` interface to the Coordinator, per-thread Negotiator, and structured reply classifier. The reliable browser demo uses deterministic execution and does not require either provider.

Provider-backed agents handle language interpretation and tool selection. Deterministic Python services retain authority over staffing arithmetic, eligibility, ranking, contact limits, transport facts, idempotency, assignment capacity, routing thresholds, Attention Budgets, pending effects, interrupts, and the decision ledger. File-backed Strands sessions make conversations recoverable, and locked local persistence supports the demo.

The product demo records observable proof: backend orchestration steps, conditional transport, assignments, resolved gap state, and a persisted RED safety interrupt. Normal tests mock external network calls while preserving the same boundaries; live-provider checks remain separate opt-in scripts.

## Challenges

The first challenge was keeping probabilistic language behavior away from irreversible authority. Registered tools, a BeforeToolCallEvent hook, static reversibility metadata, stable idempotency keys, and deterministic safety precedence solved that boundary.

The second was durable interruption. A human decision may arrive after a process restart, so the repository includes a restart-focused Strands interrupt spike and idempotent interrupt records.

The third was keeping the product demonstrable without depending on cloud quota. Strands' provider abstraction supports Bedrock and Gemini without redesigning QUORUM, while `deterministic_demo` runs the complete operational workflow with no model request.

## Accomplishments

- Provider-neutral Strands agents and Python tool calls, with Bedrock/Gemini construction tests.
- Coordinator and per-thread Negotiator separation with durable session IDs.
- Explainable candidate scores and deterministic assignment capacity.
- Cancellable YELLOW effects and durable RED human interrupts.
- Safety and injection rules that model output cannot downgrade.
- A fail-closed evidence runner and focused provider tests.
- Provider-neutral Telegram integration and an inspectable decision ledger.

## What we learned

Agent reliability improves when the model has a narrow job. QUORUM asks Gemini to interpret language and select capabilities, then asks code to decide what is eligible, authorized, reversible, and already done. We also learned that silence is a product feature: an agent should be able to record a low-value decision without demanding attention.

## What's next

The final local portfolio build includes a replayable 20-case synthetic evaluation and a responsive operator dashboard. Production authentication, durable persistence, deployment infrastructure, and operational monitoring are intentionally not claimed.

## Technologies used

Python, Strands Agents SDK, Amazon Bedrock, Google Gemini, FastAPI, Pydantic, boto3, HTTPX, pytest, Next.js, TypeScript, Tailwind CSS, and Telegram Bot API.
