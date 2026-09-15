"""Safe, explicit response contracts for the QUORUM product UI."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from quorum.domain.models import (
    GapStatus,
    HumanDecisionAction,
    InterruptStatus,
    NegotiationStatus,
    PendingStatus,
    RecoveryRunStatus,
    RecoveryStepStatus,
    Role,
    RoutingClass,
)


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


class AttentionBudgetView(BaseModel):
    allowance: int = Field(ge=0)
    spent: int = Field(ge=0)
    remaining: int = Field(ge=0)
    overrides: int = Field(ge=0)


class DashboardCounts(BaseModel):
    total_shifts: int = Field(ge=0)
    open_gaps: int = Field(ge=0)
    active_recoveries: int = Field(ge=0)
    pending_effects: int = Field(ge=0)
    human_decisions_required: int = Field(ge=0)


class ShiftOperationalStatus(StrEnum):
    SCHEDULED = "SCHEDULED"
    NEEDS_COVERAGE = "NEEDS_COVERAGE"
    RECOVERING = "RECOVERING"
    FULLY_STAFFED = "FULLY_STAFFED"


class RoleCoverage(BaseModel):
    role: Role
    required: int = Field(ge=0)
    assigned: int = Field(ge=0)
    shortfall: int = Field(ge=0)


class GapSummary(BaseModel):
    gap_id: str
    role: Role
    shortfall: int = Field(ge=0)
    status: GapStatus
    detected_at: datetime


class VolunteerCompactView(BaseModel):
    volunteer_id: str
    display_name: str


class VolunteerOperationalStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class RelatedShiftView(BaseModel):
    shift_id: str
    site_id: str
    site_name: str
    starts_at: datetime
    ends_at: datetime


class RelatedNegotiationView(BaseModel):
    thread_id: str
    status: NegotiationStatus


class HumanDecisionEvidence(BaseModel):
    label: str
    value: str


class AssignmentView(BaseModel):
    assignment_id: str
    volunteer: VolunteerCompactView
    role: Role
    confirmed_at: datetime


class RankedCandidateView(BaseModel):
    volunteer: VolunteerCompactView
    role: Role
    score: float
    breakdown: dict[str, float]
    needs_transport: bool


class InterruptCompactView(BaseModel):
    interrupt_id: str
    status: InterruptStatus
    title: str
    created_at: datetime
    routing_class: RoutingClass = RoutingClass.RED
    safety_reason: str | None = None
    routing_reason: str | None = None
    shift_id: str | None = None
    volunteer_id: str | None = None
    attention_spent: bool = False
    attention_override: bool = False


class HumanDecisionResolution(BaseModel):
    action: HumanDecisionAction
    note: str | None = None
    actor: str
    outcome: str
    automatic_continuation: bool
    resolved_at: datetime


class HumanDecisionSummary(BaseModel):
    interrupt_id: str
    status: InterruptStatus
    title: str
    reason: str
    route: RoutingClass = RoutingClass.RED
    created_at: datetime
    resolved_at: datetime | None = None
    safety_reason: str | None = None
    routing_reason: str | None = None
    shift: RelatedShiftView | None = None
    volunteer: VolunteerCompactView | None = None
    attention_spent: bool = False
    attention_override: bool = False
    allowed_actions: list[HumanDecisionAction]
    version: int = Field(ge=1)


class HumanDecisionDetail(HumanDecisionSummary):
    negotiation: RelatedNegotiationView | None = None
    evidence: list[HumanDecisionEvidence]
    resolution: HumanDecisionResolution | None = None


class ResolveInterruptRequest(BaseModel):
    action: HumanDecisionAction | None = None
    decision: Literal["approved", "vetoed"] | None = Field(
        default=None,
        exclude=True,
        description="Legacy enum-limited alias retained for Phase 1 clients.",
    )
    note: str | None = Field(default=None, max_length=1000)
    actor: Literal["demo-coordinator"] = "demo-coordinator"
    expected_version: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def require_one_action(self) -> "ResolveInterruptRequest":
        if (self.action is None) == (self.decision is None):
            raise ValueError("Provide exactly one typed decision action")
        return self

    def effective_action(self) -> HumanDecisionAction:
        if self.action is not None:
            return self.action
        return (
            HumanDecisionAction.APPROVE
            if self.decision == "approved"
            else HumanDecisionAction.VETO
        )


class ResolveInterruptResponse(BaseModel):
    resolved: bool
    outcome: str
    automatic_continuation: bool
    decision: HumanDecisionDetail


class PendingEffectCompactView(BaseModel):
    effect_id: str
    pending_id: str
    effect_type: str
    description: str
    status: PendingStatus
    created_at: datetime
    settle_at: datetime
    updated_at: datetime
    settled_at: datetime | None = None
    can_cancel: bool
    cancellable: bool
    shift_id: str | None = None
    volunteer_id: str | None = None
    thread_id: str | None = None
    related_shift: RelatedShiftView | None = None
    result_summary: str | None = None
    failure_summary: str | None = None


class CancelPendingEffectRequest(BaseModel):
    actor: Literal["demo-coordinator"] = "demo-coordinator"
    expected_status: Literal[PendingStatus.PENDING] = PendingStatus.PENDING


class CancelPendingEffectResponse(BaseModel):
    cancelled: bool
    reason: str


class DecisionFeedItem(BaseModel):
    id: str
    entry_id: str
    timestamp: datetime
    category: str
    decision: str
    summary: str
    title: str
    route: RoutingClass | None = None
    routing_class: RoutingClass | None = None
    reason: str | None = None
    event_id: str | None = None
    gap_id: str | None = None
    shift_id: str | None = None
    shift_name: str | None = None
    interrupt_id: str | None = None
    pending_id: str | None = None
    attention_effect: Literal["SPENT", "SAFETY_OVERRIDE"] | None = None
    ev_score: float | None = None
    ev_threshold: float | None = None


class DecisionFeedPage(BaseModel):
    items: list[DecisionFeedItem]
    next_cursor: str | None = None
    has_more: bool


class DemoScenarioView(BaseModel):
    id: str
    title: str
    description: str
    expected_route: RoutingClass
    expected_human_involvement: str
    execution_mode: Literal["deterministic_demo"] = "deterministic_demo"


class RecoveryRunStepView(BaseModel):
    step_id: str
    step_type: str
    label: str
    status: RecoveryStepStatus
    timestamp: datetime
    related_entity_id: str | None = None
    summary: str


class RecoveryRunDetail(BaseModel):
    run_id: str
    scenario_id: str
    scenario_title: str
    execution_mode: Literal["deterministic_demo"] = "deterministic_demo"
    status: RecoveryRunStatus
    started_at: datetime
    completed_at: datetime | None = None
    shift_id: str
    trigger: str
    steps: list[RecoveryRunStepView]
    outcome: str | None = None
    human_decision_required: bool
    interrupt_id: str | None = None
    attention_budget_before: int = Field(ge=0)
    attention_budget_after: int = Field(ge=0)
    attention_budget_delta: int = Field(ge=0)
    final_shift: ShiftSummary | None = None
    error: str | None = None


class RunDemoScenarioRequest(BaseModel):
    idempotency_key: str = Field(min_length=8, max_length=120)
    execution_mode: Literal["deterministic_demo"] = "deterministic_demo"


class RunDemoScenarioResponse(BaseModel):
    duplicate: bool
    run: RecoveryRunDetail


class DemoResetResponse(BaseModel):
    status: Literal["reset"]
    execution_mode: Literal["deterministic_demo"]
    workspace_id: Literal["org:riverside"]
    reset_at: datetime
    shifts_restored: int = Field(ge=0)
    volunteers_restored: int = Field(ge=0)
    runs_cleared: int = Field(ge=0)


class VolunteerSummaryView(BaseModel):
    volunteer_id: str
    display_name: str
    roles: list[Role]
    status: VolunteerOperationalStatus
    available_shift_count: int = Field(ge=0)
    availability_summary: str
    current_assignment_count: int = Field(ge=0)
    constraints: list[str]


class VolunteerAssignmentView(BaseModel):
    assignment_id: str
    role: Role
    confirmed_at: datetime
    shift: RelatedShiftView


class VolunteerDetailView(VolunteerSummaryView):
    available_shifts: list[RelatedShiftView]
    assignments: list[VolunteerAssignmentView]
    recent_activity: list[DecisionFeedItem]
    contact_load_summary: Literal["Not yet tracked"] = "Not yet tracked"


class ShiftSummary(BaseModel):
    shift_id: str
    site_id: str
    site_name: str
    starts_at: datetime
    ends_at: datetime
    coverage: list[RoleCoverage]
    gap_count: int = Field(ge=0)
    gap_statuses: list[GapStatus]
    status: ShiftOperationalStatus


class ShiftDetail(ShiftSummary):
    organisation_id: str
    assignments: list[AssignmentView]
    gaps: list[GapSummary]
    ranked_candidates: list[RankedCandidateView]
    pending_effects: list[PendingEffectCompactView]
    needs_attention: list[InterruptCompactView]
    recent_activity: list[DecisionFeedItem]


class DashboardSummary(BaseModel):
    generated_at: datetime
    attention_budget: AttentionBudgetView
    counts: DashboardCounts
    needs_attention: list[InterruptCompactView]
    active_operations: list[ShiftSummary]
    recent_activity: list[DecisionFeedItem]
