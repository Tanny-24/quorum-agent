"""Deterministic staffing gap detection; no model calls."""

from __future__ import annotations

from quorum.domain.models import Gap, GapStatus, Role, TERMINAL_GAP_STATUSES
from quorum.persistence.memory import MemoryStore
from quorum.utils import stable_id, utc_now


class GapDetector:
    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    def detect(self, shift_id: str, source_event_id: str) -> list[Gap]:
        shift = self.store.get_shift(shift_id)
        if shift is None:
            raise KeyError(f"Unknown shift {shift_id}")
        assignments = self.store.list_assignments(shift_id)
        results: list[Gap] = []
        for role, required in shift.required_by_role.items():
            confirmed = sum(1 for item in assignments if item.role == role)
            shortfall = required - confirmed
            gap_id = stable_id("gap", shift_id, role.value)
            existing = self.store.get_gap(gap_id)
            if shortfall <= 0:
                if existing and existing.status not in TERMINAL_GAP_STATUSES:
                    existing.shortfall = max(existing.shortfall, 1)
                    existing.status = GapStatus.RESOLVED
                    self.store.update_gap(existing)
                continue
            if existing:
                # A terminal gap is never silently reopened by duplicate/new events.
                if existing.status in TERMINAL_GAP_STATUSES:
                    continue
                existing.shortfall = shortfall
                results.append(self.store.update_gap(existing))
                continue
            results.append(
                self.store.upsert_gap(
                    Gap(
                        id=gap_id,
                        shift_id=shift_id,
                        role=Role(role),
                        shortfall=shortfall,
                        detected_at=utc_now(),
                        source_event_id=source_event_id,
                    )
                )
            )
        return results
