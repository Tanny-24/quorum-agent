"""Deterministic model provider used only for offline SDK integration tests.

This substitutes only the unavailable network model. The Agent, tools, hooks,
interrupt handling, FileSessionManager, files, and process boundaries are real.
It is never selected by the normal acceptance command.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterable
from typing import Any

from pydantic import BaseModel
from strands.models import Model
from strands.types.content import Messages
from strands.types.streaming import StreamEvent
from strands.types.tools import ToolChoice, ToolSpec

from spike_server import DEFAULT_BODY, DEFAULT_RECIPIENT


class DeterministicTestModel(Model):
    """Emit the fixed observable tool sequence required by this spike."""

    def __init__(self) -> None:
        self.config: dict[str, Any] = {"model_id": "deterministic-offline-test-model"}

    def update_config(self, **model_config: Any) -> None:
        self.config.update(model_config)

    def get_config(self) -> dict[str, Any]:
        return self.config

    async def structured_output(
        self,
        output_model: type[BaseModel],
        prompt: Messages,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterable[dict[str, Any]]:
        raise NotImplementedError("The offline integration model does not implement structured output")
        yield  # pragma: no cover

    async def stream(
        self,
        messages: Messages,
        tool_specs: list[ToolSpec] | None = None,
        system_prompt: str | None = None,
        *,
        tool_choice: ToolChoice | None = None,
        **kwargs: Any,
    ) -> AsyncIterable[StreamEvent]:
        tool_results = [
            block["toolResult"]
            for message in messages
            for block in message["content"]
            if "toolResult" in block
        ]
        tool_uses = [
            block["toolUse"]
            for message in messages
            for block in message["content"]
            if "toolUse" in block
        ]

        if not any(tool_use["name"] == "list_volunteers" for tool_use in tool_uses):
            async for event in self._tool_call("offline-list-1", "list_volunteers", {}):
                yield event
            return

        if not any(tool_use["name"] == "send_message" for tool_use in tool_uses):
            if not any(result["toolUseId"] == "offline-list-1" for result in tool_results):
                raise RuntimeError("list_volunteers result was not observed before send_message")
            async for event in self._tool_call(
                "offline-send-1",
                "send_message",
                {"recipient": DEFAULT_RECIPIENT, "body": DEFAULT_BODY},
            ):
                yield event
            return

        if not any(result["toolUseId"] == "offline-send-1" for result in tool_results):
            raise RuntimeError("Model was called before interrupted send_message finished")

        async for event in self._text_response("Offline integration flow finished."):
            yield event

    async def _tool_call(
        self, tool_use_id: str, name: str, inputs: dict[str, Any]
    ) -> AsyncIterable[StreamEvent]:
        yield {"messageStart": {"role": "assistant"}}
        yield {
            "contentBlockStart": {
                "contentBlockIndex": 0,
                "start": {"toolUse": {"name": name, "toolUseId": tool_use_id}},
            }
        }
        yield {
            "contentBlockDelta": {
                "contentBlockIndex": 0,
                "delta": {"toolUse": {"input": json.dumps(inputs)}},
            }
        }
        yield {"contentBlockStop": {"contentBlockIndex": 0}}
        yield {"messageStop": {"stopReason": "tool_use"}}
        yield self._metadata()

    async def _text_response(self, text: str) -> AsyncIterable[StreamEvent]:
        yield {"messageStart": {"role": "assistant"}}
        yield {"contentBlockStart": {"contentBlockIndex": 0, "start": {}}}
        yield {"contentBlockDelta": {"contentBlockIndex": 0, "delta": {"text": text}}}
        yield {"contentBlockStop": {"contentBlockIndex": 0}}
        yield {"messageStop": {"stopReason": "end_turn"}}
        yield self._metadata()

    @staticmethod
    def _metadata() -> StreamEvent:
        return {
            "metadata": {
                "metrics": {"latencyMs": 1},
                "usage": {"inputTokens": 1, "outputTokens": 1, "totalTokens": 2},
            }
        }
