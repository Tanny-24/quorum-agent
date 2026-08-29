from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from botocore.exceptions import ClientError
import pytest
from strands.interrupt import Interrupt, InterruptException

from quorum.domain.models import Assignment, PendingStatus, Role, RoutingClass
from quorum.hooks.routing import RoutingHook
from quorum.persistence.dynamodb import DynamoDBStore
from quorum.services.escalation import (
    BASE_THRESHOLD,
    CRITICAL_LINE,
    ONE_REMAINING_THRESHOLD,
    EscalationEngine,
    pessimistic_uncertainty,
)
from quorum.services.interrupts import InterruptService
from quorum.services.ledger import DecisionLedger
from quorum.services.pending_effects import PendingEffectService
from quorum.utils import stable_id


def test_attention_threshold_depletion_duplicate_and_critical_override(store) -> None:
    engine = EscalationEngine(store)
    assert engine.threshold() == BASE_THRESHOLD
    first = engine.route("decision-1", consequence=5, uncertainty=0.8, urgency=0.8, reversibility=1)
    assert first.routing_class == RoutingClass.RED and first.budget_spent
    assert engine.threshold() == ONE_REMAINING_THRESHOLD
    engine.route("decision-1", consequence=5, uncertainty=0.8, urgency=0.8, reversibility=1)
    assert store.get_budget("budget:riverside").spent == 1
    engine.route("decision-2", consequence=5, uncertainty=0.8, urgency=0.8, reversibility=1)
    assert engine.threshold() == CRITICAL_LINE
    critical = engine.route("decision-3", consequence=5, uncertainty=1, urgency=1, reversibility=1)
    assert critical.routing_class == RoutingClass.RED and critical.budget_override
    assert store.get_budget("budget:riverside").overrides == 1
    subcritical = engine.route("decision-4", consequence=2, uncertainty=0.6, urgency=0.8, reversibility=1)
    assert subcritical.routing_class == RoutingClass.YELLOW


def test_layer_zero_safety_bypasses_tiny_ev_and_empty_pool_is_max_uncertainty(store) -> None:
    decision = EscalationEngine(store).route(
        "injury-1",
        consequence=1,
        uncertainty=0.01,
        urgency=0.01,
        reversibility=3,
        safety_category="injury",
    )
    assert decision.routing_class == RoutingClass.RED
    assert decision.ev_score is None
    assert pessimistic_uncertainty(0.1, 0.2, empty_pool=True) == 1.0


def test_pending_create_settle_cancel_and_race(store) -> None:
    service = PendingEffectService(store)
    now = datetime.now(timezone.utc)
    due = service.create("send_message", "effect-1", {"body": "synthetic"}, now=now, delay_minutes=0)
    settled = service.settle_due({"send_message": lambda item: {"ok": True}}, now + timedelta(seconds=1))
    assert settled[0].status == PendingStatus.SETTLED
    assert service.cancel(due.id) == (False, "already_settled")

    cancellable = service.create("send_message", "effect-2", {}, now=now, delay_minutes=10)
    assert service.cancel(cancellable.id) == (True, "cancelled")

    racing = service.create("send_message", "effect-race", {}, now=now, delay_minutes=0)
    with ThreadPoolExecutor(max_workers=2) as pool:
        cancel_future = pool.submit(service.cancel, racing.id)
        settle_future = pool.submit(
            service.settle_due, {"send_message": lambda item: {"ok": True}}, now + timedelta(seconds=1)
        )
        cancelled = cancel_future.result()[0]
        settled_count = len(settle_future.result())
    assert int(cancelled) + settled_count == 1


def test_external_effect_reservation_suppresses_duplicate(store) -> None:
    first, _ = store.begin_effect("stable-message-key")
    store.complete_effect("stable-message-key", {"accepted": True})
    second, existing = store.begin_effect("stable-message-key")
    assert first is True
    assert second is False
    assert existing == {"accepted": True}


def test_assignment_capacity_race_allows_exactly_one(store) -> None:
    shift = store.get_shift("shift-1")

    def confirm(volunteer_id: str):
        assignment = Assignment(
            id=stable_id("assignment", volunteer_id),
            shift_id=shift.id,
            volunteer_id=volunteer_id,
            role=Role.DRIVER,
            confirmed_at=datetime.now(timezone.utc),
        )
        return store.confirm_assignment(assignment, 1)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(confirm, ["vol-02", "vol-03"]))
    assert sum(1 for confirmed, _, _ in results if confirmed) == 1
    assert sorted(reason for _, _, reason in results) == ["already_filled", "confirmed"]


