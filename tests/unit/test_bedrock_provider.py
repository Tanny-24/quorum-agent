from __future__ import annotations

from collections.abc import AsyncIterable
from typing import Any

import pytest
from pydantic import BaseModel
from strands.models import Model

from quorum.agents.coordinator import create_coordinator_agent
from quorum.agents.models import create_model
from quorum.agents.negotiator import create_negotiator_agent
from quorum.config import Settings


class NoCallModel(Model):
    """Minimal injected model; constructing agents must not invoke it."""

    def __init__(self) -> None:
        self.config = {"model_id": "injected-bedrock-test"}

    def update_config(self, **model_config: Any) -> None:
        self.config.update(model_config)

    def get_config(self) -> dict[str, Any]:
        return self.config

    async def stream(
        self, messages, tool_specs=None, system_prompt=None, **kwargs
    ) -> AsyncIterable[dict]:
        raise AssertionError("unit tests must not call Amazon Bedrock")
        yield

    async def structured_output(
        self,
        output_model: type[BaseModel],
        prompt,
        system_prompt=None,
        **kwargs,
    ) -> AsyncIterable[dict]:
        raise AssertionError("unit tests must not call Amazon Bedrock")
        yield


def test_bedrock_factory_uses_region_profile_and_bounded_params(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeBedrockModel:
        def __init__(self, **config):
            captured.update(config)

    monkeypatch.setattr("quorum.agents.models.BedrockModel", FakeBedrockModel)
    settings = Settings(
        model_provider="bedrock",
        model_id="us.amazon.nova-micro-v1:0",
        aws_region="us-east-1",
    )

    create_model(settings)

    assert captured == {
        "region_name": "us-east-1",
        "model_id": "us.amazon.nova-micro-v1:0",
        "temperature": 0,
        "max_tokens": 512,
    }
    assert "boto_session" not in captured


def test_environment_defaults_are_provider_aware(monkeypatch, tmp_path) -> None:
    for name in (
        "QUORUM_MODEL_PROVIDER",
        "QUORUM_MODEL_ID",
        "AWS_REGION",
        "AWS_DEFAULT_REGION",
    ):
        monkeypatch.delenv(name, raising=False)
    missing_env = tmp_path / "missing.env"

    bedrock = Settings.from_env(missing_env)
    assert bedrock.model_provider == "bedrock"
    assert bedrock.model_id == "us.amazon.nova-micro-v1:0"
    assert bedrock.aws_region == "us-east-1"

    monkeypatch.setenv("QUORUM_MODEL_PROVIDER", "gemini")
    gemini = Settings.from_env(missing_env)
    assert gemini.model_id == "gemini-3.6-flash"


def test_bedrock_classifier_override_is_used(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeBedrockModel:
        def __init__(self, **config):
            captured.update(config)

    monkeypatch.setattr("quorum.agents.models.BedrockModel", FakeBedrockModel)
    settings = Settings(
        model_provider="bedrock",
        model_id="us.amazon.nova-micro-v1:0",
        bedrock_classifier_model="us.amazon.nova-lite-v1:0",
    )

    create_model(settings, classifier=True)

    assert captured["model_id"] == "us.amazon.nova-lite-v1:0"
    assert captured["max_tokens"] == 128


@pytest.mark.parametrize(
    ("settings", "message"),
    [
        (
            Settings(
                model_provider="bedrock",
                model_id="",
                bedrock_reasoner_model=None,
            ),
            "QUORUM_MODEL_ID",
        ),
        (
            Settings(model_provider="bedrock", aws_region=""),
            "AWS_REGION",
        ),
    ],
)
def test_bedrock_factory_fails_closed_for_missing_config(settings, message) -> None:
    with pytest.raises(RuntimeError, match=message):
        create_model(settings)


def test_coordinator_and_negotiator_receive_bedrock_factory_model(
    monkeypatch, tmp_path
) -> None:
    injected = NoCallModel()
    providers: list[str] = []

    def fake_factory(settings: Settings):
        providers.append(settings.model_provider)
        return injected

    monkeypatch.setattr("quorum.agents.coordinator.create_model", fake_factory)
    monkeypatch.setattr("quorum.agents.negotiator.create_model", fake_factory)
    settings = Settings(
        model_provider="bedrock",
        session_dir=tmp_path / "sessions",
    )

    coordinator = create_coordinator_agent(settings, [])
    negotiator = create_negotiator_agent(settings, "shift-1", "vol-01", [])

    assert coordinator.model is injected
    assert negotiator.model is injected
    assert providers == ["bedrock", "bedrock"]
