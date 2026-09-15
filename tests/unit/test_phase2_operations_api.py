from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from quorum.api.app import AppContext, create_app
from quorum.config import Settings
from quorum.domain.models import (
    InterruptStatus,
    NegotiationStatus,
    NegotiationThread,
    PendingStatus,
    RoutingClass,
)
from quorum.services.ledger import DecisionLedger


NOW = datetime(2026, 9, 15, 9, 0, tzinfo=timezone.utc)


def client_for(store) -> tuple[AppContext, TestClient]:
    context = AppContext(
        store=store,
        settings=Settings(
            attention_budget=5,
            gemini_api_key=None,
            telegram_bot_token=None,
            telegram_chat_id=None,
        ),
    )
    return context, TestClient(create_app(context))


def create_red_decision(context: AppContext, key: str = "phase2-red"):
    thread = NegotiationThread(
        id="thread-phase2",
        shift_id="shift-1",
        volunteer_id="vol-09",
        session_id="nego:shift-1:vol-09",
        status=NegotiationStatus.ESCALATED,
        updated_at=NOW,
    )
    context.store.save_negotiation(thread)
    record = context.interrupts.create(
        thread.session_id,
        key,
        {
            "tool": "request_escalation",
            "classification": {
                "safety_reason": "injury",
                "raw": "private-model-payload",
            },
            "routing": {
                "reason": "layer_0:injury",
                "budget_spent": True,
                "budget_override": False,
            },
            "inputs": {
                "shift_id": "shift-1",
                "volunteer_id": "vol-09",
                "body": "private-message-payload",
            },
        },
    )
    return record


