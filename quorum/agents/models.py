"""Provider-agnostic Strands model construction."""

from __future__ import annotations

from strands.models import BedrockModel, Model
from strands.models.gemini import GeminiModel

from quorum.config import Settings


def create_model(settings: Settings, *, classifier: bool = False) -> Model:
    """Build the configured Strands model without coupling agents to a provider."""
    provider = settings.model_provider.strip().lower()
    if provider == "gemini":
        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY must be configured in the local environment")
        if not settings.model_id:
            raise RuntimeError("QUORUM_MODEL_ID must name an available Gemini model")
        return GeminiModel(
            client_args={"api_key": settings.gemini_api_key},
            model_id=settings.model_id,
            params={
                "temperature": 0,
                "max_output_tokens": 512 if classifier else 768,
                "thinking_config": {"thinking_level": "minimal"},
            },
        )
    if provider == "bedrock":
        if not settings.aws_region:
            raise RuntimeError("AWS_REGION must be configured for Amazon Bedrock")
        model_id = (
            (settings.bedrock_classifier_model or settings.model_id)
            if classifier
            else (settings.bedrock_reasoner_model or settings.model_id)
        )
        if not model_id or not model_id.strip():
            raise RuntimeError("QUORUM_MODEL_ID must name an Amazon Bedrock model or inference profile")
        return BedrockModel(
            region_name=settings.aws_region,
            model_id=model_id,
            temperature=0,
            max_tokens=128 if classifier else 512,
        )
    raise ValueError(f"Unsupported QUORUM_MODEL_PROVIDER: {settings.model_provider!r}")
