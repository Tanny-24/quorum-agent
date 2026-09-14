"""Send exactly one explicit Telegram smoke-test message."""

from quorum.channels.telegram import TelegramChannel
from quorum.config import Settings


def main() -> int:
    settings = Settings.from_env()
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        print("SKIP: Telegram configuration is unavailable")
        return 2
    result = TelegramChannel(settings.telegram_bot_token).send(
        settings.telegram_chat_id, "QUORUM Gemini integration ready"
    )
    print(f"Telegram accepted={result.accepted}; provider message ID received={result.provider_msg_id is not None}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
