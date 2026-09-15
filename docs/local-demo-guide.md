# QUORUM Local Demo Guide

This is a 3–5 minute interview demo. It uses synthetic data and the deterministic backend, so it does not require AWS, Gemini, or Telegram.

## Before the interview

From the repository root, run the backend in terminal one:

```bash
PYTHONPATH=. .venv/bin/uvicorn quorum.api.app:app --reload
```

Run the frontend in terminal two:

```bash
cd web
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). Confirm the header says **Backend connected**.

## The 3–5 minute flow

### 1. Frame the product — 20 seconds

On **Overview**, say:

> QUORUM helps a volunteer coordinator recover staffing without forwarding every uncertainty to a human. Models may interpret language, but deterministic code owns eligibility, ranking, capacity, safety, and interruption policy.

Point to the Attention Budget, active operations, and Human Decisions.

### 2. Reset the synthetic workspace — 10 seconds

Open **Demo Mode**, click **Reset Demo**, and confirm. Explain that reset affects only the in-memory Riverside synthetic workspace.

### 3. Run Scenario B — 90 seconds

Click **Run Scenario B** and confirm.

Walk down the actual backend timeline:

1. A volunteer cancellation becomes an idempotent event.
2. `GapDetector` calculates driver and sorter shortfalls.
3. `CandidateRanker` filters eligibility and returns an explainable ordering.
4. The exact synthetic reply is: “I can do it, but I need a ride.”
5. `ReplyClassifier` returns `ACCEPT_IF` with canonical condition `transport`.
6. The shared transport service returns the synthetic community-van option.
7. The assignment passes the atomic capacity guard.
8. Gap detection runs again and the shift becomes fully staffed.

Point out **Human decision: Not required** and **Attention Budget: No change**.

Open **View Shift** to show confirmed assignments and no active gaps. Then open **Decision Feed** to show conditional reply, transport resolution, assignment, and gap-resolution records.

Say:

> The UI did not animate a prepared story. Every step and outcome came from the backend run resource.

### 4. Reset and run Scenario C — 60 seconds

Return to Demo Mode, reset, then run **Scenario C**.

Explain:

1. The reply contains an injury/complaint signal.
2. Deterministic Layer-0 policy takes precedence over any model answer.
3. Routing becomes RED.
4. QUORUM pauses before a consequential action.
5. A persistent Human Decision is created and one Attention Budget interruption is spent.

Click **View Human Decision**. Show the safe evidence, allowed Approve/Veto actions, related shift, and explicit local-demo identity caveat. Do not resolve it unless the interviewer asks to see idempotent resolution.

### 5. Finish with architecture — 30 seconds

Say:

> The Next.js UI calls FastAPI. The orchestration service composes a deterministic core and two Strands agent roles. One provider factory supports Bedrock and Gemini. Demo Mode bypasses external inference but uses the same operational services. Decision Ledger, Pending Effects, and Human Decisions make every consequential path inspectable.

If useful, open the Mermaid diagram in `docs/architecture.md`.

## Useful follow-ups

- **Volunteers:** show safe operational projections and `Not yet tracked` instead of fabricated contact history.
- **Pending Effects:** explain YELLOW settlement and cancellation races.
- **Backend offline:** stop the backend and refresh to show the explicit unavailable state; restart it afterward.
- **Evaluation:** run `PYTHONPATH=. .venv/bin/python scripts/run_evaluation.py` and explain that 20/20 is synthetic regression evidence, not production performance.

## What not to show

- `.env` or any credential/configuration value
- AWS identity, account ID, ARN, access key, secret, or session token
- Telegram identifiers or message credentials
- Raw volunteer/provider payloads
- Unnecessary terminal output
- Live Bedrock or Gemini calls unless credentials, access, cost, and the validation purpose were confirmed beforehand

## If something fails

- If the header says the backend is unavailable, confirm the FastAPI terminal is running on port 8000.
- Use **Reset Demo** before retrying a scenario.
- Do not describe a failed run as success; show its safe backend error or switch to the already-tested deterministic terminal demo.
