from __future__ import annotations

from datetime import datetime, timezone

from quorum.domain.models import Assignment, GapStatus, Role
from quorum.services.candidate_ranker import CandidateRanker, laplace
from quorum.services.gap_detector import GapDetector
from quorum.services.policy import PolicyAction, PolicyGuard
from quorum.utils import stable_id


def add_assignment(store, shift_id: str, volunteer_id: str, role: Role, required: int) -> None:
    assignment = Assignment(
        id=stable_id("assignment", shift_id, volunteer_id, role.value),
        shift_id=shift_id,
        volunteer_id=volunteer_id,
        role=role,
        confirmed_at=datetime.now(timezone.utc),
    )
    assert store.confirm_assignment(assignment, required)[0]


def test_gap_detector_fully_staffed_one_short_multiple_short_and_roles(store) -> None:
    shift = store.get_shift("shift-1")
    assert shift is not None
    detector = GapDetector(store)
    initial = detector.detect(shift.id, "event-1")
    assert {(gap.role, gap.shortfall) for gap in initial} == {(Role.DRIVER, 1), (Role.SORTER, 2)}

    add_assignment(store, shift.id, "vol-02", Role.DRIVER, 1)
    add_assignment(store, shift.id, "vol-03", Role.SORTER, 2)
    partially = detector.detect(shift.id, "event-2")
    assert [(gap.role, gap.shortfall) for gap in partially] == [(Role.SORTER, 1)]

    add_assignment(store, shift.id, "vol-04", Role.SORTER, 2)
    assert detector.detect(shift.id, "event-3") == []
    assert all(gap.status == GapStatus.RESOLVED for gap in store.list_gaps())


def test_duplicate_gap_and_terminal_gap_are_not_reopened(store) -> None:
    detector = GapDetector(store)
    first = detector.detect("shift-2", "event-a")
    second = detector.detect("shift-2", "event-a-duplicate")
    assert [gap.id for gap in first] == [gap.id for gap in second]
    driver = next(gap for gap in first if gap.role == Role.DRIVER)
    driver.status = GapStatus.FAILED
    store.update_gap(driver)
    detector.detect("shift-2", "event-b")
    assert store.get_gap(driver.id).status == GapStatus.FAILED


def test_laplace_smoothing_and_ranking_are_reproducible(store) -> None:
    assert laplace(0, 0) == 0.5
    assert laplace(9, 1) > laplace(1, 1)
    ranker = CandidateRanker(store)
    first = ranker.rank("shift-1", Role.DRIVER)
    second = ranker.rank("shift-1", Role.DRIVER)
    assert first == second
    assert first[0].score >= first[-1].score
    assert set(first[0].breakdown) == {
        "reliability",
        "acceptance_rate",
        "travel_feasibility",
        "availability_fit",
        "contact_load",
        "recent_contact_penalty",
    }


def test_eligibility_blocks_minor_driver_and_missing_check(store) -> None:
    ranker = CandidateRanker(store)
    shift = store.get_shift("shift-1")
    minor = next(volunteer for volunteer in store.list_volunteers() if volunteer.archetype == "minor-driver-blocked")
    assert "under_minimum_age" in ranker.eligibility(minor, shift, Role.DRIVER)
    unchecked = store.volunteers["vol-02"]
    unchecked.background_check = False
    assert "missing_background_check" in ranker.eligibility(unchecked, shift, Role.DRIVER)


def test_policy_contact_cap_quiet_hours_and_decline_final(store) -> None:
    guard = PolicyGuard("UTC")
    volunteer = store.volunteers["vol-02"]
    volunteer.weekly_contact_count = 2
    assert guard.contact(volunteer, Role.SORTER, datetime(2026, 1, 1, 12, tzinfo=timezone.utc)).action == PolicyAction.REFUSE
    volunteer.weekly_contact_count = 0
    volunteer.concurrent_asks = 3
    assert guard.contact(volunteer, Role.SORTER, datetime(2026, 1, 1, 12, tzinfo=timezone.utc)).reason == "max_concurrent_asks"
    volunteer.concurrent_asks = 0
    assert guard.contact(volunteer, Role.SORTER, datetime(2026, 1, 1, 22, tzinfo=timezone.utc)).action == PolicyAction.QUEUE
    assert guard.contact(
        volunteer, Role.SORTER, datetime(2026, 1, 1, 12, tzinfo=timezone.utc), thread_declined=True
    ).reason == "decline_is_final"
