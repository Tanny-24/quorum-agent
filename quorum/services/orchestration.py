"""Server-side deterministic orchestration for the local synthetic demo."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from quorum.data.loader import build_fixture
from quorum.domain.models import (
    Gap,
    GapStatus,
    RecoveryRun,
    RecoveryRunStatus,
    RecoveryRunStep,
    RecoveryStepStatus,
    ReplyIntent,
    Role,
    RoutingClass,
)
from quorum.events.models import EventKind
from quorum.persistence.memory import MemoryStore
from quorum.services.workflow import CoreWorkflow
from quorum.utils import stable_id, utc_now


EXECUTION_MODE = "deterministic_demo"
WORKSPACE_ID = "org:riverside"


@dataclass(frozen=True)
class DemoScenarioDefinition:
    id: str
    title: str
    description: str
    expected_route: RoutingClass
    expected_human_involvement: str
    shift_id: str
    trigger: EventKind


SCENARIOS = {
    "scenario-a": DemoScenarioDefinition(
        id="scenario-a",
        title="Autonomous Recovery",
        description="Detect a cancellation, rank eligible replacements, and restore staffing without interrupting a coordinator.",
        expected_route=RoutingClass.GREEN,
        expected_human_involvement="None expected",
        shift_id="shift-1",
        trigger=EventKind.VOLUNTEER_CANCELLED,
    ),
    "scenario-b": DemoScenarioDefinition(
        id="scenario-b",
        title="Conditional Transport",
        description="Process a conditional acceptance, resolve synthetic transport, and confirm the replacement safely.",
        expected_route=RoutingClass.YELLOW,
        expected_human_involvement="None expected",
        shift_id="shift-2",
        trigger=EventKind.VOLUNTEER_CANCELLED,
    ),
    "scenario-c": DemoScenarioDefinition(
        id="scenario-c",
        title="Safety Escalation",
        description="Route an injury and complaint through Layer-0 safety policy to a persistent human decision.",
        expected_route=RoutingClass.RED,
        expected_human_involvement="Coordinator decision required",
        shift_id="shift-3",
        trigger=EventKind.VOLUNTEER_CANCELLED,
    ),
}


class DemoOrchestrationService:
    """Compose the existing deterministic services into truthful demo runs."""

    def __init__(self, store: MemoryStore, *, attention_allowance: int = 2) -> None:
        self.store = store
        self.attention_allowance = attention_allowance
        self.workflow = CoreWorkflow(
            store,
            attention_allowance=attention_allowance,
        )

    def scenarios(self) -> list[DemoScenarioDefinition]:
        return list(SCENARIOS.values())

    def reset(self) -> dict[str, object]:
        organisations, sites, volunteers, shifts = build_fixture()
        runs_cleared = self.store.reset_synthetic(
            organisations,
            sites,
            volunteers,
            shifts,
        )
        self.store.get_budget("budget:riverside", self.attention_allowance)
        return {
            "status": "reset",
            "execution_mode": EXECUTION_MODE,
            "workspace_id": WORKSPACE_ID,
            "reset_at": utc_now(),
            "shifts_restored": len(shifts),
            "volunteers_restored": len(volunteers),
            "runs_cleared": runs_cleared,
        }

    def _save(self, run: RecoveryRun) -> None:
        self.store.update_recovery_run(run)

    def _step(
        self,
        run: RecoveryRun,
        step_type: str,
        label: str,
        summary: str,
        *,
        related_entity_id: str | None = None,
        status: RecoveryStepStatus = RecoveryStepStatus.COMPLETED,
    ) -> None:
        run.steps.append(
            RecoveryRunStep(
                id=stable_id("run-step", run.id, len(run.steps), step_type),
                step_type=step_type,
                label=label,
                status=status,
                timestamp=utc_now(),
                related_entity_id=related_entity_id,
                summary=summary,
            )
        )
        self._save(run)

    def _record_ranking(self, run: RecoveryRun, gap: Gap, candidate_id: str, count: int) -> None:
        self.workflow.ledger.record(
            "ranking",
            "CANDIDATES_RANKED",
            gap_id=gap.id,
            routing_class=RoutingClass.GREEN,
            reason="highest_eligible_score",
            details={
                "shift_id": gap.shift_id,
                "volunteer_id": candidate_id,
                "role": gap.role.value,
            },
            key=f"demo-ranking:{run.id}:{gap.id}:{gap.shortfall}",
        )
        self._step(
            run,
            "ranking",
            "Eligible candidates ranked",
            f"{count} eligible {gap.role.value} candidates were evaluated; the highest deterministic score was selected.",
            related_entity_id=candidate_id,
        )

    def _fill_gaps(self, run: RecoveryRun, gaps: list[Gap], *, conditional: bool) -> None:
        conditional_used = False
        for initial_gap in gaps:
            while True:
                gap = self.store.get_gap(initial_gap.id)
                if gap is None or gap.status == GapStatus.RESOLVED:
                    break
                candidates = self.workflow.ranker.rank(gap.shift_id, gap.role)
                if not candidates:
                    raise RuntimeError(f"No eligible candidates for {gap.role.value}")
                candidate = candidates[0]
                self._record_ranking(
                    run,
                    gap,
                    candidate.volunteer_id,
                    len(candidates),
                )
                thread = self.workflow.open_thread(
                    gap.shift_id,
                    candidate.volunteer_id,
                )
                self._step(
                    run,
                    "negotiation",
                    "Synthetic negotiation opened",
                    "A policy-eligible candidate entered the deterministic reply workflow.",
                    related_entity_id=thread.id,
                )
                pending = self.workflow.queue_outreach(
                    thread,
                    "Can you cover this synthetic Riverside shift?",
                    delay_minutes=0,
                )
                settled = self.workflow.settle_outreach(
                    utc_now() + timedelta(seconds=1)
                )
                if settled < 1:
                    raise RuntimeError("Synthetic outreach did not settle")
                self._step(
                    run,
                    "outreach",
                    "Synthetic outreach settled locally",
                    "The reversible outreach effect completed without contacting a real volunteer.",
                    related_entity_id=pending.id,
                )

                use_conditional = conditional and not conditional_used
                reply = (
                    "I can do it, but I need a ride."
                    if use_conditional
                    else "yes"
                )
                result = self.workflow.reply_and_assign(thread, reply, gap.role)
                classification = result["classification"]
                if not hasattr(classification, "intent"):
                    raise RuntimeError("Reply classifier returned no intent")
                route = (
                    RoutingClass.YELLOW
                    if classification.intent == ReplyIntent.ACCEPT_IF
                    else RoutingClass.GREEN
                )
                self.workflow.ledger.record(
                    "reply",
                    classification.intent.value,
                    routing_class=route,
                    reason=(
                        f"condition:{classification.condition}"
                        if classification.condition
                        else "deterministic_reply_classification"
                    ),
                    details={
                        "shift_id": gap.shift_id,
                        "thread_id": thread.id,
                        "volunteer_id": candidate.volunteer_id,
                    },
                    key=f"demo-reply:{run.id}:{thread.id}",
                )
                self._step(
                    run,
                    "reply",
                    "Volunteer response classified",
                    f"The deterministic classifier returned {classification.intent.value}.",
                    related_entity_id=thread.id,
                )

                transport = result.get("transport")
                if use_conditional:
                    conditional_used = True
                    if classification.intent != ReplyIntent.ACCEPT_IF:
                        raise RuntimeError("Conditional reply was not classified as ACCEPT_IF")
                    if classification.condition != "transport":
                        raise RuntimeError("Conditional reply did not canonicalize to transport")
                    if not isinstance(transport, dict) or not transport.get("available"):
                        raise RuntimeError("Synthetic transport was unavailable")
                    self.workflow.ledger.record(
                        "transport",
                        "CONDITION_RESOLVED",
                        routing_class=RoutingClass.GREEN,
                        reason="synthetic_transport_available",
                        details={
                            "shift_id": gap.shift_id,
                            "thread_id": thread.id,
                            "volunteer_id": candidate.volunteer_id,
                        },
                        key=f"demo-transport:{run.id}:{thread.id}",
                    )
                    self._step(
                        run,
                        "transport",
                        "Transport condition resolved",
                        str(transport["option"]),
                        related_entity_id=thread.id,
                    )

                if not result.get("confirmed"):
                    raise RuntimeError("Assignment was not confirmed")
                assignment = result.get("assignment")
                assignment_id = getattr(assignment, "id", None)
                self._step(
                    run,
                    "assignment",
                    "Assignment confirmed",
                    f"The {gap.role.value} assignment passed the backend capacity guard.",
                    related_entity_id=assignment_id,
                )
                updated_gap = self.store.get_gap(gap.id)
                if updated_gap and updated_gap.status == GapStatus.RESOLVED:
                    self.workflow.ledger.record(
                        "gap",
                        "RESOLVED",
                        gap_id=gap.id,
                        routing_class=RoutingClass.GREEN,
                        reason="required_capacity_restored",
                        details={"shift_id": gap.shift_id},
                        key=f"demo-gap-resolved:{run.id}:{gap.id}",
                    )
                    self._step(
                        run,
                        "gap_resolution",
                        f"{gap.role.value.title()} gap resolved",
                        "Confirmed assignments now meet the required role capacity.",
                        related_entity_id=gap.id,
                    )

    def run(self, scenario_id: str, idempotency_key: str) -> tuple[bool, RecoveryRun]:
        scenario = SCENARIOS.get(scenario_id)
        if scenario is None:
            raise KeyError(scenario_id)
        run_key = f"{scenario.id}:{idempotency_key}"
        budget = self.store.get_budget("budget:riverside", self.attention_allowance)
        run = RecoveryRun(
            id=stable_id("demo-run", run_key),
            idempotency_key=run_key,
            scenario_id=scenario.id,
            started_at=utc_now(),
            shift_id=scenario.shift_id,
            trigger=scenario.trigger.value,
            attention_spent_before=budget.spent,
            attention_spent_after=budget.spent,
        )
        created, stored = self.store.create_recovery_run(run)
        if not created:
            return True, stored
        run = stored
        open_interrupts_before = len(self.store.list_open_interrupts())
        try:
            gaps = self.workflow.staffing_event(
                scenario.trigger,
                scenario.shift_id,
                f"demo-event:{run.id}",
            )
            self._step(
                run,
                "event",
                "Cancellation recorded",
                "The synthetic VOLUNTEER_CANCELLED event was accepted by the idempotent event handler.",
                related_entity_id=scenario.shift_id,
            )
            self._step(
                run,
                "gap_detection",
                "Staffing gaps detected",
                f"The backend detected {len(gaps)} role-level staffing gaps.",
                related_entity_id=gaps[0].id if gaps else None,
            )

            if scenario.id == "scenario-c":
                driver_gap = next(
                    gap for gap in gaps if gap.role == Role.DRIVER
                )
                candidates = self.workflow.ranker.rank(
                    scenario.shift_id,
                    driver_gap.role,
                )
                candidate = candidates[0]
                self._record_ranking(
                    run,
                    driver_gap,
                    candidate.volunteer_id,
                    len(candidates),
                )
                thread = self.workflow.open_thread(
                    scenario.shift_id,
                    candidate.volunteer_id,
                )
                self._step(
                    run,
                    "negotiation",
                    "Synthetic negotiation opened",
                    "A candidate response entered the deterministic safety classifier.",
                    related_entity_id=thread.id,
                )
                result = self.workflow.reply_and_assign(
                    thread,
                    "I was injured and need to make a complaint.",
                    driver_gap.role,
                )
                classification = result["classification"]
                routing = result["routing"]
                interrupt = result["interrupt"]
                if classification.intent != ReplyIntent.OUT_OF_SCOPE:
                    raise RuntimeError("Safety reply was not OUT_OF_SCOPE")
                if routing.routing_class != RoutingClass.RED:
                    raise RuntimeError("Safety reply was not routed RED")
                persisted = self.store.get_interrupt(interrupt.id)
                if persisted is None:
                    raise RuntimeError("Human decision was not persisted")
                run.interrupt_id = persisted.id
                run.human_decision_required = True
                self._step(
                    run,
                    "safety",
                    "Layer-0 safety policy applied",
                    f"The deterministic classifier returned OUT_OF_SCOPE with safety reason {classification.safety_reason}.",
                    related_entity_id=thread.id,
                )
                self._step(
                    run,
                    "human_decision",
                    "Human decision required",
                    "QUORUM paused before consequential action and persisted a RED decision.",
                    related_entity_id=persisted.id,
                    status=RecoveryStepStatus.WAITING_FOR_HUMAN,
                )
                run.status = RecoveryRunStatus.WAITING_FOR_HUMAN
                run.outcome = "Paused safely for a coordinator decision"
            else:
                self._fill_gaps(
                    run,
                    list(gaps),
                    conditional=scenario.id == "scenario-b",
                )
                run.human_decision_required = (
                    len(self.store.list_open_interrupts())
                    > open_interrupts_before
                )
                if run.human_decision_required:
                    raise RuntimeError("Unexpected human decision was created")
                unresolved = [
                    gap
                    for gap in gaps
                    if not self.workflow.resolve_gap_if_staffed(gap.id)
                ]
                if unresolved:
                    raise RuntimeError("One or more staffing gaps remain unresolved")
                run.status = RecoveryRunStatus.COMPLETED
                run.outcome = "Shift fully staffed without human interruption"
            run.completed_at = utc_now()
            run.attention_spent_after = self.store.get_budget(
                "budget:riverside",
                self.attention_allowance,
            ).spent
            self._save(run)
        except Exception as exc:
            run.status = RecoveryRunStatus.FAILED
            run.completed_at = utc_now()
            run.error = f"Deterministic workflow failed ({type(exc).__name__})."
            run.outcome = "Workflow did not complete"
            run.attention_spent_after = self.store.get_budget(
                "budget:riverside",
                self.attention_allowance,
            ).spent
            self._step(
                run,
                "failure",
                "Workflow failed",
                run.error,
                status=RecoveryStepStatus.FAILED,
            )
            self._save(run)
        return False, self.store.get_recovery_run(run.id) or run
