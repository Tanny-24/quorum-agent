"""Deterministic local workflow joining events, negotiation, routing, and ledger."""

from __future__ import annotations

from datetime import datetime, timezone

from quorum.agents.classifier import ModelReplyClassifier, ReplyClassifier
from quorum.domain.models import (
    Assignment,
    GapStatus,
    NegotiationStatus,
    NegotiationThread,
    ReplyIntent,
    Role,
    RoutingClass,
)
from quorum.events.handlers import EventHandler
from quorum.events.models import EventKind, QuorumEvent
from quorum.persistence.memory import MemoryStore
from quorum.services.candidate_ranker import CandidateRanker
from quorum.services.escalation import EscalationEngine
from quorum.services.gap_detector import GapDetector
from quorum.services.interrupts import InterruptService
from quorum.services.ledger import DecisionLedger
from quorum.services.pending_effects import PendingEffectService
from quorum.utils import stable_id, stable_key, utc_now


class CoreWorkflow:
    def __init__(
        self, store: MemoryStore, classifier: ReplyClassifier | ModelReplyClassifier | None = None
    ) -> None:
        self.store = store
        self.events = EventHandler(store)
        self.ranker = CandidateRanker(store)
        self.classifier = classifier or ReplyClassifier()
        self.ledger = DecisionLedger(store)
        self.pending = PendingEffectService(store)
        self.interrupts = InterruptService(store)
        self.escalation = EscalationEngine(store)

    def staffing_event(self, kind: EventKind, shift_id: str, event_key: str) -> list[object]:
        event = QuorumEvent(
            id=stable_id("event", event_key),
            kind=kind,
            idempotency_key=event_key,
            occurred_at=utc_now(),
            payload={"shift_id": shift_id},
        )
        return list(self.events.handle(event)["gaps"])

    def open_thread(self, shift_id: str, volunteer_id: str) -> NegotiationThread:
        thread = NegotiationThread(
            id=stable_id("thread", shift_id, volunteer_id),
            shift_id=shift_id,
            volunteer_id=volunteer_id,
            session_id=f"nego:{shift_id}:{volunteer_id}",
            status=NegotiationStatus.AWAITING_REPLY,
            updated_at=utc_now(),
        )
        self.store.save_negotiation(thread)
        self.ledger.record("negotiation", "OPENED", details={"thread_id": thread.id})
        return thread

    def queue_outreach(self, thread: NegotiationThread, body: str, delay_minutes: int = 10):
        key = stable_key(thread.id, thread.turn_index, body)
        pending = self.pending.create(
            "send_message",
            key,
            {"thread_id": thread.id, "turn_index": thread.turn_index, "body": body},
            delay_minutes=delay_minutes,
        )
        self.ledger.record(
            "routing",
            "PENDING_CREATED",
            routing_class=RoutingClass.YELLOW,
            details={"pending_id": pending.id},
            key=f"pending-ledger:{pending.id}",
        )
        return pending

    def settle_outreach(self, now: datetime | None = None) -> int:
        def controlled_send(item):
            created, _ = self.store.record_effect_once(
                item.idempotency_key, {"accepted": True, "provider_msg_id": "controlled-test"}
            )
            self.ledger.record(
                "pending",
                "SETTLED" if created else "DUPLICATE_SUPPRESSED",
                details={"pending_id": item.id},
                key=f"settled-ledger:{item.id}",
            )
            return {"sent": created}

        return len(self.pending.settle_due({"send_message": controlled_send}, now or utc_now()))

    def reply_and_assign(self, thread: NegotiationThread, text: str, role: Role) -> dict[str, object]:
        classification = self.classifier.classify(text)
        if classification.intent == ReplyIntent.OUT_OF_SCOPE:
            decision = self.escalation.route(
                stable_key(thread.id, text),
                consequence=1,
                uncertainty=0.01,
                urgency=0.01,
                reversibility=3,
                safety_category=classification.safety_reason,
            )
            record = self.interrupts.create(
                thread.session_id,
                stable_key(thread.id, text),
                {"classification": classification.model_dump(mode="json"), "routing": decision.model_dump(mode="json")},
            )
            thread.status = NegotiationStatus.ESCALATED
            self.store.save_negotiation(thread)
            self.ledger.record(
                "interrupt",
                "RAISED",
                routing_class=RoutingClass.RED,
                details={"interrupt_id": record.id},
                key=f"raised:{record.id}",
            )
            return {"classification": classification, "routing": decision, "interrupt": record}
        transport = None
        if classification.intent == ReplyIntent.ACCEPT_IF and classification.condition == "transport":
            transport = {"available": True, "option": "Synthetic community van pickup 30 minutes before shift"}
        if classification.intent not in {ReplyIntent.ACCEPT, ReplyIntent.ACCEPT_IF}:
            return {"classification": classification, "confirmed": False}
        shift = self.store.get_shift(thread.shift_id)
        if shift is None:
            raise KeyError(thread.shift_id)
        assignment = Assignment(
            id=stable_id("assignment", thread.shift_id, thread.volunteer_id, role.value),
            shift_id=thread.shift_id,
            volunteer_id=thread.volunteer_id,
            role=role,
            confirmed_at=datetime.now(timezone.utc),
        )
        confirmed, saved, reason = self.store.confirm_assignment(assignment, shift.required_by_role[role])
        if confirmed:
            thread.status = NegotiationStatus.ACCEPTED
            self.store.save_negotiation(thread)
            GapDetector(self.store).detect(thread.shift_id, f"assignment:{assignment.id}")
        self.ledger.record(
            "assignment",
            "CONFIRMED" if confirmed else "REJECTED",
            reason=reason,
            details={"assignment_id": saved.id if saved else None},
            key=f"assignment-ledger:{assignment.id}",
        )
        return {
            "classification": classification,
            "transport": transport,
            "confirmed": confirmed,
            "reason": reason,
        }

    def resolve_gap_if_staffed(self, gap_id: str) -> bool:
        gap = self.store.get_gap(gap_id)
        return bool(gap and gap.status == GapStatus.RESOLVED)
