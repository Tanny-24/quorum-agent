"""Fresh-per-invocation Coordinator Agent factory."""

from __future__ import annotations

from pathlib import Path

from strands import Agent
from strands.models import Model
from strands.session import FileSessionManager

from quorum.agents.models import create_model
from quorum.agents.prompts import COORDINATOR_PROMPT
from quorum.config import Settings


def create_coordinator_agent(
    settings: Settings,
    tools: list[object],
    model: Model | None = None,
    hooks: list[object] | None = None,
) -> Agent:
    if model is None:
        model = create_model(settings)
    storage = Path(settings.session_dir)
    storage.mkdir(parents=True, exist_ok=True)
    return Agent(
        agent_id="coordinator",
        model=model,
        tools=tools,
        hooks=hooks,
        system_prompt=COORDINATOR_PROMPT,
        session_manager=FileSessionManager(session_id="org:riverside", storage_dir=str(storage)),
        callback_handler=None,
    )
