"""Backend-owned joins and safe projections for product read APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from quorum.api.schemas import (
    AssignmentView,
    AttentionBudgetView,
    DashboardCounts,
    DashboardSummary,
    DecisionFeedPage,
    DecisionFeedItem,
    GapSummary,
    HumanDecisionDetail,
    HumanDecisionEvidence,
    HumanDecisionResolution,
    HumanDecisionSummary,
    InterruptCompactView,
    PendingEffectCompactView,
    RankedCandidateView,
    RelatedNegotiationView,
    RelatedShiftView,
    RecoveryRunDetail,
    RecoveryRunStepView,
    RoleCoverage,
    ShiftDetail,
    ShiftOperationalStatus,
    ShiftSummary,
    VolunteerCompactView,
    VolunteerAssignmentView,
    VolunteerDetailView,
    VolunteerOperationalStatus,
    VolunteerSummaryView,
)
from quorum.domain.models import (
    Gap,
    GapStatus,
    HumanDecisionAction,
    InterruptRecord,
    InterruptStatus,
    LedgerEntry,
    NegotiationThread,
    PendingEffect,
    PendingStatus,
    RecoveryRun,
    Role,
    RoutingClass,
    Shift,
    TERMINAL_GAP_STATUSES,
)
from quorum.persistence.memory import MemoryStore
from quorum.services.candidate_ranker import CandidateRanker
from quorum.services.interrupts import InterruptService
from quorum.services.orchestration import SCENARIOS
from quorum.utils import utc_now


RECOVERY_GAP_STATUSES = {
    GapStatus.ANALYZING,
    GapStatus.SEARCHING,
    GapStatus.CONTACTING,
    GapStatus.AWAITING,
    GapStatus.ESCALATION_REQUIRED,
    GapStatus.WAITING_FOR_HUMAN,
    GapStatus.RESUMING,
}
ACTIVE_PENDING_STATUSES = {PendingStatus.PENDING, PendingStatus.SETTLING}


def _safe_identifier(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


class ReadModelService:
    """Build UI views without moving deterministic calculations to clients."""

    def __init__(
        self,
        store: MemoryStore,
        *,
        attention_budget_id: str = "budget:riverside",
        attention_allowance: int = 2,
    ) -> None:
        self.store = store
        self.attention_budget_id = attention_budget_id
        self.attention_allowance = attention_allowance
        self.ranker = CandidateRanker(store)
        self.interrupt_service = InterruptService(store)

    def attention_budget(self) -> AttentionBudgetView:
        budget = self.store.get_budget(
            self.attention_budget_id, self.attention_allowance
        )
        return AttentionBudgetView(
            allowance=budget.allowance,
            spent=budget.spent,
            remaining=max(0, budget.allowance - budget.spent),
            overrides=budget.overrides,
        )

    @staticmethod
    def gap_summary(gap: Gap) -> GapSummary:
        return GapSummary(
            gap_id=gap.id,
            role=gap.role,
            shortfall=gap.shortfall,
            status=gap.status,
            detected_at=gap.detected_at,
        )

    def related_shift(self, shift_id: str | None) -> RelatedShiftView | None:
        if not shift_id:
            return None
        shift = self.store.get_shift(shift_id)
        if shift is None:
            return None
        site = self.store.get_site(shift.site_id)
        return RelatedShiftView(
            shift_id=shift.id,
            site_id=shift.site_id,
            site_name=site.name if site else "Unknown site",
            starts_at=shift.starts_at,
            ends_at=shift.ends_at,
        )

    def _active_gaps(self, shift_id: str | None = None) -> list[Gap]:
        return [
            gap
            for gap in self.store.list_gaps()
            if gap.status not in TERMINAL_GAP_STATUSES
            and (shift_id is None or gap.shift_id == shift_id)
        ]

    def shift_summary(self, shift: Shift) -> ShiftSummary:
        site = self.store.get_site(shift.site_id)
        assignments = self.store.list_assignments(shift.id)
        coverage = [
            RoleCoverage(
                role=role,
                required=required,
                assigned=sum(1 for item in assignments if item.role == role),
                shortfall=max(
                    0,
                    required
                    - sum(1 for item in assignments if item.role == role),
                ),
            )
            for role, required in sorted(
                shift.required_by_role.items(), key=lambda item: item[0].value
            )
        ]
        active_gaps = sorted(
            self._active_gaps(shift.id), key=lambda item: (item.role.value, item.id)
        )
        if any(gap.status in RECOVERY_GAP_STATUSES for gap in active_gaps):
            status = ShiftOperationalStatus.RECOVERING
        elif active_gaps:
            status = ShiftOperationalStatus.NEEDS_COVERAGE
        elif all(item.shortfall == 0 for item in coverage):
            status = ShiftOperationalStatus.FULLY_STAFFED
        else:
            status = ShiftOperationalStatus.SCHEDULED
        return ShiftSummary(
            shift_id=shift.id,
            site_id=shift.site_id,
            site_name=site.name if site else "Unknown site",
            starts_at=shift.starts_at,
            ends_at=shift.ends_at,
            coverage=coverage,
            gap_count=len(active_gaps),
            gap_statuses=sorted(
                {gap.status for gap in active_gaps}, key=lambda item: item.value
            ),
            status=status,
        )

    def shift_summaries(self) -> list[ShiftSummary]:
        return [
            self.shift_summary(shift)
            for shift in sorted(
                self.store.list_shifts(), key=lambda item: (item.starts_at, item.id)
            )
        ]

    def _thread_context(
        self, thread_id: str | None
    ) -> tuple[str | None, str | None]:
        if not thread_id:
            return None, None
        thread = self.store.get_negotiation(thread_id)
        if not thread:
            return None, None
        return thread.shift_id, thread.volunteer_id

    def pending_view(self, item: PendingEffect) -> PendingEffectCompactView:
        thread_id = _safe_identifier(item.payload.get("thread_id"))
        shift_id = _safe_identifier(item.payload.get("shift_id"))
        volunteer_id = _safe_identifier(item.payload.get("volunteer_id"))
        thread_shift_id, thread_volunteer_id = self._thread_context(thread_id)
        descriptions = {
            "send_message": "Send queued volunteer message",
            "confirm_assignment": "Confirm volunteer assignment",
            "widen_search": "Expand candidate search",
        }
        related_shift = self.related_shift(shift_id or thread_shift_id)
        result_summary = None
        failure_summary = None
        if item.status == PendingStatus.SETTLED:
            if isinstance(item.result, dict) and item.result.get("sent") is False:
                result_summary = "Duplicate operation was safely suppressed"
            else:
                result_summary = "Effect completed successfully"
        elif item.status == PendingStatus.FAILED:
            error_type = (
                item.result.get("error") if isinstance(item.result, dict) else None
            )
            failure_summary = (
                f"Effect failed ({error_type})"
                if isinstance(error_type, str) and error_type
                else "Effect failed before completion"
            )
        can_cancel = item.status == PendingStatus.PENDING
        return PendingEffectCompactView(
            effect_id=item.id,
            pending_id=item.id,
            effect_type=item.effect_type,
            description=descriptions.get(item.effect_type, "Queued operation"),
            status=item.status,
            created_at=item.created_at,
            settle_at=item.settle_at,
            updated_at=item.updated_at,
            settled_at=(
                item.updated_at if item.status == PendingStatus.SETTLED else None
            ),
            can_cancel=can_cancel,
            cancellable=can_cancel,
            shift_id=related_shift.shift_id if related_shift else None,
            volunteer_id=volunteer_id or thread_volunteer_id,
            thread_id=thread_id,
            related_shift=related_shift,
            result_summary=result_summary,
            failure_summary=failure_summary,
        )

    def pending_effects(
        self, status: PendingStatus | None = None
    ) -> list[PendingEffectCompactView]:
        items = self.store.list_pending()
        if status is not None:
            items = [item for item in items if item.status == status]
        return [
            self.pending_view(item)
            for item in sorted(items, key=lambda item: (item.created_at, item.id), reverse=True)
        ]

    def _interrupt_context(
        self, item: InterruptRecord
    ) -> tuple[
        dict[str, Any],
        dict[str, Any],
        dict[str, Any],
        str | None,
        str | None,
        NegotiationThread | None,
    ]:
        reason = item.reason if isinstance(item.reason, dict) else {}
        classification = reason.get("classification")
        routing = reason.get("routing")
        inputs = reason.get("inputs")
        classification = classification if isinstance(classification, dict) else {}
        routing = routing if isinstance(routing, dict) else {}
        inputs = inputs if isinstance(inputs, dict) else {}
        safety_reason = _safe_identifier(classification.get("safety_reason"))
        if safety_reason is None:
            safety_reason = _safe_identifier(inputs.get("safety_category"))
        routing_reason = _safe_identifier(routing.get("reason"))
        shift_id = _safe_identifier(inputs.get("shift_id"))
        volunteer_id = _safe_identifier(inputs.get("volunteer_id"))
        negotiation = None
        for thread in self.store.list_negotiations():
            if thread.session_id == item.session_id:
                negotiation = thread
                shift_id = shift_id or thread.shift_id
                volunteer_id = volunteer_id or thread.volunteer_id
                break
        return (
            reason,
            classification,
            routing,
            shift_id,
            volunteer_id,
            negotiation,
        )

    def interrupt_view(self, item: InterruptRecord) -> InterruptCompactView:
        (
            _,
            _,
            routing,
            shift_id,
            volunteer_id,
            _,
        ) = self._interrupt_context(item)
        safety_reason = _safe_identifier(
            (
                item.reason.get("classification", {})
                if isinstance(item.reason.get("classification"), dict)
                else {}
            ).get("safety_reason")
        )
        if safety_reason is None:
            inputs = item.reason.get("inputs", {})
            if isinstance(inputs, dict):
                safety_reason = _safe_identifier(inputs.get("safety_category"))
        routing_reason = _safe_identifier(routing.get("reason"))
        title = (
            f"{safety_reason.replace('_', ' ').title()} requires human review"
            if safety_reason
            else "Human decision required"
        )
        return InterruptCompactView(
            interrupt_id=item.id,
            status=item.status,
            title=title,
            created_at=item.created_at,
            safety_reason=safety_reason,
            routing_reason=routing_reason,
            shift_id=shift_id,
            volunteer_id=volunteer_id,
            attention_spent=bool(routing.get("budget_spent", False)),
            attention_override=bool(routing.get("budget_override", False)),
        )

    @staticmethod
    def _decision_action(item: InterruptRecord) -> HumanDecisionAction | None:
        normalized = (item.decision or "").upper()
        if normalized in {"APPROVE", "APPROVED"}:
            return HumanDecisionAction.APPROVE
        if normalized in {"VETO", "VETOED"}:
            return HumanDecisionAction.VETO
        return None

    def human_decision_summary(
        self, item: InterruptRecord
    ) -> HumanDecisionSummary:
        (
            reason_payload,
            classification,
            routing,
            shift_id,
            volunteer_id,
            _,
        ) = self._interrupt_context(item)
        safety_reason = _safe_identifier(classification.get("safety_reason"))
        inputs = reason_payload.get("inputs")
        inputs = inputs if isinstance(inputs, dict) else {}
        safety_reason = safety_reason or _safe_identifier(inputs.get("safety_category"))
        routing_reason = _safe_identifier(routing.get("reason"))
        if safety_reason:
            title = f"{safety_reason.replace('_', ' ').title()} requires human review"
            explanation = (
                f"Layer-0 safety policy identified {safety_reason.replace('_', ' ')}."
            )
        elif routing_reason:
            title = "Consequential action requires human review"
            explanation = routing_reason.replace("_", " ").capitalize() + "."
        else:
            title = "Human decision required"
            explanation = "QUORUM paused before a consequential action."
        volunteer = self.store.get_volunteer(volunteer_id) if volunteer_id else None
        return HumanDecisionSummary(
            interrupt_id=item.id,
            status=item.status,
            title=title,
            reason=explanation,
            created_at=item.created_at,
            resolved_at=item.resolved_at,
            safety_reason=safety_reason,
            routing_reason=routing_reason,
            shift=self.related_shift(shift_id),
            volunteer=(
                VolunteerCompactView(
                    volunteer_id=volunteer.id,
                    display_name=volunteer.display_name,
                )
                if volunteer
                else None
            ),
            attention_spent=bool(routing.get("budget_spent", False)),
            attention_override=bool(routing.get("budget_override", False)),
            allowed_actions=self.interrupt_service.allowed_actions(item),
            version=item.version,
        )

    def human_decision_detail(
        self, interrupt_id: str
    ) -> HumanDecisionDetail | None:
        item = self.store.get_interrupt(interrupt_id)
        if item is None:
            return None
        summary = self.human_decision_summary(item)
        (
            reason_payload,
            _,
            _,
            _,
            _,
            negotiation,
        ) = self._interrupt_context(item)
        evidence: list[HumanDecisionEvidence] = []
        if summary.safety_reason:
            evidence.append(
                HumanDecisionEvidence(
                    label="Safety signal",
                    value=summary.safety_reason.replace("_", " ").capitalize(),
                )
            )
        if summary.routing_reason:
            evidence.append(
                HumanDecisionEvidence(
                    label="Routing basis",
                    value=summary.routing_reason.replace("_", " ").capitalize(),
                )
            )
        tool_name = _safe_identifier(reason_payload.get("tool"))
        if tool_name:
            evidence.append(
                HumanDecisionEvidence(
                    label="Paused action",
                    value=tool_name.replace("_", " ").capitalize(),
                )
            )
        if summary.attention_override:
            evidence.append(
                HumanDecisionEvidence(
                    label="Attention Budget",
                    value="Layer-0 safety override applied",
                )
            )
        elif summary.attention_spent:
            evidence.append(
                HumanDecisionEvidence(
                    label="Attention Budget",
                    value="One interruption was spent",
                )
            )
        action = self._decision_action(item)
        resolution = None
        if (
            action
            and item.resolved_at
            and item.decision_actor
            and item.resolution_outcome
        ):
            resolution = HumanDecisionResolution(
                action=action,
                note=item.decision_note,
                actor=item.decision_actor,
                outcome=item.resolution_outcome,
                automatic_continuation=item.resolution_outcome
                == "workflow_resumed",
                resolved_at=item.resolved_at,
            )
        return HumanDecisionDetail(
            **summary.model_dump(),
            negotiation=(
                RelatedNegotiationView(
                    thread_id=negotiation.id,
                    status=negotiation.status,
                )
                if negotiation
                else None
            ),
            evidence=evidence,
            resolution=resolution,
        )

    def human_decisions(
        self, status: InterruptStatus | None = None
    ) -> list[HumanDecisionSummary]:
        items = self.store.list_interrupts(status)
        items.sort(
            key=lambda item: (
                item.status == InterruptStatus.OPEN,
                item.created_at,
                item.id,
            ),
            reverse=True,
        )
        return [self.human_decision_summary(item) for item in items]

    def open_interrupts(self) -> list[InterruptCompactView]:
        return [
            self.interrupt_view(item)
            for item in sorted(
                self.store.list_open_interrupts(),
                key=lambda item: (item.created_at, item.id),
                reverse=True,
            )
        ]

    def _ledger_shift_id(self, item: LedgerEntry) -> str | None:
        shift_id = _safe_identifier(item.details.get("shift_id"))
        if shift_id:
            return shift_id
        if item.gap_id:
            gap = self.store.get_gap(item.gap_id)
            if gap:
                return gap.shift_id
        assignment_id = _safe_identifier(item.details.get("assignment_id"))
        if assignment_id:
            assignment = self.store.get_assignment(assignment_id)
            if assignment:
                return assignment.shift_id
        thread_id = _safe_identifier(item.details.get("thread_id"))
        thread_shift_id, _ = self._thread_context(thread_id)
        if thread_shift_id:
            return thread_shift_id
        pending_id = _safe_identifier(item.details.get("pending_id"))
        if pending_id:
            pending = self.store.get_pending(pending_id)
            if pending:
                return self.pending_view(pending).shift_id
        interrupt_id = _safe_identifier(item.details.get("interrupt_id"))
        if interrupt_id:
            interrupt = self.store.get_interrupt(interrupt_id)
            if interrupt:
                return self.interrupt_view(interrupt).shift_id
        return None

    def decision_feed_item(self, item: LedgerEntry) -> DecisionFeedItem:
        decision_label = item.decision.replace("_", " ").lower()
        category_label = item.category.replace("_", " ").title()
        shift_id = self._ledger_shift_id(item)
        related_shift = self.related_shift(shift_id)
        interrupt_id = _safe_identifier(item.details.get("interrupt_id"))
        pending_id = _safe_identifier(item.details.get("pending_id"))
        attention_effect = None
        if interrupt_id:
            interrupt = self.store.get_interrupt(interrupt_id)
            if interrupt:
                view = self.interrupt_view(interrupt)
                if view.attention_override:
                    attention_effect = "SAFETY_OVERRIDE"
                elif view.attention_spent:
                    attention_effect = "SPENT"
        return DecisionFeedItem(
            id=item.id,
            entry_id=item.id,
            timestamp=item.timestamp,
            category=item.category,
            decision=item.decision,
            summary=f"{category_label}: {decision_label}",
            title=decision_label.capitalize(),
            route=item.routing_class,
            routing_class=item.routing_class,
            reason=item.reason,
            event_id=item.event_id,
            gap_id=item.gap_id,
            shift_id=shift_id,
            shift_name=related_shift.site_name if related_shift else None,
            interrupt_id=interrupt_id,
            pending_id=pending_id,
            attention_effect=attention_effect,
            ev_score=item.ev_score,
            ev_threshold=item.ev_inputs.get("threshold"),
        )

    def recovery_run_detail(self, run: RecoveryRun) -> RecoveryRunDetail:
        scenario = SCENARIOS.get(run.scenario_id)
        return RecoveryRunDetail(
            run_id=run.id,
            scenario_id=run.scenario_id,
            scenario_title=scenario.title if scenario else "Synthetic recovery",
            status=run.status,
            started_at=run.started_at,
            completed_at=run.completed_at,
            shift_id=run.shift_id,
            trigger=run.trigger,
            steps=[
                RecoveryRunStepView(
                    step_id=step.id,
                    step_type=step.step_type,
                    label=step.label,
                    status=step.status,
                    timestamp=step.timestamp,
                    related_entity_id=step.related_entity_id,
                    summary=step.summary,
                )
                for step in run.steps
            ],
            outcome=run.outcome,
            human_decision_required=run.human_decision_required,
            interrupt_id=run.interrupt_id,
            attention_budget_before=run.attention_spent_before,
            attention_budget_after=run.attention_spent_after,
            attention_budget_delta=max(
                0,
                run.attention_spent_after - run.attention_spent_before,
            ),
            final_shift=(
                self.shift_summary(shift)
                if (shift := self.store.get_shift(run.shift_id))
                else None
            ),
            error=run.error,
        )

    def recovery_runs(self) -> list[RecoveryRunDetail]:
        return [
            self.recovery_run_detail(run)
            for run in sorted(
                self.store.list_recovery_runs(),
                key=lambda item: (item.started_at, item.id),
                reverse=True,
            )
        ]

    def volunteer_summary(self, volunteer) -> VolunteerSummaryView:
        available_shifts = [
            shift
            for shift in self.store.list_shifts()
            if shift.id in volunteer.available_shift_ids
        ]
        assignments = self.store.list_assignments_for_volunteer(volunteer.id)
        constraints = []
        if volunteer.needs_transport:
            constraints.append("Transport coordination may be needed")
        return VolunteerSummaryView(
            volunteer_id=volunteer.id,
            display_name=volunteer.display_name,
            roles=sorted(volunteer.roles, key=lambda item: item.value),
            status=(
                VolunteerOperationalStatus.ACTIVE
                if volunteer.active
                else VolunteerOperationalStatus.INACTIVE
            ),
            available_shift_count=len(available_shifts),
            availability_summary=(
                f"Available for {len(available_shifts)} synthetic shift"
                f"{'s' if len(available_shifts) != 1 else ''}"
            ),
            current_assignment_count=len(assignments),
            constraints=constraints,
        )

    def volunteer_summaries(
        self,
        *,
        role: Role | None = None,
        status: VolunteerOperationalStatus | None = None,
        available: bool | None = None,
    ) -> list[VolunteerSummaryView]:
        items = [self.volunteer_summary(item) for item in self.store.list_volunteers()]
        if role is not None:
            items = [item for item in items if role in item.roles]
        if status is not None:
            items = [item for item in items if item.status == status]
        if available is not None:
            items = [
                item
                for item in items
                if (item.available_shift_count > 0) == available
            ]
        return sorted(items, key=lambda item: (item.display_name, item.volunteer_id))

    def _ledger_volunteer_id(self, item: LedgerEntry) -> str | None:
        volunteer_id = _safe_identifier(item.details.get("volunteer_id"))
        if volunteer_id:
            return volunteer_id
        assignment_id = _safe_identifier(item.details.get("assignment_id"))
        if assignment_id:
            assignment = self.store.get_assignment(assignment_id)
            if assignment:
                return assignment.volunteer_id
        thread_id = _safe_identifier(item.details.get("thread_id"))
        if thread_id:
            thread = self.store.get_negotiation(thread_id)
            if thread:
                return thread.volunteer_id
        return None

    def volunteer_detail(self, volunteer_id: str) -> VolunteerDetailView | None:
        volunteer = self.store.get_volunteer(volunteer_id)
        if volunteer is None:
            return None
        summary = self.volunteer_summary(volunteer)
        available_shifts = [
            view
            for shift_id in sorted(volunteer.available_shift_ids)
            if (view := self.related_shift(shift_id)) is not None
        ]
        assignments = []
        for assignment in sorted(
            self.store.list_assignments_for_volunteer(volunteer.id),
            key=lambda item: (item.confirmed_at, item.id),
            reverse=True,
        ):
            shift = self.related_shift(assignment.shift_id)
            if shift:
                assignments.append(
                    VolunteerAssignmentView(
                        assignment_id=assignment.id,
                        role=assignment.role,
                        confirmed_at=assignment.confirmed_at,
                        shift=shift,
                    )
                )
        activity = [
            self.decision_feed_item(entry)
            for entry in sorted(
                self.store.list_ledger(),
                key=lambda item: (item.timestamp, item.id),
                reverse=True,
            )
            if self._ledger_volunteer_id(entry) == volunteer.id
        ][:8]
        return VolunteerDetailView(
            **summary.model_dump(),
            available_shifts=available_shifts,
            assignments=assignments,
            recent_activity=activity,
        )

    def decision_feed_page(
        self,
        *,
        route: RoutingClass | None = None,
        category: str | None = None,
        shift_id: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> DecisionFeedPage:
        entries = sorted(
            self.store.list_ledger(),
            key=lambda item: (item.timestamp, item.id),
            reverse=True,
        )
        projected = [self.decision_feed_item(item) for item in entries]
        if route is not None:
            projected = [item for item in projected if item.route == route]
        if category is not None:
            projected = [item for item in projected if item.category == category]
        if shift_id is not None:
            projected = [item for item in projected if item.shift_id == shift_id]
        start = 0
        if cursor is not None:
            try:
                start = next(
                    index + 1
                    for index, item in enumerate(projected)
                    if item.id == cursor
                )
            except StopIteration as exc:
                raise ValueError("invalid_cursor") from exc
        page = projected[start : start + limit]
        has_more = start + limit < len(projected)
        return DecisionFeedPage(
            items=page,
            next_cursor=page[-1].id if has_more and page else None,
            has_more=has_more,
        )

    def recent_activity(
        self, *, limit: int = 8, shift_id: str | None = None
    ) -> list[DecisionFeedItem]:
        entries = sorted(
            self.store.list_ledger(),
            key=lambda item: (item.timestamp, item.id),
            reverse=True,
        )
        projected = [self.decision_feed_item(item) for item in entries]
        if shift_id is not None:
            projected = [item for item in projected if item.shift_id == shift_id]
        return projected[:limit]

    def shift_detail(self, shift_id: str) -> ShiftDetail | None:
        shift = self.store.get_shift(shift_id)
        if shift is None:
            return None
        summary = self.shift_summary(shift)
        assignments = []
        for assignment in sorted(
            self.store.list_assignments(shift_id),
            key=lambda item: (item.confirmed_at, item.id),
        ):
            volunteer = self.store.get_volunteer(assignment.volunteer_id)
            assignments.append(
                AssignmentView(
                    assignment_id=assignment.id,
                    volunteer=VolunteerCompactView(
                        volunteer_id=assignment.volunteer_id,
                        display_name=(
                            volunteer.display_name if volunteer else "Unknown volunteer"
                        ),
                    ),
                    role=assignment.role,
                    confirmed_at=assignment.confirmed_at,
                )
            )

        candidates: list[RankedCandidateView] = []
        for role in sorted(shift.required_by_role, key=lambda item: item.value):
            for candidate in self.ranker.rank(shift_id, Role(role))[:5]:
                volunteer = self.store.get_volunteer(candidate.volunteer_id)
                if volunteer is None:
                    continue
                candidates.append(
                    RankedCandidateView(
                        volunteer=VolunteerCompactView(
                            volunteer_id=volunteer.id,
                            display_name=volunteer.display_name,
                        ),
                        role=Role(role),
                        score=candidate.score,
                        breakdown=candidate.breakdown,
                        needs_transport=volunteer.needs_transport,
                    )
                )

        pending = [
            item
            for item in self.pending_effects()
            if item.shift_id == shift_id
        ]
        interrupts = [
            item for item in self.open_interrupts() if item.shift_id == shift_id
        ]
        return ShiftDetail(
            **summary.model_dump(),
            organisation_id=shift.organisation_id,
            assignments=assignments,
            gaps=[
                self.gap_summary(gap)
                for gap in sorted(
                    self._active_gaps(shift_id),
                    key=lambda item: (item.role.value, item.id),
                )
            ],
            ranked_candidates=candidates,
            pending_effects=pending,
            needs_attention=interrupts,
            recent_activity=self.recent_activity(limit=10, shift_id=shift_id),
        )

    def dashboard(self, now: datetime | None = None) -> DashboardSummary:
        open_gaps = self._active_gaps()
        active_recoveries = [
            gap for gap in open_gaps if gap.status in RECOVERY_GAP_STATUSES
        ]
        pending = [
            item
            for item in self.store.list_pending()
            if item.status in ACTIVE_PENDING_STATUSES
        ]
        interrupts = self.open_interrupts()
        active_shift_ids = {gap.shift_id for gap in open_gaps}
        active_operations = [
            summary
            for summary in self.shift_summaries()
            if summary.shift_id in active_shift_ids
        ]
        return DashboardSummary(
            generated_at=now or utc_now(),
            attention_budget=self.attention_budget(),
            counts=DashboardCounts(
                total_shifts=len(self.store.list_shifts()),
                open_gaps=len(open_gaps),
                active_recoveries=len(active_recoveries),
                pending_effects=len(pending),
                human_decisions_required=len(interrupts),
            ),
            needs_attention=interrupts[:5],
            active_operations=active_operations[:5],
            recent_activity=self.recent_activity(limit=8),
        )
