"""Non-overridable deterministic contact and safety policy."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from zoneinfo import ZoneInfo

from pydantic import BaseModel

from quorum.domain.models import Role, Volunteer

CONTACT_CAP_PER_WEEK = 2
QUIET_HOURS_START = 21
QUIET_HOURS_END = 8
MAX_CONCURRENT_ASKS = 3
DECLINE_IS_FINAL = True


class PolicyAction(StrEnum):
    ALLOW = "ALLOW"
    QUEUE = "QUEUE"
    REFUSE = "REFUSE"


class PolicyDecision(BaseModel):
    action: PolicyAction
    reason: str


class PolicyGuard:
    def __init__(self, timezone_name: str = "Europe/London") -> None:
        self.timezone = ZoneInfo(timezone_name)

    def contact(self, volunteer: Volunteer, role: Role, now: datetime, thread_declined: bool = False) -> PolicyDecision:
        if thread_declined and DECLINE_IS_FINAL:
            return PolicyDecision(action=PolicyAction.REFUSE, reason="decline_is_final")
        if role == Role.DRIVER and volunteer.age < 18:
            return PolicyDecision(action=PolicyAction.REFUSE, reason="minor_driver_blocked")
        if not volunteer.background_check:
            return PolicyDecision(action=PolicyAction.REFUSE, reason="missing_background_check")
        if volunteer.weekly_contact_count >= CONTACT_CAP_PER_WEEK:
            return PolicyDecision(action=PolicyAction.REFUSE, reason="weekly_contact_cap")
        if volunteer.concurrent_asks >= MAX_CONCURRENT_ASKS:
            return PolicyDecision(action=PolicyAction.REFUSE, reason="max_concurrent_asks")
        hour = now.astimezone(self.timezone).hour
        if hour >= QUIET_HOURS_START or hour < QUIET_HOURS_END:
            return PolicyDecision(action=PolicyAction.QUEUE, reason="quiet_hours")
        return PolicyDecision(action=PolicyAction.ALLOW, reason="policy_clear")
