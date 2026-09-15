from __future__ import annotations

from scripts.run_evaluation import LABEL, run_evaluation


def test_synthetic_evaluation_is_complete_deterministic_and_safe() -> None:
    first = run_evaluation()
    second = run_evaluation()

    assert first == second
    assert first["label"] == LABEL
    assert len(first["cases"]) == 20
    assert first["metrics"] == {
        "total_cases": 20,
        "expected_outcome_correct": 20,
        "expected_outcome_accuracy": 1.0,
        "critical_safety_cases": 4,
        "critical_safety_misses": 0,
        "incorrect_autonomous_actions": 0,
        "autonomous_resolution_cases": 14,
        "human_interruption_cases": 5,
        "prompt_injection_blocked": 1,
        "idempotency_protection_cases": 3,
        "assignment_protection_cases": 1,
    }
