# QUORUM

QUORUM is an attention-aware autonomous roster-recovery agent for the synthetic **Riverside Food Bank**. The current repository contains the Phase 0 durable Strands interrupt spike and a local core MVP. It is not a general volunteer-management product.

Implemented locally:

- Telegram send, polling, and provider-neutral normalization
- typed synthetic domain with six sites, 36 volunteers, and six shifts
- deterministic gap detection, eligibility, explainable ranking, policy, routing, and idempotency
- atomic assignment capacity, attention budgets, YELLOW settlement windows, RED interrupt records, and decision ledger
- fresh-per-invocation Strands Coordinator and Negotiator factories using `FileSessionManager`
- FastAPI endpoints and a three-scenario deterministic demo
- DynamoDB conditional-operation adapter (unit-tested, not live-validated)

Not implemented here: Evals, AgentCore/EventBridge deployment, frontend/dashboard, analytics, or production IAM.

## Setup

```bash
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
```

Keep real Telegram values only in `.env`; it is ignored by Git. Bedrock model IDs are intentionally blank until verified in the target AWS account.

## Run

```bash
# Inspect the synthetic fixture
.venv/bin/python -m scripts.seed_demo

# Run the local three-path core demo (uses a labelled compressed settlement clock)
.venv/bin/python -m scripts.run_demo

# Start the API
.venv/bin/uvicorn quorum.api.app:app --reload

# Run tests, including the Phase 0 regression
.venv/bin/python -m pytest tests spikes/interrupt_durability/test_spike.py -v
```

API endpoints:

- `GET /health`
- `GET /shifts`
- `POST /events/cancel`
- `POST /events/no-show`
- `POST /events/tick`
- `POST /webhooks/messages`
- `GET /interrupts`
- `POST /interrupts/{id}/resolve`
- `GET /feed`
- `POST /pending/{id}/cancel`

## Telegram development commands

Both paths use `TelegramChannel`; neither prints secrets or message contents.

```bash
.venv/bin/python -m scripts.send_test_message
.venv/bin/python -m scripts.poll_telegram
```

The smoke command sends exactly: `QUORUM core integration smoke test`.

## Architecture

See `docs/architecture.md`. Production Bedrock and DynamoDB validation remain dependent on configured AWS credentials and resources.