def test_human_decision_reads_are_safe_filterable_and_contextual(store) -> None:
    context, client = client_for(store)
    record = create_red_decision(context)

    collection = client.get("/interrupts")
    assert collection.status_code == 200
    summary = collection.json()[0]
    assert summary["interrupt_id"] == record.id
    assert summary["status"] == "OPEN"
    assert summary["allowed_actions"] == ["APPROVE", "VETO"]
    assert summary["shift"]["site_name"] == "River Hall"
    assert summary["volunteer"]["display_name"] == "Synthetic Volunteer 09"

    detail_response = client.get(f"/interrupts/{record.id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["reason"] == "Layer-0 safety policy identified injury."
    assert detail["negotiation"] == {
        "thread_id": "thread-phase2",
        "status": "ESCALATED",
    }
    assert {item["label"] for item in detail["evidence"]} == {
        "Safety signal",
        "Routing basis",
        "Paused action",
        "Attention Budget",
    }
    assert "private-model-payload" not in detail_response.text
    assert "private-message-payload" not in detail_response.text
    assert client.get("/interrupts", params={"status": "RESOLVED"}).json() == []
    assert client.get("/interrupts/unknown").status_code == 404


def test_typed_resolution_records_truthful_outcome_and_audit(store) -> None:
    context, client = client_for(store)
    record = create_red_decision(context)
    request = {
        "action": "APPROVE",
        "note": "Coordinator reviewed the synthetic safety context.",
        "actor": "demo-coordinator",
        "expected_version": record.version,
    }

    response = client.post(f"/interrupts/{record.id}/resolve", json=request)
    assert response.status_code == 200
    body = response.json()
    assert body["resolved"] is True
    assert body["outcome"] == "recorded_no_runtime_resumer"
    assert body["automatic_continuation"] is False
    assert body["decision"]["status"] == "RESOLVED"
    assert body["decision"]["allowed_actions"] == []
    assert body["decision"]["resolution"] == {
        "action": "APPROVE",
        "note": "Coordinator reviewed the synthetic safety context.",
        "actor": "demo-coordinator",
        "outcome": "recorded_no_runtime_resumer",
        "automatic_continuation": False,
        "resolved_at": body["decision"]["resolved_at"],
    }
    assert client.post(f"/interrupts/{record.id}/resolve", json=request).status_code == 409
    resolved = client.get("/interrupts", params={"status": "RESOLVED"}).json()
    assert [item["interrupt_id"] for item in resolved] == [record.id]
    audit = [
        item
        for item in context.store.list_ledger()
        if item.category == "human_decision"
    ]
    assert len(audit) == 1
    assert audit[0].decision == "APPROVED"
    assert audit[0].details == {
        "interrupt_id": record.id,
        "actor": "demo-coordinator",
    }


def test_invalid_or_stale_resolution_cannot_mutate_interrupt(store) -> None:
    context, client = client_for(store)
    invalid = create_red_decision(context, "phase2-invalid")
    invalid_response = client.post(
        f"/interrupts/{invalid.id}/resolve",
        json={
            "action": "ACKNOWLEDGE",
            "actor": "demo-coordinator",
            "expected_version": invalid.version,
        },
    )
    assert invalid_response.status_code == 422
    assert context.store.get_interrupt(invalid.id).status == InterruptStatus.OPEN

    stale = create_red_decision(context, "phase2-stale")
    stale_response = client.post(
        f"/interrupts/{stale.id}/resolve",
        json={
            "action": "VETO",
            "actor": "demo-coordinator",
            "expected_version": stale.version + 1,
        },
    )
    assert stale_response.status_code == 409
    assert stale_response.json()["detail"]["code"] == "interrupt_version_conflict"
    assert context.store.get_interrupt(stale.id).status == InterruptStatus.OPEN


def test_pending_projection_and_authoritative_cancellation_states(store) -> None:
    context, client = client_for(store)
    pending = context.pending.create(
        "send_message",
        "phase2-pending",
        {
            "shift_id": "shift-1",
            "volunteer_id": "vol-09",
            "body": "private-message-payload",
        },
        now=NOW,
        delay_minutes=10,
    )
    projected = client.get("/pending", params={"status": "PENDING"})
    assert projected.status_code == 200
    item = projected.json()[0]
    assert item["effect_id"] == pending.id
    assert item["can_cancel"] is True
    assert item["related_shift"]["site_name"] == "River Hall"
    assert item["result_summary"] is None
    assert "private-message-payload" not in projected.text

    cancelled = client.post(
        f"/pending/{pending.id}/cancel",
        json={"actor": "demo-coordinator", "expected_status": "PENDING"},
    )
    assert cancelled.status_code == 200
    assert cancelled.json() == {"cancelled": True, "reason": "cancelled"}
    authoritative = client.get("/pending", params={"status": "CANCELLED"}).json()
    assert authoritative[0]["effect_id"] == pending.id
    assert authoritative[0]["can_cancel"] is False
    assert client.post(f"/pending/{pending.id}/cancel").json() == {
        "cancelled": False,
        "reason": "already_cancelled",
    }
    audit = [
        entry
        for entry in context.store.list_ledger()
        if entry.decision == "CANCELLED"
    ]
    assert len(audit) == 1


def test_pending_cancel_reports_settlement_race_states_and_unknown(store) -> None:
    context, client = client_for(store)
    cases = [
        ("SETTLING", PendingStatus.SETTLING),
        ("SETTLED", PendingStatus.SETTLED),
        ("FAILED", PendingStatus.FAILED),
    ]
    for label, target in cases:
        item = context.pending.create(
            "send_message",
            f"phase2-{label.lower()}",
            {"shift_id": "shift-1"},
            now=NOW,
            delay_minutes=10,
        )
        context.store.transition_pending(item.id, PendingStatus.PENDING, target)
        response = client.post(f"/pending/{item.id}/cancel")
        assert response.status_code == 200
        assert response.json() == {
            "cancelled": False,
            "reason": f"already_{label.lower()}",
        }
    assert client.post("/pending/unknown/cancel").status_code == 404


def test_decision_feed_is_safe_filterable_and_cursor_paginated(store) -> None:
    context, client = client_for(store)
    ledger = DecisionLedger(context.store)
    ledger.record(
        "ranking",
        "CANDIDATE_RANKED",
        routing_class=RoutingClass.GREEN,
        reason="highest_eligible_score",
        details={"shift_id": "shift-1", "raw": "private-ledger-detail"},
        key="feed-green",
    )
    ledger.record(
        "routing",
        "PENDING_CREATED",
        routing_class=RoutingClass.YELLOW,
        reason="settlement_window",
        details={"shift_id": "shift-1", "pending_id": "pending-safe"},
        key="feed-yellow",
    )
    ledger.record(
        "routing",
        "INTENTIONAL_SILENCE",
        routing_class=RoutingClass.DEFER,
        reason="contact_cap_reached",
        details={"shift_id": "shift-1"},
        key="feed-silent",
    )

    first = client.get("/feed", params={"limit": 2})
    assert first.status_code == 200
    page = first.json()
    assert len(page["items"]) == 2
    assert page["has_more"] is True
    assert page["next_cursor"] == page["items"][-1]["id"]
    assert page["items"][0]["shift_name"] == "River Hall"
    assert "private-ledger-detail" not in first.text

    second = client.get(
        "/feed",
        params={"limit": 2, "cursor": page["next_cursor"]},
    ).json()
    assert {item["id"] for item in page["items"]}.isdisjoint(
        {item["id"] for item in second["items"]}
    )
    silent = client.get("/feed", params={"route": "SILENT/DEFER"}).json()
    assert [item["route"] for item in silent["items"]] == ["SILENT/DEFER"]
    green = client.get(
        "/feed",
        params={"route": "GREEN", "category": "ranking", "shift_id": "shift-1"},
    ).json()
    assert [item["id"] for item in green["items"]] == ["feed-green"]
    assert client.get("/feed", params={"cursor": "unknown"}).status_code == 400
