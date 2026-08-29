"""Core events, each with a required idempotency key."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class EventKind(StrEnum):
    SHIFT_CREATED = "SHIFT_CREATED"
    VOLUNTEER_CANCELLED = "VOLUNTEER_CANCELLED"
    NO_SHOW = "NO_SHOW"
    VOLUNTEER_REPLY = "VOLUNTEER_REPLY"
    TIMER_TICK = "TIMER_TICK"
    SETTLEMENT_EXPIRED = "SETTLEMENT_EXPIRED"
    HUMAN_DECISION_RECEIVED = "HUMAN_DECISION_RECEIVED"
    SHIFT_STARTED = "SHIFT_STARTED"


class QuorumEvent(BaseModel):
    id: str
    kind: EventKind
    idempotency_key: str
    occurred_at: datetime
    payload: dict[str, Any]
    synthetic: bool = True
