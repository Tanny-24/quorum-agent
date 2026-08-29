"""Resume a persisted Phase 0 interrupt in a completely fresh process."""

from __future__ import annotations

import argparse
import os
import sys

from spike_server import PENDING_FILE, atomic_write_json, create_agent, read_effects, read_json, utc_now


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("decision", choices=("y", "n"), help="y approves; n vetoes")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not PENDING_FILE.exists():
        print(f"FAIL: no persisted interrupt metadata at {PENDING_FILE}", file=sys.stderr)
        return 2

    pending = read_json(PENDING_FILE)
    expected = "y" if pending["scenario"] == "approval" else "n"
    if args.decision != expected:
        print(
            f"FAIL: pending scenario={pending['scenario']!r} requires decision {expected!r}; "
            "reset to exercise a different path.",
            file=sys.stderr,
        )
        return 2

    run_pid = int(pending["run_pid"])
    resume_pid = os.getpid()
    if resume_pid == run_pid:
        print("FAIL: resume must execute in a different process", file=sys.stderr)
        return 1

    model = None
    if pending["model_mode"] == "deterministic-offline-test":
        from offline_test_model import DeterministicTestModel

        model = DeterministicTestModel()
        print("WARNING: resuming with deterministic offline test model; this is not a Bedrock acceptance run.")
    elif pending["model_mode"] != "bedrock":
        print(f"FAIL: unsupported persisted model mode {pending['model_mode']!r}", file=sys.stderr)
        return 2

    print(f"RESUME_PID={resume_pid} original_pid={run_pid} session_id={pending['session_id']}")
    responses = [
        {
            "interruptResponse": {
                "interruptId": interrupt["id"],
                "response": args.decision,
            }
        }
        for interrupt in pending["interrupts"]
    ]

    count_before = len(read_effects())
    try:
        agent = create_agent(str(pending["session_id"]), model=model)
        result = agent(responses)
    except Exception as exc:
        print(f"FAIL: resume invocation raised {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    count_after = len(read_effects())
    pending.update(
        {
            "decision": args.decision,
            "effect_count_after_resume": count_after,
            "effect_count_at_resume_start": count_before,
            "resume_completed_at": utc_now(),
            "resume_pid": resume_pid,
            "resume_stop_reason": result.stop_reason,
        }
    )
    atomic_write_json(PENDING_FILE, pending)
    print(f"RESUME_STOP_REASON={result.stop_reason}")
    print(f"EFFECT_COUNT_BEFORE={count_before} EFFECT_COUNT_AFTER={count_after}")
    if result.stop_reason == "interrupt":
        print("FAIL: resumed flow interrupted again", file=sys.stderr)
        return 1
    print("PASS: persisted interrupt response completed in a fresh process.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
