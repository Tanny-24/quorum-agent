"""Deterministic transport-condition resolution for the synthetic workspace."""

from __future__ import annotations

from quorum.persistence.memory import MemoryStore


class TransportService:
    """Resolve the one supported synthetic transport condition without providers."""

    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    def find_option(self, shift_id: str, volunteer_id: str) -> dict[str, object]:
        if not self.store.get_shift(shift_id) or not self.store.get_volunteer(
            volunteer_id
        ):
            return {"available": False, "option": None}
        return {
            "available": True,
            "option": "Synthetic community van pickup 30 minutes before shift",
        }
