"""Provider-independent messaging channels."""

from .base import Channel, NormalizedMessage, SendResult
from .telegram import TelegramChannel

__all__ = ["Channel", "NormalizedMessage", "SendResult", "TelegramChannel"]
