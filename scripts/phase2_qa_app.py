"""Explicit local-only FastAPI app with deterministic Phase 2 QA state."""

from __future__ import annotations

from quorum.api.app import AppContext, create_app
from quorum.config import Settings
from quorum.data.loader import seed_store
from quorum.domain.models import Role, RoutingClass
from quorum.events.models import EventKind
from quorum.persistence.memory import MemoryStore
from quorum.services.workflow import CoreWorkflow


def build_qa_context() -> AppContext:
    store = seed_store(MemoryStore())
    workflow = CoreWorkflow(store)
    workflow.staffing_event(
        EventKind.VOLUNTEER_CANCELLED,
        "shift-1",
        "phase2-qa-cancellation",
    )
    thread = workflow.open_thread("shift-1", "vol-09")
    workflow.queue_outreach(
        thread,
        "Can you cover this synthetic Riverside shift?",
        delay_minutes=30,
    )
    workflow.ledger.record(
        "ranking",
        "CANDIDATE_RANKED",
        routing_class=RoutingClass.GREEN,
        reason="highest_eligible_score",
        details={"shift_id": "shift-1"},
        key="phase2-qa-green",
    )
    workflow.ledger.silence(
        "contact_cap_reached",
        details={"shift_id": "shift-1"},
        key="phase2-qa-silent",
    )
    workflow.reply_and_assign(
        thread,
        "I was injured and need to complain",
        Role.DRIVER,
    )
    return AppContext(
        store=store,
        settings=Settings(
            attention_budget=5,
            gemini_api_key=None,
            telegram_bot_token=None,
            telegram_chat_id=None,
        ),
    )


app = create_app(build_qa_context())
