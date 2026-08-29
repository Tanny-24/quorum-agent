"""Basic recovery: settle durable timers, surface interrupts, and close stale threads."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from quorum.domain.models import NegotiationStatus
from quorum.persistence.memory import MemoryStore
from quorum.services.gap_detector import GapDetector
from quorum.services.pending_effects import PendingEffectService


class RecoveryService:
    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    def recover(self, handlers: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
        now = now or datetime.now(timezone.utc)
        settled = PendingEffectService(self.store).settle_due(handlers, now)
        for gap in self.store.list_gaps():
            GapDetector(self.store).detect(gap.shift_id, f"recovery:{gap.id}")
        closed = 0
        for thread in self.store.list_negotiations():
            shift = self.store.get_shift(thread.shift_id)
            if shift and shift.starts_at <= now and thread.status in {
                NegotiationStatus.OPEN,
                NegotiationStatus.AWAITING_REPLY,
            }:
                thread.status = NegotiationStatus.TIMED_OUT
                thread.updated_at = now
                self.store.save_negotiation(thread)
                closed += 1
        return {
            "settled": len(settled),
            "open_interrupts": self.store.list_open_interrupts(),
            "closed_negotiations": closed,
        }
