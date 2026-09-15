"""Idempotent event handling for the narrow roster-recovery core."""

from __future__ import annotations

from quorum.events.models import EventKind, QuorumEvent
from quorum.persistence.memory import MemoryStore
from quorum.services.gap_detector import GapDetector
from quorum.services.ledger import DecisionLedger


class EventHandler:
    def __init__(self, store: MemoryStore) -> None:
        self.store = store
        self.gaps = GapDetector(store)
        self.ledger = DecisionLedger(store)

    def handle(self, event: QuorumEvent) -> dict[str, object]:
        if not self.store.record_event_once(event.idempotency_key):
            self.ledger.record(
                "event",
                "DUPLICATE_SUPPRESSED",
                event_id=event.id,
                reason="event_idempotency_key_seen",
                key=f"ledger:duplicate:{event.idempotency_key}",
            )
            return {"duplicate": True, "gaps": []}
        gaps = []
        if event.kind in {EventKind.VOLUNTEER_CANCELLED, EventKind.NO_SHOW, EventKind.SHIFT_CREATED}:
            shift_id = str(event.payload["shift_id"])
            gaps = self.gaps.detect(shift_id, event.id)
        details = {"kind": event.kind.value}
        shift_id = event.payload.get("shift_id")
        if isinstance(shift_id, str):
            details["shift_id"] = shift_id
        self.ledger.record("event", "PROCESSED", event_id=event.id, details=details)
        return {"duplicate": False, "gaps": gaps}
