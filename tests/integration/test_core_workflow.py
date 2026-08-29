from __future__ import annotations

from collections.abc import AsyncIterable
from datetime import timedelta
from typing import Any

from pydantic import BaseModel
from strands.models import Model

from quorum.agents.coordinator import create_coordinator_agent
from quorum.config import Settings
from quorum.domain.models import ReplyIntent, Role, RoutingClass
from quorum.events.models import EventKind
from quorum.services.workflow import CoreWorkflow
from quorum.utils import utc_now


class EndTurnModel(Model):
    def __init__(self):
        self.config = {"model_id": "deterministic-session-test"}

    def update_config(self, **model_config: Any) -> None:
        self.config.update(model_config)

    def get_config(self) -> dict[str, Any]:
        return self.config

    async def structured_output(self, output_model: type[BaseModel], prompt, system_prompt=None, **kwargs):
        raise NotImplementedError
        yield

    async def stream(self, messages, tool_specs=None, system_prompt=None, **kwargs) -> AsyncIterable[dict]:
        yield {"messageStart": {"role": "assistant"}}
        yield {"contentBlockStart": {"contentBlockIndex": 0, "start": {}}}
        yield {"contentBlockDelta": {"contentBlockIndex": 0, "delta": {"text": "done"}}}
        yield {"contentBlockStop": {"contentBlockIndex": 0}}
        yield {"messageStop": {"stopReason": "end_turn"}}
        yield {
            "metadata": {
                "usage": {"inputTokens": 1, "outputTokens": 1, "totalTokens": 2},
                "metrics": {"latencyMs": 1},
            }
        }


def test_fresh_agent_restores_file_session_state(tmp_path) -> None:
    settings = Settings(session_dir=tmp_path / "sessions")
    first = create_coordinator_agent(settings, [], model=EndTurnModel())
    first.state.set("durable", "yes")
    assert first("persist state").stop_reason == "end_turn"
    second = create_coordinator_agent(settings, [], model=EndTurnModel())
    assert second.state.get("durable") == "yes"


def test_three_end_to_end_scenarios(store) -> None:
    workflow = CoreWorkflow(store)
    gaps_a = workflow.staffing_event(EventKind.VOLUNTEER_CANCELLED, "shift-1", "integration-a")
    candidate_a = workflow.ranker.rank("shift-1", Role.DRIVER)[0]
    thread_a = workflow.open_thread("shift-1", candidate_a.volunteer_id)
    workflow.queue_outreach(thread_a, "Can you cover this synthetic shift?", delay_minutes=0)
    assert workflow.settle_outreach(utc_now() + timedelta(seconds=1)) == 1
    assert workflow.reply_and_assign(thread_a, "yes", Role.DRIVER)["confirmed"] is True
    assert workflow.resolve_gap_if_staffed(gaps_a[0].id)

    gaps_b = workflow.staffing_event(EventKind.NO_SHOW, "shift-2", "integration-b")
    candidate_b = workflow.ranker.rank("shift-2", Role.DRIVER)[0]
    thread_b = workflow.open_thread("shift-2", candidate_b.volunteer_id)
    result_b = workflow.reply_and_assign(thread_b, "can do but I need a ride", Role.DRIVER)
    assert result_b["classification"].intent == ReplyIntent.ACCEPT_IF
    assert result_b["transport"]["available"] is True
    assert workflow.resolve_gap_if_staffed(gaps_b[0].id)

    thread_c = workflow.open_thread("shift-3", "vol-09")
    result_c = workflow.reply_and_assign(thread_c, "I am injured and want to complain", Role.SORTER)
    assert result_c["routing"].routing_class == RoutingClass.RED
    assert len(store.list_open_interrupts()) == 1
