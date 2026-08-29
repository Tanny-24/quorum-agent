"""Deterministic EV routing and persistent attention-budget accounting."""

from __future__ import annotations

from datetime import datetime

from quorum.domain.models import RoutingClass, RoutingDecision
from quorum.persistence.memory import MemoryStore

BASE_THRESHOLD = 1.8
ONE_REMAINING_THRESHOLD = 2.7
CRITICAL_LINE = 3.6

LAYER_ZERO_TERMS = {
    "injury",
    "illness",
    "medical",
    "safeguarding",
    "vulnerable_person",
    "harassment",
    "discrimination",
    "complaint",
    "service_cancellation",
    "resource_conflict",
    "permanent_removal",
    "money",
    "employment",
    "contracts",
    "unsafe_minor",
}


def urgency_from_hours(hours_until_shift: float) -> float:
    if hours_until_shift <= 2:
        return 1.0
    if hours_until_shift <= 8:
        return 0.8
    if hours_until_shift <= 24:
        return 0.5
    return 0.2


def consequence_for(shortfall: int, blocking_role: bool = False, service_stopping: bool = False) -> int:
    if service_stopping:
        return 5
    if blocking_role:
        return min(5, 3 + shortfall)
    return min(5, 1 + shortfall)


def pessimistic_uncertainty(model_estimate: float, observable: float, empty_pool: bool = False) -> float:
    if empty_pool:
        return 1.0
    return max(0.0, min(1.0, max(model_estimate, observable)))


def ev_score(consequence: int, uncertainty: float, urgency: float, reversibility: int) -> float:
    """Policy heuristic, not a mathematically optimal expected-value model."""
    return (consequence * uncertainty * urgency) / reversibility


class EscalationEngine:
    def __init__(self, store: MemoryStore, budget_id: str = "budget:riverside", allowance: int = 2) -> None:
        self.store = store
        self.budget_id = budget_id
        self.allowance = allowance

    def threshold(self) -> float:
        budget = self.store.get_budget(self.budget_id, self.allowance)
        remaining = budget.allowance - budget.spent
        if remaining >= 2:
            return BASE_THRESHOLD
        if remaining == 1:
            return ONE_REMAINING_THRESHOLD
        return CRITICAL_LINE

    def route(
        self,
        decision_id: str,
        *,
        consequence: int,
        uncertainty: float,
        urgency: float,
        reversibility: int,
        safety_category: str | None = None,
        yellow_floor: float = 0.7,
    ) -> RoutingDecision:
        budget = self.store.get_budget(self.budget_id, self.allowance)
        if safety_category in LAYER_ZERO_TERMS:
            override = budget.spent >= budget.allowance
            self.store.spend_budget_once(self.budget_id, decision_id, override=override)
            return RoutingDecision(
                routing_class=RoutingClass.RED,
                ev_score=None,
                threshold=None,
                reason=f"layer_0:{safety_category}",
                budget_spent=not override,
                budget_override=override,
            )
        score = ev_score(consequence, uncertainty, urgency, reversibility)
        threshold = self.threshold()
        if score >= CRITICAL_LINE:
            override = budget.spent >= budget.allowance
            self.store.spend_budget_once(self.budget_id, decision_id, override=override)
            return RoutingDecision(
                routing_class=RoutingClass.RED,
                ev_score=score,
                threshold=threshold,
                reason="critical_ev",
                budget_spent=not override,
                budget_override=override,
            )
        if score >= threshold and budget.spent < budget.allowance:
            self.store.spend_budget_once(self.budget_id, decision_id)
            return RoutingDecision(
                routing_class=RoutingClass.RED,
                ev_score=score,
                threshold=threshold,
                reason="attention_threshold",
                budget_spent=True,
            )
        if score >= yellow_floor:
            return RoutingDecision(
                routing_class=RoutingClass.YELLOW,
                ev_score=score,
                threshold=threshold,
                reason="settlement_window",
            )
        return RoutingDecision(
            routing_class=RoutingClass.GREEN,
            ev_score=score,
            threshold=threshold,
            reason="low_consequence_reversible",
        )
