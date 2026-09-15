"""Run exactly four bounded live Strands/Bedrock validation scenarios.

This script is intentionally excluded from pytest. It reads credentials only
through boto3's standard AWS credential chain and performs no external writes.
"""

from __future__ import annotations

import json
import re
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import boto3
from strands import Agent, tool

from quorum.agents.coordinator import create_coordinator_agent
from quorum.agents.models import create_model
from quorum.agents.negotiator import create_negotiator_agent
from quorum.config import Settings
from quorum.data.loader import seed_store
from quorum.persistence.memory import MemoryStore
from quorum.tools.core import build_tools


def tool_uses(messages: list[dict[str, Any]]) -> list[str]:
    names: list[str] = []
    for message in messages:
        for block in message.get("content", []):
            tool_use = block.get("toolUse")
            if tool_use and tool_use.get("name"):
                names.append(str(tool_use["name"]))
    return names


def safe_error(exc: Exception) -> str:
    detail = str(exc)
    detail = re.sub(r"arn:aws[^\s,\]]+", "[REDACTED_AWS_ARN]", detail)
    detail = re.sub(r"\b\d{12}\b", "[REDACTED_AWS_ACCOUNT]", detail)
    return detail[:500]


def run_validation(settings: Settings) -> dict[str, object]:
    session = boto3.Session()
    if session.get_credentials() is None:
        raise RuntimeError("No credentials were found in the standard AWS credential chain")
    # Prove authentication and verify that the configured system inference
    # profile exists in the selected region without printing account metadata.
    session.client("sts", region_name=settings.aws_region).get_caller_identity()
    if settings.model_id.startswith(("us.", "eu.", "apac.", "global.")):
        session.client("bedrock", region_name=settings.aws_region).get_inference_profile(
            inferenceProfileIdentifier=settings.model_id
        )

    with TemporaryDirectory(prefix="quorum-bedrock-") as temp_dir:
        isolated = replace(settings, session_dir=Path(temp_dir) / "sessions")
        store = seed_store(MemoryStore())
        tools = build_tools(store)
        model = create_model(isolated)

        smoke = Agent(model=model, callback_handler=None)(
            "Reply exactly with this text and nothing else: QUORUM_BEDROCK_OK"
        )
        smoke_pass = str(smoke).strip() == "QUORUM_BEDROCK_OK"

        @tool
        def read_demo_label() -> str:
            """Return a harmless local synthetic label."""
            return "RIVERSIDE_SYNTHETIC"

        tool_agent = Agent(model=model, tools=[read_demo_label], callback_handler=None)
        tool_result = tool_agent(
            "Call read_demo_label exactly once, then reply exactly with its result."
        )
        tool_pass = (
            "read_demo_label" in tool_uses(tool_agent.messages)
            and "RIVERSIDE_SYNTHETIC" in str(tool_result)
        )

        coordinator = create_coordinator_agent(isolated, tools, model=model)
        coordinator_result = coordinator(
            "Call get_shift exactly once for shift-1. Then reply with only its shift ID."
        )
        coordinator_pass = (
            "get_shift" in tool_uses(coordinator.messages)
            and "shift-1" in str(coordinator_result)
        )

        negotiator = create_negotiator_agent(
            isolated,
            "shift-2",
            "vol-04",
            [],
            model=model,
        )
        negotiator_result = negotiator(
            "A synthetic volunteer says they need time to decide. Reply with one calm "
            "question under 20 words. Do not call a tool."
        )
        negotiator_pass = bool(str(negotiator_result).strip()) and not tool_uses(
            negotiator.messages
        )

        return {
            "region": settings.aws_region,
            "model": settings.model_id,
            "smoke": "PASS" if smoke_pass else "FAIL",
            "tool_call": "PASS" if tool_pass else "FAIL",
            "coordinator": "PASS" if coordinator_pass else "FAIL",
            "negotiator": "PASS" if negotiator_pass else "FAIL",
        }


def main() -> int:
    settings = Settings.from_env()
    if settings.model_provider != "bedrock":
        print(json.dumps({"status": "blocked", "reason": "Bedrock is not active"}))
        return 2
    try:
        result = run_validation(settings)
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "detail": safe_error(exc),
                },
                indent=2,
            )
        )
        return 1
    print(json.dumps(result, indent=2))
    checks = ("smoke", "tool_call", "coordinator", "negotiator")
    return 0 if all(result[key] == "PASS" for key in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
