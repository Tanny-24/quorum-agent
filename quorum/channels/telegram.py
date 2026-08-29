"""Telegram Bot API channel with no provider leakage into domain code."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from quorum.channels.base import NormalizedMessage, SendResult


class TelegramChannel:
    def __init__(self, bot_token: str, client: httpx.Client | Any | None = None) -> None:
        if not bot_token:
            raise ValueError("Telegram bot token is required")
        self._base_url = f"https://api.telegram.org/bot{bot_token}"
        self._client = client or httpx.Client(timeout=15)

    def send(self, recipient_ref: str, text: str) -> SendResult:
        try:
            response = self._client.post(
                f"{self._base_url}/sendMessage",
                json={"chat_id": recipient_ref, "text": text},
            )
            response.raise_for_status()
        except httpx.HTTPError:
            raise RuntimeError("Telegram send request failed") from None
        payload = response.json()
        if not payload.get("ok"):
            raise RuntimeError("Telegram rejected the message")
        message_id = payload.get("result", {}).get("message_id")
        return SendResult(accepted=True, provider_msg_id=str(message_id) if message_id is not None else None)

    def normalise(self, payload: dict[str, Any]) -> NormalizedMessage:
        message = payload.get("message") or payload.get("edited_message")
        if not isinstance(message, dict):
            raise ValueError("Telegram update contains no supported message")
        sender = message.get("from") or {}
        text = message.get("text")
        if not isinstance(text, str):
            raise ValueError("Telegram message contains no text")
        timestamp = datetime.fromtimestamp(int(message["date"]), tz=timezone.utc)
        return NormalizedMessage(
            provider="telegram",
            provider_msg_id=str(message["message_id"]),
            from_ref=str(sender.get("id", message.get("chat", {}).get("id", "unknown"))),
            text=text,
            received_at=timestamp,
        )

    def poll(self, offset: int | None = None, timeout: int = 20) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"timeout": timeout}
        if offset is not None:
            params["offset"] = offset
        try:
            response = self._client.get(f"{self._base_url}/getUpdates", params=params)
            response.raise_for_status()
        except httpx.HTTPError:
            raise RuntimeError("Telegram polling request failed") from None
        payload = response.json()
        if not payload.get("ok"):
            raise RuntimeError("Telegram getUpdates failed")
        return list(payload.get("result", []))
