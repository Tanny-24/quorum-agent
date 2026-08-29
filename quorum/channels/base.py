"""Provider-neutral channel contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol

from pydantic import BaseModel


class NormalizedMessage(BaseModel):
    provider: str
    provider_msg_id: str
    from_ref: str
    text: str
    received_at: datetime


class SendResult(BaseModel):
    accepted: bool
    provider_msg_id: str | None = None


class Channel(Protocol):
    def send(self, recipient_ref: str, text: str) -> SendResult: ...
    def normalise(self, payload: dict[str, Any]) -> NormalizedMessage: ...
