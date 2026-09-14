# QUORUM

QUORUM is an attention-aware autonomous roster-recovery agent for the synthetic **Riverside Food Bank**. It uses the Strands Agents SDK with Google Gemini as the active model provider. Strands remains provider-agnostic; QUORUM's agent architecture and deterministic authority do not change with the model provider.

Implemented:

- separate Strands Coordinator and per-thread Negotiator agents
- real Gemini-backed inference and Strands tool calling
- persisted organization and nego:{shift}:{volunteer} sessions
- durable interrupt/resume proof
- deterministic gap detection, eligibility, candidate ranking, and assignment capacity
- BeforeToolCallEvent routing across GREEN, YELLOW, RED, and SILENT/DEFER
- Attention Budget, cancellable PendingEffect settlement, stable idempotency, and decision ledger
- deterministic safety overrides that model output cannot downgrade
- FastAPI backend and provider-neutral Telegram channel
- synthetic dataset, three deterministic scenarios, and a fail-closed live agent demo

Amazon Bedrock was the originally intended provider but could not be live-validated because AWS account activation remained blocked during the hackathon. Bedrock and the DynamoDB adapter remain future deployment paths, not completed submission infrastructure. AgentCore, EventBridge, a dashboard, and production IAM are not claimed.

## Setup

~~~bash
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
~~~

Set these values in the ignored .env:

~~~dotenv
GEMINI_API_KEY=your-local-secret
QUORUM_MODEL_PROVIDER=gemini
QUORUM_MODEL_ID=gemini-3.6-flash
~~~

Never commit .env. gemini-2.5-flash returned a provider 404 for this account because it is unavailable to new users; gemini-3.6-flash is the API-verified replacement. QUORUM uses minimal thinking and short output budgets for predictable operational turns.

## Run

~~~bash
# Inspect the synthetic fixture
PYTHONPATH=. .venv/bin/python -m scripts.seed_demo

# Run the three deterministic authority/safety scenarios
PYTHONPATH=. .venv/bin/python -m scripts.run_demo

# Run real Gemini Coordinator, Negotiator, tools, classifications, E2E, and RED safety proof
PYTHONPATH=. .venv/bin/python -m scripts.run_agent_demo

# Start the API
PYTHONPATH=. .venv/bin/uvicorn quorum.api.app:app --reload

# Run the full suite, including Phase 0 durability
PYTHONPATH=. .venv/bin/python -m pytest tests spikes/interrupt_durability/test_spike.py -v
~~~

The live demo prints only synthetic observable state. It includes a 55-second pause between phases so it fits Gemini free-tier request windows. It fails instead of simulating success when Gemini, tool calls, classifications, resolution, or safety evidence is missing.

API endpoints:

- GET /health
- GET /shifts
- POST /events/cancel
- POST /events/no-show
- POST /events/tick
- POST /webhooks/messages
- GET /interrupts
- POST /interrupts/{id}/resolve
- GET /feed
- POST /pending/{id}/cancel

## Telegram

The existing adapter has real inbound and outbound validation. These commands use TelegramChannel and never print credentials or message contents:

~~~bash
PYTHONPATH=. .venv/bin/python -m scripts.send_test_message
PYTHONPATH=. .venv/bin/python -m scripts.poll_telegram
~~~

The isolated smoke command sends exactly QUORUM Gemini integration ready; run it at most once after the Gemini demo passes.

## Submission material

See [architecture](docs/architecture.md), [four-minute demo script](docs/demo-script.md), and [Devpost draft](docs/devpost-submission.md).
