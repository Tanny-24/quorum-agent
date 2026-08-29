"""Static reversibility and default routing metadata owned by code, not models."""

from __future__ import annotations

from dataclasses import dataclass

from quorum.domain.models import RoutingClass


@dataclass(frozen=True)
class ToolMetadata:
    name: str
    side_effecting: bool
    reversibility: int
    default_route: RoutingClass


TOOL_REGISTRY = {
    name: ToolMetadata(name, False, 3, RoutingClass.GREEN)
    for name in ("get_shift", "detect_staffing_gap", "list_candidates", "get_contact_history", "find_transport_option")
}
TOOL_REGISTRY.update(
    {
        "send_message": ToolMetadata("send_message", True, 2, RoutingClass.YELLOW),
        "open_negotiation": ToolMetadata("open_negotiation", True, 3, RoutingClass.GREEN),
        "confirm_assignment": ToolMetadata("confirm_assignment", True, 2, RoutingClass.YELLOW),
        "close_negotiation": ToolMetadata("close_negotiation", True, 3, RoutingClass.GREEN),
        "request_escalation": ToolMetadata("request_escalation", True, 1, RoutingClass.RED),
        "log_decision": ToolMetadata("log_decision", True, 3, RoutingClass.GREEN),
    }
)
