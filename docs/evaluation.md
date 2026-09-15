# Synthetic Evaluation

> **Synthetic evaluation — not real-world production performance.**

## Why this exists

QUORUM combines model-facing components with deterministic authority. This benchmark checks the authority layer directly so regression evidence is fast, reproducible, inexpensive, and independent of Bedrock, Gemini, Telegram, or the network.

## Methodology

`scripts/run_evaluation.py` runs 20 named synthetic cases against fresh seeded `MemoryStore` instances and a fixed clock. Every case declares one expected observable outcome. The runner uses the same services as the application and exits non-zero if any expectation fails.

No model calls, channel sends, external services, production records, or private data are involved. `--json` prints per-case expected and actual outcomes for inspection.

## Test categories

- Staffing: cancellation and no-show gap detection
- Ranking: deterministic reproducibility
- Replies: accept, conditional transport, decline, and ambiguity
- Safety: injury, complaint, safeguarding, and prompt injection
- Idempotency: duplicate events, duplicate assignments, and duplicate human resolution
- Concurrency: assignment capacity race
- Policy and eligibility: contact cap and minor-driver block
- Routing: Layer-0 RED, GREEN, and YELLOW

## Metrics

- `expected_outcome_accuracy` is correct cases divided by total cases.
- `critical_safety_misses` counts tagged critical cases whose expected safe outcome was not observed.
- `incorrect_autonomous_actions` counts critical cases observed on an autonomous path.
- `autonomous_resolution_cases` and `human_interruption_cases` count correct cases by their actual attention path.
- Protection metrics count correct idempotency and assignment-capacity guard cases.

## Latest measured result

Measured locally on 15 September 2026:

| Metric | Result |
| --- | ---: |
| Total cases | 20 |
| Expected outcomes correct | 20 |
| Expected-outcome accuracy | 1.0 |
| Critical safety cases | 4 |
| Critical safety misses | 0 |
| Incorrect autonomous actions | 0 |
| Autonomous-resolution cases | 14 |
| Human-interruption cases | 5 |
| Prompt-injection attempts blocked | 1 |
| Idempotency protection cases | 3 |
| Assignment protection cases | 1 |

Command used:

```bash
PYTHONPATH=. .venv/bin/python scripts/run_evaluation.py
```

## Limitations

- Synthetic cases validate implemented rules, not real volunteer outcomes.
- The benchmark is intentionally small and does not estimate social impact, model quality, fairness, latency, cost, or production reliability.
- Cases are deterministic and therefore do not measure language-model variance.
- The in-memory concurrency case checks one process, not a distributed deployment.
- Passing the benchmark is regression evidence, not a safety certification.
