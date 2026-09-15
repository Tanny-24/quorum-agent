"""Environment-driven configuration without secret logging."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

DEFAULT_BEDROCK_MODEL_ID = "us.amazon.nova-micro-v1:0"
DEFAULT_BEDROCK_REGION = "us-east-1"
DEFAULT_GEMINI_MODEL_ID = "gemini-3.6-flash"


@dataclass(frozen=True)
class Settings:
    app_env: str = "development"
    session_dir: Path = Path("_runtime/sessions")
    attention_budget: int = 2
    store: str = "memory"
    model_provider: str = "bedrock"
    model_id: str = DEFAULT_BEDROCK_MODEL_ID
    gemini_api_key: str | None = None
    aws_region: str = DEFAULT_BEDROCK_REGION
    bedrock_reasoner_model: str | None = None
    bedrock_classifier_model: str | None = None
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None

    @classmethod
    def from_env(cls, env_file: Path | None = None) -> "Settings":
        load_dotenv(dotenv_path=env_file, override=False)
        provider = os.getenv("QUORUM_MODEL_PROVIDER", "bedrock").strip().lower()
        default_model = (
            DEFAULT_GEMINI_MODEL_ID
            if provider == "gemini"
            else DEFAULT_BEDROCK_MODEL_ID
        )
        return cls(
            app_env=os.getenv("APP_ENV", "development"),
            session_dir=Path(os.getenv("QUORUM_SESSION_DIR", "_runtime/sessions")),
            attention_budget=int(os.getenv("QUORUM_ATTENTION_BUDGET", "2")),
            store=os.getenv("QUORUM_STORE", "memory"),
            model_provider=provider,
            model_id=os.getenv("QUORUM_MODEL_ID", default_model).strip(),
            gemini_api_key=os.getenv("GEMINI_API_KEY") or None,
            aws_region=os.getenv(
                "AWS_REGION",
                os.getenv("AWS_DEFAULT_REGION", DEFAULT_BEDROCK_REGION),
            ).strip(),
            bedrock_reasoner_model=os.getenv("BEDROCK_REASONER_MODEL") or None,
            bedrock_classifier_model=os.getenv("BEDROCK_CLASSIFIER_MODEL") or None,
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN") or None,
            telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID") or None,
        )
