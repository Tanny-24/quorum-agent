"""Environment-driven configuration without secret logging."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    app_env: str = "development"
    session_dir: Path = Path("_runtime/sessions")
    attention_budget: int = 2
    store: str = "memory"
    aws_region: str = "us-west-2"
    bedrock_reasoner_model: str | None = None
    bedrock_classifier_model: str | None = None
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None

    @classmethod
    def from_env(cls, env_file: Path | None = None) -> "Settings":
        load_dotenv(dotenv_path=env_file, override=False)
        return cls(
            app_env=os.getenv("APP_ENV", "development"),
            session_dir=Path(os.getenv("QUORUM_SESSION_DIR", "_runtime/sessions")),
            attention_budget=int(os.getenv("QUORUM_ATTENTION_BUDGET", "2")),
            store=os.getenv("QUORUM_STORE", "memory"),
            aws_region=os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "us-west-2")),
            bedrock_reasoner_model=os.getenv("BEDROCK_REASONER_MODEL") or None,
            bedrock_classifier_model=os.getenv("BEDROCK_CLASSIFIER_MODEL") or None,
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN") or None,
            telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID") or None,
        )
