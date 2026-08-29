"""Offline integration and unit tests for the Phase 0 spike."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SPIKE_DIR = Path(__file__).resolve().parent
RUN = SPIKE_DIR / "spike_run.py"
RESUME = SPIKE_DIR / "spike_resume.py"
VERIFY = SPIKE_DIR / "spike_verify.py"


def invoke(script: Path, *args: str, runtime_dir: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["QUORUM_SPIKE_RUNTIME_DIR"] = str(runtime_dir)
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=SPIKE_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def assert_ok(result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"


@pytest.mark.parametrize(("scenario", "decision"), [("approval", "y"), ("veto", "n")])
def test_interrupt_survives_fresh_process_and_enforces_decision(
    tmp_path: Path, scenario: str, decision: str
) -> None:
    runtime = tmp_path / scenario
    initial = invoke(RUN, "--scenario", scenario, "--offline-test-model", runtime_dir=runtime)
    assert_ok(initial)
    assert "RUN_STOP_REASON=interrupt" in initial.stdout
    assert "READ_TOOL_EXECUTED" in initial.stdout
    assert not (runtime / "_effects.log").exists()

    resumed = invoke(RESUME, decision, runtime_dir=runtime)
    assert_ok(resumed)
    assert "RESUME_STOP_REASON=end_turn" in resumed.stdout

    verified = invoke(VERIFY, scenario, runtime_dir=runtime)
    assert_ok(verified)
    effects_path = runtime / "_effects.log"
    effects = effects_path.read_text(encoding="utf-8").splitlines() if effects_path.exists() else []
    assert len(effects) == (1 if scenario == "approval" else 0)

    pending = json.loads((runtime / "_pending.json").read_text(encoding="utf-8"))
    assert pending["run_pid"] != pending["resume_pid"]


def test_duplicate_send_is_suppressed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QUORUM_SPIKE_RUNTIME_DIR", str(tmp_path))
    sys.modules.pop("spike_server", None)
    import spike_server

    first = spike_server.record_send_effect("Sam T.", "Stable body")
    second = spike_server.record_send_effect("Sam T.", "Stable body")

    assert first["status"] == "sent"
    assert second["status"] == "duplicate_suppressed"
    assert first["idempotency_key"] == second["idempotency_key"]
    assert len(spike_server.read_effects()) == 1
