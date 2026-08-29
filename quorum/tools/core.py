"""Concrete core tools; every external action has a stable idempotency key."""

from __future__ import annotations

from datetime import datetime, timezone
from collections.abc import Callable
from typing import Any

from strands import tool

from quorum.channels.base import Channel
from quorum.domain.models import Assignment, NegotiationStatus, NegotiationThread, Role
from quorum.persistence.memory import MemoryStore
from quorum.services.candidate_ranker import CandidateRanker
from quorum.services.gap_detector import GapDetector
from quorum.services.ledger import DecisionLedger
from quorum.utils import stable_id, stable_key


def build_tools(
    store: MemoryStore,
    channel: Channel | None = None,
    contact_resolver: Callable[[str], str] | None = None,
) -> list[object]:
    ranker = CandidateRanker(store)
    gaps = GapDetector(store)
    ledger = DecisionLedger(store)

    @tool
    def get_shift(shift_id: str) -> dict[str, Any]:
        """Get a synthetic shift by ID."""
        shift = store.get_shift(shift_id)
        return shift.model_dump(mode="json", by_alias=True) if shift else {"error": "not_found"}

    @tool
    def detect_staffing_gap(shift_id: str, source_event_id: str) -> list[dict[str, Any]]:
        """Deterministically detect role shortfalls for a shift."""
        return [item.model_dump(mode="json", by_alias=True) for item in gaps.detect(shift_id, source_event_id)]

    @tool
    def list_candidates(shift_id: str, role: str) -> list[dict[str, Any]]:
        """Return deterministic eligible candidates and score breakdowns."""
        return [item.model_dump(mode="json") for item in ranker.rank(shift_id, Role(role))]

    @tool
    def get_contact_history(volunteer_id: str) -> list[dict[str, Any]]:
        """Return safe aggregate local contact history."""
        volunteer = store.get_volunteer(volunteer_id)
        if not volunteer:
            return []
        return [{"weekly_contact_count": volunteer.weekly_contact_count, "concurrent_asks": volunteer.concurrent_asks}]

    @tool
    def find_transport_option(shift_id: str, volunteer_id: str) -> dict[str, Any]:
        """Find the fixed synthetic transport option for the demo world."""
        if not store.get_shift(shift_id) or not store.get_volunteer(volunteer_id):
            return {"available": False}
        return {"available": True, "option": "Synthetic community van pickup 30 minutes before shift"}

    @tool
    def send_message(
        volunteer_id: str,
        thread_id: str,
        turn_index: int,
        body: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        """Send one message after idempotency and routing gates.

        Args:
            volunteer_id: Synthetic volunteer domain ID.
            thread_id: Stable negotiation thread ID.
            turn_index: Stable outbound turn number.
            body: Concise outbound body.
            idempotency_key: Stable logical key from thread, turn, and body.
        """
        expected_key = stable_key(thread_id, turn_index, body)
        if idempotency_key != expected_key:
            return {"status": "blocked", "reason": "invalid_idempotency_key"}
        reserved, existing = store.begin_effect(idempotency_key)
        if not reserved:
            return {"status": "duplicate_suppressed", **existing}
        try:
            if channel is None:
                result = {"accepted": True, "provider_msg_id": "controlled-test"}
            else:
                if contact_resolver is None:
                    raise RuntimeError("No provider contact resolver is configured")
                result = channel.send(contact_resolver(volunteer_id), body).model_dump()
        except Exception as exc:
            store.complete_effect(idempotency_key, {"status": "failed", "error": type(exc).__name__})
            raise
        stored = store.complete_effect(idempotency_key, result)
        return {"status": "sent", **stored}

    @tool
    def open_negotiation(shift_id: str, volunteer_id: str, idempotency_key: str) -> dict[str, Any]:
        """Open one negotiation thread for one shift and volunteer."""
        thread_id = stable_id("thread", shift_id, volunteer_id)
        existing = store.negotiations.get(thread_id)
        if existing:
            return {"status": "duplicate_suppressed", "thread_id": thread_id}
        thread = NegotiationThread(
            id=thread_id,
            shift_id=shift_id,
            volunteer_id=volunteer_id,
            session_id=f"nego:{shift_id}:{volunteer_id}",
            updated_at=datetime.now(timezone.utc),
        )
        store.save_negotiation(thread)
        store.record_effect_once(idempotency_key, {"thread_id": thread.id})
        return {"status": "opened", "thread_id": thread.id}

    @tool
    def confirm_assignment(
        shift_id: str, volunteer_id: str, role: str, idempotency_key: str
    ) -> dict[str, Any]:
        """Atomically confirm one assignment while a role seat remains."""
        shift = store.get_shift(shift_id)
        if not shift:
            return {"confirmed": False, "reason": "shift_not_found"}
        volunteer = store.get_volunteer(volunteer_id)
        role_value = Role(role)
        if not volunteer or role_value not in volunteer.roles or not volunteer.background_check:
            return {"confirmed": False, "reason": "eligibility_failed"}
        assignment = Assignment(
            id=stable_id("assignment", idempotency_key),
            shift_id=shift_id,
            volunteer_id=volunteer_id,
            role=role_value,
            confirmed_at=datetime.now(timezone.utc),
        )
        confirmed, saved, reason = store.confirm_assignment(assignment, shift.required_by_role[role_value])
        return {"confirmed": confirmed, "reason": reason, "assignment_id": saved.id if saved else None}

    @tool
    def close_negotiation(thread_id: str, status: str, idempotency_key: str) -> dict[str, Any]:
        """Close an open negotiation in a terminal state."""
        thread = store.negotiations.get(thread_id)
        if not thread:
            return {"closed": False, "reason": "not_found"}
        if thread.status != NegotiationStatus.OPEN and thread.status != NegotiationStatus.AWAITING_REPLY:
            return {"closed": False, "reason": "already_closed"}
        thread.status = NegotiationStatus(status)
        thread.updated_at = datetime.now(timezone.utc)
        store.save_negotiation(thread)
        store.record_effect_once(idempotency_key, {"thread_id": thread_id, "status": status})
        return {"closed": True}

    @tool
    def request_escalation(reason: str, idempotency_key: str) -> dict[str, Any]:
        """Record an escalation request after RoutingHook approval."""
        created, result = store.record_effect_once(idempotency_key, {"requested": True, "reason": reason})
        return {"status": "requested" if created else "duplicate_suppressed", **result}

    @tool
    def log_decision(category: str, decision: str, idempotency_key: str) -> dict[str, Any]:
        """Append one sanitized decision ledger entry."""
        ledger.record(category, decision, key=f"ledger:{idempotency_key}")
        return {"logged": True}

    return [
        get_shift,
        detect_staffing_gap,
        list_candidates,
        get_contact_history,
        find_transport_option,
        send_message,
        open_negotiation,
        confirm_assignment,
        close_negotiation,
        request_escalation,
        log_decision,
    ]
