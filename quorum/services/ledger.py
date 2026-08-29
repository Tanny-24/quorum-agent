"""Append-only logical decision ledger."""

from __future__ import annotations

from typing import Any

from quorum.domain.models import LedgerEntry, RoutingClass
from quorum.persistence.memory import MemoryStore
from quorum.utils import stable_id, utc_now


class DecisionLedger:
    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    def record(
        self,
        category: str,
        decision: str,
        *,
        event_id: str | None = None,
        gap_id: str | None = None,
        routing_class: RoutingClass | None = None,
        ev_inputs: dict[str, float] | None = None,
        ev_score: float | None = None,
        budget_state: dict[str, int] | None = None,
        reason: str | None = None,
        details: dict[str, Any] | None = None,
        key: str | None = None,
    ) -> LedgerEntry:
        entry = LedgerEntry(
            id=key or stable_id("ledger", category, decision, event_id, gap_id, reason, details),
            timestamp=utc_now(),
            category=category,
            decision=decision,
            event_id=event_id,
            gap_id=gap_id,
            routing_class=routing_class,
            ev_inputs=ev_inputs or {},
            ev_score=ev_score,
            budget_state=budget_state or {},
            reason=reason,
            details=details or {},
        )
        self.store.append_ledger(entry)
        return entry

    def silence(self, reason: str, **kwargs: Any) -> LedgerEntry:
        return self.record("routing", "INTENTIONAL_SILENCE", routing_class=RoutingClass.DEFER, reason=reason, **kwargs)
