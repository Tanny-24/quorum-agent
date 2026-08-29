"""Persistent human-interrupt records and idempotent resolution."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from quorum.domain.models import InterruptRecord
from quorum.persistence.memory import MemoryStore
from quorum.utils import stable_id, utc_now


class InterruptService:
    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    def create(self, session_id: str, idempotency_key: str, reason: dict[str, Any]) -> InterruptRecord:
        return self.store.create_interrupt(
            InterruptRecord(
                id=stable_id("interrupt", session_id, idempotency_key),
                session_id=session_id,
                idempotency_key=idempotency_key,
                reason=reason,
                created_at=utc_now(),
            )
        )

    def resolve_once(
        self,
        record_id: str,
        decision: str,
        resume: Callable[[InterruptRecord, str], Any] | None = None,
    ) -> tuple[bool, InterruptRecord | None, Any | None]:
        won, record = self.store.claim_interrupt(record_id)
        if not won or record is None:
            return False, record, None
        try:
            result = resume(record, decision) if resume else None
        except Exception:
            self.store.release_interrupt(record_id)
            raise
        completed = self.store.complete_interrupt(record_id, decision)
        return True, completed, result


class StrandsInterruptResumer:
    """Create a fresh Agent and submit the persisted Strands interrupt response."""

    def __init__(self, agent_factory: Callable[[str], Any]) -> None:
        self.agent_factory = agent_factory

    def __call__(self, record: InterruptRecord, decision: str) -> dict[str, Any]:
        if not record.strands_interrupt_id:
            raise RuntimeError("Interrupt record has no persisted Strands interrupt ID")
        agent = self.agent_factory(record.session_id)
        result = agent(
            [
                {
                    "interruptResponse": {
                        "interruptId": record.strands_interrupt_id,
                        "response": decision,
                    }
                }
            ]
        )
        if result.stop_reason == "interrupt":
            raise RuntimeError("Fresh-agent resume raised another interrupt")
        return {"stop_reason": result.stop_reason}
