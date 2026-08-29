"""Fresh-per-invocation Negotiator Agent factory."""

from __future__ import annotations

from pathlib import Path

from strands import Agent
from strands.models import BedrockModel, Model
from strands.session import FileSessionManager

from quorum.agents.prompts import NEGOTIATOR_PROMPT
from quorum.config import Settings


def negotiation_session_id(shift_id: str, volunteer_id: str) -> str:
    return f"nego:{shift_id}:{volunteer_id}"


def create_negotiator_agent(
    settings: Settings,
    shift_id: str,
    volunteer_id: str,
    tools: list[object],
    model: Model | None = None,
    hooks: list[object] | None = None,
) -> Agent:
    if model is None:
        if not settings.bedrock_reasoner_model:
            raise RuntimeError("BEDROCK_REASONER_MODEL must name a verified model")
        model = BedrockModel(
            region_name=settings.aws_region,
            model_id=settings.bedrock_reasoner_model,
            temperature=0,
            max_tokens=512,
        )
    storage = Path(settings.session_dir)
    storage.mkdir(parents=True, exist_ok=True)
    session_id = negotiation_session_id(shift_id, volunteer_id)
    return Agent(
        agent_id="negotiator",
        model=model,
        tools=tools,
        hooks=hooks,
        system_prompt=NEGOTIATOR_PROMPT,
        session_manager=FileSessionManager(session_id=session_id, storage_dir=str(storage)),
        callback_handler=None,
    )
