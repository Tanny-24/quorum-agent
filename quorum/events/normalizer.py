"""Translate provider-neutral messages into core events."""

from __future__ import annotations

from quorum.channels.base import NormalizedMessage
from quorum.events.models import EventKind, QuorumEvent
from quorum.utils import stable_id, stable_key


def message_to_event(message: NormalizedMessage) -> QuorumEvent:
    key = stable_key(message.provider, message.provider_msg_id)
    return QuorumEvent(
        id=stable_id("event", key),
        kind=EventKind.VOLUNTEER_REPLY,
        idempotency_key=key,
        occurred_at=message.received_at,
        payload={"from_ref": message.from_ref, "text": message.text, "provider": message.provider},
    )