def test_interrupt_resolution_is_idempotent_and_resumes_once(store) -> None:
    service = InterruptService(store)
    record = service.create("org:riverside", "red-1", {"reason": "synthetic injury"})
    calls = []
    first = service.resolve_once(record.id, "approved", lambda item, decision: calls.append(decision))
    second = service.resolve_once(record.id, "approved", lambda item, decision: calls.append(decision))
    assert first[0] is True
    assert second[0] is False
    assert calls == ["approved"]


def test_interrupt_failure_releases_claim_for_retry(store) -> None:
    service = InterruptService(store)
    record = service.create("org:riverside", "red-retry", {"reason": "synthetic"})
    try:
        service.resolve_once(record.id, "approved", lambda item, decision: (_ for _ in ()).throw(RuntimeError("fail")))
    except RuntimeError:
        pass
    else:
        raise AssertionError("Expected resume failure")
    assert store.interrupts[record.id].status.value == "OPEN"


def test_routing_hook_green_yellow_red_and_silence_ledger(store) -> None:
    hook = RoutingHook(store, "org:riverside")
    green = SimpleNamespace(tool_use={"name": "open_negotiation", "input": {"idempotency_key": "g"}}, cancel_tool=False)
    hook.route_tool(green)
    assert green.cancel_tool is False

    yellow = SimpleNamespace(tool_use={"name": "send_message", "input": {"idempotency_key": "y", "body": "x"}}, cancel_tool=False)
    hook.route_tool(yellow)
    assert "Queued for settlement" in yellow.cancel_tool

    red = SimpleNamespace(
        tool_use={"name": "request_escalation", "input": {"idempotency_key": "r", "safety_category": "injury"}},
        cancel_tool=False,
        interrupt=lambda name, reason: "n",
    )
    hook.route_tool(red)
    assert "vetoed" in red.cancel_tool.lower()
    deferred = SimpleNamespace(
        tool_use={
            "name": "request_escalation",
            "input": {
                "idempotency_key": "defer",
                "consequence": 1,
                "uncertainty": 0.1,
                "urgency": 0.1,
            },
        },
        cancel_tool=False,
    )
    hook.route_tool(deferred)
    assert deferred.cancel_tool == "Action intentionally deferred"
    DecisionLedger(store).silence("test_silence", key="silence-1")
    assert any(entry.decision == "INTENTIONAL_SILENCE" for entry in store.list_ledger())


def test_routing_hook_persists_strands_interrupt_id_before_propagating(store) -> None:
    hook = RoutingHook(store, "org:riverside")

    def raise_interrupt(name, reason):
        raise InterruptException(Interrupt(id="strands-interrupt-1", name=name, reason=reason))

    event = SimpleNamespace(
        tool_use={
            "name": "request_escalation",
            "input": {"idempotency_key": "persisted-red", "safety_category": "injury"},
        },
        cancel_tool=False,
        interrupt=raise_interrupt,
    )
    with pytest.raises(InterruptException):
        hook.route_tool(event)
    record = next(item for item in store.interrupts.values() if item.idempotency_key == "persisted-red")
    assert record.strands_interrupt_id == "strands-interrupt-1"


class FakeTable:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.calls = []

    def put_item(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail:
            raise ClientError({"Error": {"Code": "ConditionalCheckFailedException"}}, "PutItem")

    def update_item(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail:
            raise ClientError({"Error": {"Code": "ConditionalCheckFailedException"}}, "UpdateItem")


def test_dynamodb_adapter_uses_conditional_writes() -> None:
    table = FakeTable()
    adapter = DynamoDBStore(table)
    assert adapter.put_idempotent({"pk": "effect#1"})
    assert "attribute_not_exists" in table.calls[-1]["ConditionExpression"]
    assert adapter.transition("pending#1", "PENDING", "SETTLING")
    assert adapter.confirm_assignment("shift#role", {"id": "a"}, 1)
    assert adapter.spend_attention("budget#week", 2)
    assert not DynamoDBStore(FakeTable(fail=True)).put_idempotent({"pk": "effect#1"})
