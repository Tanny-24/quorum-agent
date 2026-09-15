"""Narrow FastAPI endpoints justified by the current core."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from quorum.api.schemas import (
    AttentionBudgetView,
    CancelPendingEffectRequest,
    CancelPendingEffectResponse,
    DashboardSummary,
    DecisionFeedPage,
    DemoResetResponse,
    DemoScenarioView,
    HealthResponse,
    HumanDecisionDetail,
    HumanDecisionSummary,
    PendingEffectCompactView,
    RecoveryRunDetail,
    ResolveInterruptRequest,
    ResolveInterruptResponse,
    RunDemoScenarioRequest,
    RunDemoScenarioResponse,
    ShiftDetail,
    ShiftSummary,
    VolunteerDetailView,
    VolunteerOperationalStatus,
    VolunteerSummaryView,
)
from quorum.channels.telegram import TelegramChannel
from quorum.config import Settings
from quorum.data.loader import seed_store
from quorum.domain.models import InterruptStatus, PendingStatus, Role, RoutingClass
from quorum.events.handlers import EventHandler
from quorum.events.models import EventKind, QuorumEvent
from quorum.events.normalizer import message_to_event
from quorum.persistence.memory import MemoryStore
from quorum.services.interrupts import InterruptService
from quorum.services.orchestration import DemoOrchestrationService, EXECUTION_MODE
from quorum.services.pending_effects import PendingEffectService
from quorum.services.read_models import ReadModelService
from quorum.services.recovery import RecoveryService
from quorum.utils import stable_id, stable_key


class StaffingEventRequest(BaseModel):
    shift_id: str
    idempotency_key: str


class AppContext:
    def __init__(self, store: MemoryStore | None = None, settings: Settings | None = None) -> None:
        self.settings = settings or Settings.from_env()
        self.store = store or seed_store(MemoryStore())
        self.events = EventHandler(self.store)
        self.pending = PendingEffectService(self.store)
        self.interrupts = InterruptService(self.store)
        self.demo = DemoOrchestrationService(
            self.store,
            attention_allowance=self.settings.attention_budget,
        )
        self.read = ReadModelService(
            self.store,
            attention_allowance=self.settings.attention_budget,
        )
        # Materialize the one runtime budget used by both UI reads and routing.
        self.read.attention_budget()
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

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse()

    @app.get("/dashboard", response_model=DashboardSummary)
    def dashboard() -> DashboardSummary:
        return context.read.dashboard()

    @app.get("/attention-budget", response_model=AttentionBudgetView)
    def attention_budget() -> AttentionBudgetView:
        return context.read.attention_budget()

    @app.get("/shifts", response_model=list[ShiftSummary])
    def shifts() -> list[ShiftSummary]:
        return context.read.shift_summaries()

    @app.get("/shifts/{shift_id}", response_model=ShiftDetail)
    def shift_detail(shift_id: str) -> ShiftDetail:
        detail = context.read.shift_detail(shift_id)
        if detail is None:
            raise HTTPException(status_code=404, detail={"code": "shift_not_found"})
        return detail

    @app.get("/volunteers", response_model=list[VolunteerSummaryView])
    def volunteers(
        role: Role | None = None,
        status: VolunteerOperationalStatus | None = None,
        available: bool | None = None,
    ) -> list[VolunteerSummaryView]:
        return context.read.volunteer_summaries(
            role=role,
            status=status,
            available=available,
        )

    @app.get(
        "/volunteers/{volunteer_id}",
        response_model=VolunteerDetailView,
    )
    def volunteer_detail(volunteer_id: str) -> VolunteerDetailView:
        detail = context.read.volunteer_detail(volunteer_id)
        if detail is None:
            raise HTTPException(
                status_code=404,
                detail={"code": "volunteer_not_found"},
            )
        return detail

    @app.get("/demo/scenarios", response_model=list[DemoScenarioView])
    def demo_scenarios() -> list[DemoScenarioView]:
        return [
            DemoScenarioView(
                id=scenario.id,
                title=scenario.title,
                description=scenario.description,
                expected_route=scenario.expected_route,
                expected_human_involvement=scenario.expected_human_involvement,
                execution_mode=EXECUTION_MODE,
            )
            for scenario in context.demo.scenarios()
        ]

    @app.post("/demo/reset", response_model=DemoResetResponse)
    def demo_reset() -> DemoResetResponse:
        return DemoResetResponse.model_validate(context.demo.reset())

    @app.get("/demo/runs", response_model=list[RecoveryRunDetail])
    def demo_runs() -> list[RecoveryRunDetail]:
        return context.read.recovery_runs()

    @app.get("/demo/runs/{run_id}", response_model=RecoveryRunDetail)
    def demo_run(run_id: str) -> RecoveryRunDetail:
        run = context.store.get_recovery_run(run_id)
        if run is None:
            raise HTTPException(
                status_code=404,
                detail={"code": "demo_run_not_found"},
            )
        return context.read.recovery_run_detail(run)

    @app.post(
        "/demo/scenarios/{scenario_id}/run",
        response_model=RunDemoScenarioResponse,
    )
    def run_demo_scenario(
        scenario_id: str,
        request: RunDemoScenarioRequest,
    ) -> RunDemoScenarioResponse:
        try:
            duplicate, run = context.demo.run(
                scenario_id,
                request.idempotency_key,
            )
        except KeyError as exc:
            raise HTTPException(
                status_code=404,
                detail={"code": "demo_scenario_not_found"},
            ) from exc
        return RunDemoScenarioResponse(
            duplicate=duplicate,
            run=context.read.recovery_run_detail(run),
        )

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

    @app.get("/interrupts", response_model=list[HumanDecisionSummary])
    def interrupts(
        status: InterruptStatus | None = None,
    ) -> list[HumanDecisionSummary]:
        return context.read.human_decisions(status)

    @app.get("/interrupts/{interrupt_id}", response_model=HumanDecisionDetail)
    def interrupt_detail(interrupt_id: str) -> HumanDecisionDetail:
        detail = context.read.human_decision_detail(interrupt_id)
        if detail is None:
            raise HTTPException(
                status_code=404,
                detail={"code": "interrupt_not_found"},
            )
        return detail

    @app.post(
        "/interrupts/{interrupt_id}/resolve",
        response_model=ResolveInterruptResponse,
    )
    def resolve_interrupt(
        interrupt_id: str,
        request: ResolveInterruptRequest,
    ) -> ResolveInterruptResponse:
        existing = context.store.get_interrupt(interrupt_id)
        if existing is None:
            raise HTTPException(
                status_code=404,
                detail={"code": "interrupt_not_found"},
            )
        action = request.effective_action()
        allowed = context.interrupts.allowed_actions(existing)
        if existing.status != InterruptStatus.OPEN:
            if request.decision is not None:
                detail = context.read.human_decision_detail(existing.id)
                if detail is None:
                    raise HTTPException(status_code=500)
                return ResolveInterruptResponse(
                    resolved=False,
                    outcome="already_resolved",
                    automatic_continuation=False,
                    decision=detail,
                )
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "interrupt_already_resolved",
                    "status": existing.status.value,
                },
            )
        if existing.version != request.expected_version:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "interrupt_version_conflict",
                    "status": existing.status.value,
                    "version": existing.version,
                },
            )
        if action not in allowed:
            raise HTTPException(
                status_code=409,
                detail={"code": "interrupt_action_not_allowed"},
            )
        try:
            won, record, _ = context.interrupts.resolve_once(
                interrupt_id,
                action.value,
                context.interrupt_resumer,
                expected_version=request.expected_version,
                note=request.note,
                actor=request.actor,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail={"code": "interrupt_resume_failed"},
            ) from exc
        if not won or record is None:
            latest = context.store.get_interrupt(interrupt_id)
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "interrupt_resolution_conflict",
                    "status": latest.status.value if latest else None,
                },
            )
        detail = context.read.human_decision_detail(record.id)
        if detail is None:
            raise HTTPException(
                status_code=500,
                detail={"code": "interrupt_projection_failed"},
            )
        outcome = record.resolution_outcome or "recorded_no_runtime_resumer"
        return ResolveInterruptResponse(
            resolved=True,
            outcome=outcome,
            automatic_continuation=outcome == "workflow_resumed",
            decision=detail,
        )

    @app.get("/feed", response_model=DecisionFeedPage)
    def feed(
        route_filter: RoutingClass | None = Query(default=None, alias="route"),
        category: str | None = None,
        shift_id: str | None = None,
        cursor: str | None = None,
        limit: int = Query(default=50, ge=1, le=100),
    ) -> DecisionFeedPage:
        try:
            return context.read.decision_feed_page(
                route=route_filter,
                category=category,
                shift_id=shift_id,
                cursor=cursor,
                limit=limit,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail={"code": str(exc)},
            ) from exc

    @app.get("/pending", response_model=list[PendingEffectCompactView])
    def pending(status: PendingStatus | None = None) -> list[PendingEffectCompactView]:
        return context.read.pending_effects(status)

    @app.post(
        "/pending/{pending_id}/cancel",
        response_model=CancelPendingEffectResponse,
    )
    def cancel_pending(
        pending_id: str,
        request: CancelPendingEffectRequest | None = None,
    ) -> CancelPendingEffectResponse:
        command = request or CancelPendingEffectRequest()
        cancelled, reason = context.pending.cancel(
            pending_id,
            actor=command.actor,
        )
        if reason == "not_found":
            raise HTTPException(status_code=404, detail={"code": "pending_not_found"})
        return CancelPendingEffectResponse(cancelled=cancelled, reason=reason)

    return app


app = create_app()
