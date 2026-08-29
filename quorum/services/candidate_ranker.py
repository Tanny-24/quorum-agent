"""Explainable deterministic eligibility and ranking."""

from __future__ import annotations

from datetime import datetime

from quorum.domain.models import CandidateScore, Role, Shift, Volunteer
from quorum.persistence.memory import MemoryStore


def laplace(successes: int, failures: int) -> float:
    """Laplace-smoothed binary rate for sparse volunteer histories."""
    return (successes + 1) / (successes + failures + 2)


class CandidateRanker:
    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    def eligibility(self, volunteer: Volunteer, shift: Shift, role: Role) -> list[str]:
        reasons: list[str] = []
        if role not in volunteer.roles:
            reasons.append("wrong_role")
        if not volunteer.active:
            reasons.append("inactive")
        if shift.id not in volunteer.available_shift_ids:
            reasons.append("unavailable")
        if not volunteer.background_check:
            reasons.append("missing_background_check")
        if role == Role.DRIVER and volunteer.age < 18:
            reasons.append("under_minimum_age")
        if volunteer.weekly_contact_count >= 2:
            reasons.append("weekly_contact_cap")
        if volunteer.concurrent_asks >= 3:
            reasons.append("max_concurrent_asks")
        for assignment in self.store.assignments.values():
            if assignment.volunteer_id != volunteer.id:
                continue
            other = self.store.get_shift(assignment.shift_id)
            if other and max(other.starts_at, shift.starts_at) < min(other.ends_at, shift.ends_at):
                reasons.append("conflicting_assignment")
                break
        site = self.store.sites[shift.site_id]
        if site.travel_zone not in volunteer.travel_zones and not volunteer.needs_transport:
            reasons.append("travel_infeasible")
        return reasons

    def rank(self, shift_id: str, role: Role, now: datetime | None = None) -> list[CandidateScore]:
        shift = self.store.get_shift(shift_id)
        if shift is None:
            raise KeyError(f"Unknown shift {shift_id}")
        ranked: list[CandidateScore] = []
        for volunteer in self.store.list_volunteers():
            reasons = self.eligibility(volunteer, shift, role)
            if reasons:
                continue
            reliability = laplace(volunteer.reliability_successes, volunteer.reliability_failures)
            acceptance = laplace(volunteer.accepted, volunteer.declined)
            travel = 0.55 if volunteer.needs_transport else 1.0
            availability = 1.0
            contact_load = max(0.0, 1.0 - volunteer.weekly_contact_count / 2)
            recent_penalty = 0.0
            if now and volunteer.last_contact_at:
                hours = (now - volunteer.last_contact_at).total_seconds() / 3600
                recent_penalty = max(0.0, (24 - hours) / 24) * 0.1
            breakdown = {
                "reliability": round(reliability * 0.35, 6),
                "acceptance_rate": round(acceptance * 0.25, 6),
                "travel_feasibility": round(travel * 0.15, 6),
                "availability_fit": availability * 0.15,
                "contact_load": round(contact_load * 0.10, 6),
                "recent_contact_penalty": round(-recent_penalty, 6),
            }
            score = round(sum(breakdown.values()), 6)
            ranked.append(CandidateScore(volunteer_id=volunteer.id, score=score, breakdown=breakdown))
        return sorted(ranked, key=lambda item: (-item.score, item.volunteer_id))
