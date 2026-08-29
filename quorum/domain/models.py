"""Minimum typed domain for Riverside Food Bank roster recovery."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SyntheticModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, use_enum_values=False)
    synthetic: bool = Field(default=True, alias="_synthetic")


class Role(StrEnum):
    DRIVER = "driver"
    SORTER = "sorter"


class GapStatus(StrEnum):
    DETECTED = "DETECTED"
    ANALYZING = "ANALYZING"
    SEARCHING = "SEARCHING"
    CONTACTING = "CONTACTING"
    AWAITING = "AWAITING"
    ESCALATION_REQUIRED = "ESCALATION_REQUIRED"
    WAITING_FOR_HUMAN = "WAITING_FOR_HUMAN"
    RESUMING = "RESUMING"
    DEFERRED = "DEFERRED"
    RESOLVED = "RESOLVED"
    FAILED = "FAILED"


TERMINAL_GAP_STATUSES = {GapStatus.RESOLVED, GapStatus.FAILED}


class NegotiationStatus(StrEnum):
    OPEN = "OPEN"
    AWAITING_REPLY = "AWAITING_REPLY"
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"
    ESCALATED = "ESCALATED"
    TIMED_OUT = "TIMED_OUT"


class PendingStatus(StrEnum):
    PENDING = "PENDING"
    SETTLING = "SETTLING"
    SETTLED = "SETTLED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


class InterruptStatus(StrEnum):
    OPEN = "OPEN"
    RESOLVING = "RESOLVING"
    RESOLVED = "RESOLVED"


class ReplyIntent(StrEnum):
    ACCEPT = "ACCEPT"
    ACCEPT_IF = "ACCEPT_IF"
    DECLINE = "DECLINE"
    QUESTION = "QUESTION"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"
    UNCLEAR = "UNCLEAR"


class RoutingClass(StrEnum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"
    DEFER = "SILENT/DEFER"


class Organisation(SyntheticModel):
    id: str
    name: str


class Site(SyntheticModel):
    id: str
    organisation_id: str
    name: str
    travel_zone: int = Field(ge=1, le=6)


class Volunteer(SyntheticModel):
    id: str
    display_name: str
    roles: set[Role]
    active: bool = True
    age: int = Field(ge=0)
    background_check: bool = False
    available_shift_ids: set[str] = Field(default_factory=set)
    travel_zones: set[int] = Field(default_factory=set)
    reliability_successes: int = 0
    reliability_failures: int = 0
    accepted: int = 0
    declined: int = 0
    weekly_contact_count: int = 0
    concurrent_asks: int = 0
    last_contact_at: datetime | None = None
    needs_transport: bool = False
    archetype: str = "standard"


class Shift(SyntheticModel):
    id: str
    organisation_id: str
    site_id: str
    starts_at: datetime
    ends_at: datetime
    required_by_role: dict[Role, int]


class Assignment(SyntheticModel):
    id: str
    shift_id: str
    volunteer_id: str
    role: Role
    confirmed_at: datetime


class Gap(SyntheticModel):
    id: str
    shift_id: str
    role: Role
    shortfall: int = Field(gt=0)
    status: GapStatus = GapStatus.DETECTED
    detected_at: datetime
    source_event_id: str


class NegotiationThread(SyntheticModel):
    id: str
    shift_id: str
    volunteer_id: str
    session_id: str
    status: NegotiationStatus = NegotiationStatus.OPEN
    turn_index: int = 0
    updated_at: datetime


class ContactRecord(SyntheticModel):
    id: str
    volunteer_id: str
    thread_id: str
    direction: str
    contacted_at: datetime


class AttentionBudget(SyntheticModel):
    id: str
    allowance: int = 2
    spent: int = 0
    overrides: int = 0
    history: list[dict[str, Any]] = Field(default_factory=list)


class PendingEffect(SyntheticModel):
    id: str
    effect_type: str
    idempotency_key: str
    payload: dict[str, Any]
    settle_at: datetime
    status: PendingStatus = PendingStatus.PENDING
    created_at: datetime
    updated_at: datetime
    result: dict[str, Any] | None = None


class InterruptRecord(SyntheticModel):
    id: str
    session_id: str
    idempotency_key: str
    reason: dict[str, Any]
    strands_interrupt_id: str | None = None
    status: InterruptStatus = InterruptStatus.OPEN
    created_at: datetime
    resolved_at: datetime | None = None
    decision: str | None = None


class LedgerEntry(SyntheticModel):
    id: str
    timestamp: datetime
    category: str
    decision: str
    event_id: str | None = None
    gap_id: str | None = None
    routing_class: RoutingClass | None = None
    ev_inputs: dict[str, float] = Field(default_factory=dict)
    ev_score: float | None = None
    budget_state: dict[str, int] = Field(default_factory=dict)
    reason: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class CandidateScore(BaseModel):
    volunteer_id: str
    score: float
    breakdown: dict[str, float]
    eligible: bool = True
    rejection_reasons: list[str] = Field(default_factory=list)


class ReplyClassification(BaseModel):
    intent: ReplyIntent
    condition: str | None = None
    confidence: float = Field(ge=0, le=1)
    safety_reason: str | None = None


class RoutingDecision(BaseModel):
    routing_class: RoutingClass
    ev_score: float | None
    threshold: float | None
    reason: str
    budget_spent: bool = False
    budget_override: bool = False
