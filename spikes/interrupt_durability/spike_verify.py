"""Verify or safely reset Phase 0 generated proof artifacts."""

from __future__ import annotations

import argparse
import shutil
import sys

from spike_server import (
    EFFECTS_LOCK,
    EFFECTS_LOG,
    PENDING_FILE,
    RUNTIME_DIR,
    STATE_DIR,
    idempotency_key,
    read_effects,
    read_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("approval", "veto", "reset"))
    return parser.parse_args()


def reset_runtime() -> int:
    targets = (STATE_DIR, EFFECTS_LOG, EFFECTS_LOCK, PENDING_FILE)
    for target in targets:
        resolved = target.resolve()
        if resolved.parent != RUNTIME_DIR and resolved != STATE_DIR.resolve():
            print(f"FAIL: refusing to reset unexpected path {resolved}", file=sys.stderr)
            return 2
        if resolved.is_dir():
            shutil.rmtree(resolved)
        elif resolved.exists():
            resolved.unlink()
    print(f"PASS: removed only generated spike runtime state under {RUNTIME_DIR}")
    return 0


def verify(scenario: str) -> int:
    failures: list[str] = []
    if not PENDING_FILE.exists():
        failures.append("pending metadata is missing")
        pending = {}
    else:
        pending = read_json(PENDING_FILE)

    effects = read_effects()
    if pending.get("scenario") != scenario:
        failures.append(f"pending scenario is {pending.get('scenario')!r}, expected {scenario!r}")
    if pending.get("stop_reason") != "interrupt":
        failures.append("original stop reason was not interrupt")
    if pending.get("effect_count_before_resume") != 0:
        failures.append("an effect existed before resume")
    if "resume_pid" not in pending:
        failures.append("resume metadata is missing")
    elif pending.get("resume_pid") == pending.get("run_pid"):
        failures.append("run and resume PIDs are identical")
    if pending.get("resume_stop_reason") == "interrupt":
        failures.append("resume stopped on another interrupt")

    if scenario == "approval":
        if pending.get("decision") != "y":
            failures.append("approval decision was not recorded")
        if len(effects) != 1:
            failures.append(f"expected exactly one effect, found {len(effects)}")
        if effects:
            effect = effects[0]
            expected_key = idempotency_key(str(effect.get("recipient", "")), str(effect.get("body", "")))
            if effect.get("idempotency_key") != expected_key:
                failures.append("effect has an invalid stable idempotency key")
            if effect.get("pid") != pending.get("resume_pid"):
                failures.append("effect did not execute in the resume process")
            if effect.get("pid") == pending.get("run_pid"):
                failures.append("effect executed in the original process")
            reason = (pending.get("interrupts") or [{}])[0].get("reason", {})
            if effect.get("idempotency_key") != reason.get("idempotency_key"):
                failures.append("effect key differs from the pre-interrupt action key")
    else:
        if pending.get("decision") != "n":
            failures.append("veto decision was not recorded")
        if effects:
            failures.append(f"veto expected zero effects, found {len(effects)}")

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        return 1

    print(
        f"PASS: {scenario} path; run_pid={pending['run_pid']} resume_pid={pending['resume_pid']} "
        f"effects={len(effects)}"
    )
    return 0


def main() -> int:
    args = parse_args()
    if args.command == "reset":
        return reset_runtime()
    return verify(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
