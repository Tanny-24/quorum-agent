"""Development polling path using the same Telegram normalizer as webhooks."""

from quorum.channels.telegram import TelegramChannel
from quorum.config import Settings


def main() -> int:
    settings = Settings.from_env()
    if not settings.telegram_bot_token:
        print("SKIP: Telegram configuration is unavailable")
        return 2
    channel = TelegramChannel(settings.telegram_bot_token)
    updates = channel.poll(timeout=1)
    normalized = []
    for update in updates:
        try:
            normalized.append(channel.normalise(update))
        except ValueError:
            continue
    print(f"Normalized {len(normalized)} text message(s); private identifiers omitted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
