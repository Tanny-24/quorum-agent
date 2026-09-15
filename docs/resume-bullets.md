# QUORUM — Attention-Aware Autonomous Coordination Agent

Built a local, full-stack AI-agent portfolio system that recovers synthetic volunteer staffing while minimizing unnecessary human interruption. Combined Strands agent roles and interchangeable Bedrock/Gemini providers with a deterministic safety and operations core.

- Architected Coordinator and per-volunteer Negotiator agents through a provider-neutral Strands model factory, while keeping eligibility, ranking, capacity, idempotency, settlement, and Layer-0 safety authoritative in typed Python services.
- Delivered FastAPI orchestration and a responsive Next.js operations UI covering deterministic demo runs, staffing/volunteer views, pending effects, auditable decisions, and persistent human escalation with an Attention Budget.
- Created a reproducible 20-case synthetic benchmark that achieved 20/20 expected outcomes, 0 critical-safety misses, and 0 incorrect autonomous actions across safety, routing, concurrency, and idempotency cases.

**Tech stack:** Python 3.13, FastAPI, Pydantic, Strands Agents SDK, Amazon Bedrock, Google Gemini, boto3, pytest, Next.js 16, React 19, TypeScript, Tailwind CSS
