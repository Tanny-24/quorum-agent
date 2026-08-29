"""Narrow FastAPI endpoints justified by the current core."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from quorum.channels.telegram import TelegramChannel
from quorum.config import Settings
from quorum.data.loader import seed_store
from quorum.events.handlers import EventHandler
from quorum.events.models import EventKind, QuorumEvent
from quorum.events.normalizer import message_to_event
from quorum.persistence.memory import MemoryStore
from quorum.services.interrupts import InterruptService
from quorum.services.pending_effects import PendingEffectService
from quorum.services.recovery import RecoveryService
from quorum.utils import stable_id, stable_key


class StaffingEventRequest(BaseModel):
    shift_id: str
    idempotency_key: str


class DecisionRequest(BaseModel):
    decision: str


class AppContext:
    def __init__(self, store: MemoryStore | None = None, settings: Settings | None = None) -> None:
        self.settings = settings or Settings.from_env()
        self.store = store or seed_store(MemoryStore())
        self.events = EventHandler(self.store)
        self.pending = PendingEffectService(self.store)
        self.interrupts = InterruptService(self.store)
        self.telegram = TelegramChannel(self.settings.telegram_bot_token or "not-configured")
        self.interrupt_resumer = None

    def settlement_handlers(self) -> dict[str, Any]:
        def send_message(item):
            reserved, existing = self.store.begin_effect(item.idempotency_key)
            if not reserved:
                return {"duplicate": True, **existing}
            payload = item.payload
            if not self.settings.telegram_bot_token:
                result = {"accepted": True, "provider_msg_id": "controlled-local"}
            else:
                if not self.settings.telegram_chat_id:
                    raise RuntimeError("Telegram chat ID is unavailable")
                result = self.telegram.send(self.settings.telegram_chat_id, str(payload["body"])).model_dump()
            return self.store.complete_effect(item.idempotency_key, result)

        return {"send_message": send_message}


def create_app(context: AppContext | None = None) -> FastAPI:
    context = context or AppContext()
    app = FastAPI(title="QUORUM Core", version="0.1.0")
    app.state.context = context

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/shifts")
    def shifts() -> list[dict[str, Any]]:
        return [item.model_dump(mode="json", by_alias=True) for item in context.store.list_shifts()]

    def handle_staffing(kind: EventKind, request: StaffingEventRequest) -> dict[str, Any]:
        if context.store.get_shift(request.shift_id) is None:
            raise HTTPException(status_code=404, detail={"code": "shift_not_found"})
        event = QuorumEvent(
            id=stable_id("event", request.idempotency_key),
            kind=kind,
            idempotency_key=request.idempotency_key,
            occurred_at=datetime.now(timezone.utc),
            payload={"shift_id": request.shift_id},
        )
        result = context.events.handle(event)
        return {
            "duplicate": result["duplicate"],
            "gaps": [item.model_dump(mode="json", by_alias=True) for item in result["gaps"]],
        }

    @app.post("/events/cancel")
    def cancellation(request: StaffingEventRequest) -> dict[str, Any]:
        return handle_staffing(EventKind.VOLUNTEER_CANCELLED, request)

    @app.post("/events/no-show")
    def no_show(request: StaffingEventRequest) -> dict[str, Any]:
        return handle_staffing(EventKind.NO_SHOW, request)

    @app.post("/events/tick")
    def tick() -> dict[str, Any]:
        result = RecoveryService(context.store).recover(context.settlement_handlers(), datetime.now(timezone.utc))
        result["open_interrupts"] = [
            item.model_dump(mode="json", by_alias=True) for item in result["open_interrupts"]
        ]
        return result

    @app.post("/webhooks/messages")
    def webhook(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            normalized = context.telegram.normalise(payload)
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail={"code": "invalid_message", "message": str(exc)}) from exc
        event = message_to_event(normalized)
        result = context.events.handle(event)
        return {"accepted": True, "duplicate": result["duplicate"], "event_id": event.id}

    @app.get("/interrupts")
    def interrupts() -> list[dict[str, Any]]:
        return [item.model_dump(mode="json", by_alias=True) for item in context.store.list_open_interrupts()]

    @app.post("/interrupts/{interrupt_id}/resolve")
    def resolve_interrupt(interrupt_id: str, request: DecisionRequest) -> dict[str, Any]:
        existing = context.store.interrupts.get(interrupt_id)
        if existing and existing.strands_interrupt_id and context.interrupt_resumer is None:
            raise HTTPException(status_code=503, detail={"code": "agent_resumer_unavailable"})
        won, record, _ = context.interrupts.resolve_once(
            interrupt_id, request.decision, context.interrupt_resumer
        )
        if record is None:
            raise HTTPException(status_code=404, detail={"code": "interrupt_not_found"})
        return {"resolved": won, "status": record.status.value, "decision": record.decision}

    @app.get("/feed")
    def feed() -> list[dict[str, Any]]:
        return [item.model_dump(mode="json", by_alias=True) for item in context.store.list_ledger()]

    @app.post("/pending/{pending_id}/cancel")
    def cancel_pending(pending_id: str) -> dict[str, Any]:
        cancelled, reason = context.pending.cancel(pending_id)
        if reason == "not_found":
            raise HTTPException(status_code=404, detail={"code": "pending_not_found"})
        return {"cancelled": cancelled, "reason": reason}

    return app


app = create_app()
