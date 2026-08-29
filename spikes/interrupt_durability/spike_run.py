"""Start a fresh Phase 0 session and stop at the send_message interrupt."""

from __future__ import annotations

import argparse
import os
import sys

from spike_server import (
    DEFAULT_SESSION_ID,
    EFFECTS_LOG,
    PENDING_FILE,
    atomic_write_json,
    create_agent,
    initial_prompt,
    read_effects,
    utc_now,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session-id", default=DEFAULT_SESSION_ID)
    parser.add_argument("--scenario", choices=("approval", "veto"), required=True)
    parser.add_argument(
        "--offline-test-model",
        action="store_true",
        help="Use the deterministic model for SDK integration tests; this is not a Bedrock acceptance run.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if PENDING_FILE.exists():
        print(f"FAIL: pending run already exists at {PENDING_FILE}; reset the generated state first.", file=sys.stderr)
        return 2
    if read_effects():
        print(f"FAIL: {EFFECTS_LOG} already contains effects; reset the generated state first.", file=sys.stderr)
        return 2

    model = None
    model_mode = "bedrock"
    if args.offline_test_model:
        from offline_test_model import DeterministicTestModel

        model = DeterministicTestModel()
        model_mode = "deterministic-offline-test"
        print("WARNING: deterministic offline test model selected; this is not a Bedrock acceptance run.")

    pid = os.getpid()
    print(f"RUN_PID={pid} session_id={args.session_id} model_mode={model_mode}")
    try:
        agent = create_agent(args.session_id, model=model)
        result = agent(initial_prompt())
    except Exception as exc:
        print(f"FAIL: agent invocation raised {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    print(f"RUN_STOP_REASON={result.stop_reason}")
    if result.stop_reason != "interrupt":
        print("FAIL: expected stop_reason=interrupt", file=sys.stderr)
        return 1
    if len(result.interrupts) != 1:
        print(f"FAIL: expected one interrupt, found {len(result.interrupts)}", file=sys.stderr)
        return 1

    effect_count = len(read_effects())
    if effect_count != 0:
        print(f"FAIL: side effect executed before approval (count={effect_count})", file=sys.stderr)
        return 1

    interrupt = result.interrupts[0]
    pending = {
        "created_at": utc_now(),
        "effect_count_before_resume": effect_count,
        "interrupts": [interrupt.to_dict()],
        "model_mode": model_mode,
        "run_pid": pid,
        "scenario": args.scenario,
        "session_id": args.session_id,
        "stop_reason": result.stop_reason,
    }
    atomic_write_json(PENDING_FILE, pending)
    print(f"INTERRUPT_ID={interrupt.id}")
    print("PASS: interrupted before side effect; process may now terminate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
