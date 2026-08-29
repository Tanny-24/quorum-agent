"""BeforeToolCallEvent gate for GREEN, YELLOW, RED, and silence decisions."""

from __future__ import annotations

from typing import Any

from strands.hooks import BeforeToolCallEvent, HookProvider, HookRegistry
from strands.interrupt import InterruptException

from quorum.domain.models import RoutingClass
from quorum.persistence.memory import MemoryStore
from quorum.services.escalation import EscalationEngine
from quorum.services.interrupts import InterruptService
from quorum.services.ledger import DecisionLedger
from quorum.services.pending_effects import PendingEffectService
from quorum.tools.registry import TOOL_REGISTRY
from quorum.utils import stable_key


class RoutingHook(HookProvider):
    """Keep policy and reversibility outside model control."""

    def __init__(self, store: MemoryStore, session_id: str, attention_allowance: int = 2) -> None:
        self.store = store
        self.session_id = session_id
        self.engine = EscalationEngine(store, allowance=attention_allowance)
        self.pending = PendingEffectService(store)
        self.interrupts = InterruptService(store)
        self.ledger = DecisionLedger(store)

    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        registry.add_callback(BeforeToolCallEvent, self.route_tool)

    def route_tool(self, event: BeforeToolCallEvent) -> None:
        name = event.tool_use["name"]
        metadata = TOOL_REGISTRY.get(name)
        if metadata is None or not metadata.side_effecting:
            return
        inputs = dict(event.tool_use.get("input", {}))
        idempotency_key = str(inputs.get("idempotency_key") or stable_key(name, inputs))
        if inputs.get("policy_block"):
            event.cancel_tool = f"Hard policy blocked action: {inputs['policy_block']}"
            self.ledger.record("policy", "BLOCKED", reason=str(inputs["policy_block"]), key=f"policy:{idempotency_key}")
            return
        if metadata.default_route == RoutingClass.GREEN:
            self.ledger.record("routing", "EXECUTE", routing_class=RoutingClass.GREEN, key=f"route:{idempotency_key}")
            return
        if metadata.default_route == RoutingClass.YELLOW:
            pending = self.pending.create(name, idempotency_key, inputs)
            self.ledger.record(
                "routing",
                "PENDING_CREATED",
                routing_class=RoutingClass.YELLOW,
                details={"pending_id": pending.id},
                key=f"route:{idempotency_key}",
            )
            event.cancel_tool = f"Queued for settlement as {pending.id}"
            return

        decision = self.engine.route(
            idempotency_key,
            consequence=int(inputs.get("consequence", 4)),
            uncertainty=float(inputs.get("uncertainty", 1.0)),
            urgency=float(inputs.get("urgency", 1.0)),
            reversibility=metadata.reversibility,
            safety_category=inputs.get("safety_category"),
        )
        if decision.routing_class in {RoutingClass.DEFER, RoutingClass.GREEN}:
            event.cancel_tool = "Action intentionally deferred"
            self.ledger.silence("below_attention_threshold", key=f"route:{idempotency_key}")
            return
        if decision.routing_class == RoutingClass.YELLOW:
            pending = self.pending.create(name, idempotency_key, inputs)
            event.cancel_tool = f"Queued for settlement as {pending.id}"
            return
        record = self.interrupts.create(
            self.session_id,
            idempotency_key,
            {"tool": name, "inputs": inputs, "routing": decision.model_dump(mode="json")},
        )
        try:
            response = event.interrupt(
                "quorum_red_decision",
                reason={"interrupt_record_id": record.id, "tool": name, "routing": decision.model_dump(mode="json")},
            )
        except InterruptException as exc:
            record.strands_interrupt_id = exc.interrupt.id
            self.store.update_interrupt(record)
            raise
        approved = response is True or str(response).lower() in {"y", "yes", "approve"}
        self.interrupts.resolve_once(record.id, "approved" if approved else "vetoed")
        self.ledger.record(
            "interrupt",
            "RESOLVED" if approved else "VETOED",
            routing_class=RoutingClass.RED,
            details={"interrupt_id": record.id},
            key=f"interrupt-resolution:{record.id}",
        )
        if not approved:
            event.cancel_tool = "Human vetoed the RED action"
