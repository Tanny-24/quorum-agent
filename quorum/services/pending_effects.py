"""Persisted YELLOW settlement-window state machine."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from quorum.domain.models import PendingEffect, PendingStatus
from quorum.persistence.memory import MemoryStore
from quorum.utils import stable_id, utc_now

SETTLEMENT_WINDOWS = {"send_message": 10, "confirm_assignment": 5, "widen_search": 15}


class PendingEffectService:
    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    def create(
        self,
        effect_type: str,
        idempotency_key: str,
        payload: dict[str, Any],
        *,
        now: datetime | None = None,
        delay_minutes: int | None = None,
    ) -> PendingEffect:
        now = now or utc_now()
        delay = SETTLEMENT_WINDOWS[effect_type] if delay_minutes is None else delay_minutes
        return self.store.create_pending(
            PendingEffect(
                id=stable_id("pending", idempotency_key),
                effect_type=effect_type,
                idempotency_key=idempotency_key,
                payload=payload,
                settle_at=now + timedelta(minutes=delay),
                created_at=now,
                updated_at=now,
            )
        )

    def cancel(self, pending_id: str) -> tuple[bool, str]:
        won, item = self.store.transition_pending(pending_id, PendingStatus.PENDING, PendingStatus.CANCELLED)
        if won:
            return True, "cancelled"
        if item is None:
            return False, "not_found"
        return False, f"already_{item.status.value.lower()}"

    def settle_due(
        self, handlers: dict[str, Callable[[PendingEffect], dict[str, Any]]], now: datetime | None = None
    ) -> list[PendingEffect]:
        now = now or utc_now()
        settled: list[PendingEffect] = []
        for item in self.store.list_due_pending(now):
            claimed, claimed_item = self.store.transition_pending(
                item.id, PendingStatus.PENDING, PendingStatus.SETTLING
            )
            if not claimed or claimed_item is None:
                continue
            handler = handlers.get(item.effect_type)
            if handler is None:
                self.store.transition_pending(item.id, PendingStatus.SETTLING, PendingStatus.FAILED)
                continue
            try:
                result = handler(claimed_item)
                _, completed = self.store.transition_pending(
                    item.id, PendingStatus.SETTLING, PendingStatus.SETTLED, result
                )
            except Exception as exc:
                _, completed = self.store.transition_pending(
                    item.id, PendingStatus.SETTLING, PendingStatus.FAILED, {"error": type(exc).__name__}
                )
            if completed:
                settled.append(completed)
        return settled
