"""Run three deterministic local QUORUM core scenarios with a compressed demo clock."""

from __future__ import annotations

from datetime import timedelta

from quorum.data.loader import seed_store
from quorum.domain.models import Role
from quorum.events.models import EventKind
from quorum.persistence.memory import MemoryStore
from quorum.services.workflow import CoreWorkflow
from quorum.utils import utc_now


def main() -> int:
    store = seed_store(MemoryStore())
    workflow = CoreWorkflow(store)

    gaps_a = workflow.staffing_event(EventKind.VOLUNTEER_CANCELLED, "shift-1", "demo-a-cancel")
    candidates_a = workflow.ranker.rank("shift-1", Role.DRIVER)
    thread_a = workflow.open_thread("shift-1", candidates_a[0].volunteer_id)
    workflow.queue_outreach(thread_a, "Can you cover the synthetic driver shift?", delay_minutes=0)
    settled_a = workflow.settle_outreach(utc_now() + timedelta(seconds=1))
    result_a = workflow.reply_and_assign(thread_a, "yes", Role.DRIVER)
    resolved_a = workflow.resolve_gap_if_staffed(gaps_a[0].id)

    gaps_b = workflow.staffing_event(EventKind.NO_SHOW, "shift-2", "demo-b-no-show")
    candidates_b = workflow.ranker.rank("shift-2", Role.DRIVER)
    thread_b = workflow.open_thread("shift-2", candidates_b[0].volunteer_id)
    result_b = workflow.reply_and_assign(thread_b, "can do but I need a ride", Role.DRIVER)
    resolved_b = workflow.resolve_gap_if_staffed(gaps_b[0].id)

    thread_c = workflow.open_thread("shift-3", "vol-09")
    result_c = workflow.reply_and_assign(thread_c, "I was injured and need to complain", Role.SORTER)

    output = {
        "scenario_a": {
            "settled_effects": settled_a,
            "confirmed": result_a["confirmed"],
            "gap_resolved": resolved_a,
            "human_interruptions": 0,
        },
        "scenario_b": {
            "intent": result_b["classification"].intent.value,
            "transport_found": bool(result_b["transport"]),
            "confirmed": result_b["confirmed"],
            "gap_resolved": resolved_b,
        },
        "scenario_c": {
            "intent": result_c["classification"].intent.value,
            "route": result_c["routing"].routing_class.value,
            "interrupt_id": result_c["interrupt"].id,
        },
    }
    for scenario, result in output.items():
        print(f"{scenario}: {result}")
    return 0 if resolved_a and resolved_b and output["scenario_c"]["route"] == "RED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
