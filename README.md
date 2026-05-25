# Telegram Forward

Mirror alerts from a private Telegram bot chat into another Telegram room, group, or channel.

This is for the case where another person's bot sends alerts to your private chat. A normal Bot API token cannot read that private chat, so this project runs a Telegram user-client forwarder with your own Telegram account.

## Setup

Install the dependency:

```bash
python3 -m pip install -r requirements.txt
```

Create Telegram API credentials at https://my.telegram.org/apps, then set these in `.env`:

```bash
TELEGRAM_API_ID=123456
TELEGRAM_API_HASH=replace-with-your-api-hash
TELEGRAM_SOURCE_CHAT=@source_alert_bot
TELEGRAM_TARGET_CHAT=-1001234567890
TELEGRAM_FORWARD_MODE=copy
TELEGRAM_SESSION=telegram_forwarder
```

Fields:

- `TELEGRAM_SOURCE_CHAT`: the private chat where the alert bot sends messages, usually the bot username like `@source_alert_bot`.
- `TELEGRAM_TARGET_CHAT`: the room, group, or channel that should receive the copied alerts.
- `TELEGRAM_FORWARD_MODE=copy`: sends a clean copy without a forwarded-from header.
- `TELEGRAM_FORWARD_MODE=forward`: preserves Telegram's forwarded message header.

If you do not know the source or target IDs, log in once and list visible dialogs:

```bash
python3 telegram_forwarder.py --list-dialogs
```

Run the live forwarder:

```bash
python3 telegram_forwarder.py
```

Expected startup logs look like this:

```text
[2026-05-25 17:40:00] Starting Telegram forwarder
[2026-05-25 17:40:00] Connecting to Telegram...
[2026-05-25 17:40:01] Connected to Telegram as: Your Name (123456789)
[2026-05-25 17:40:01] Source ready: Source Alert Bot (123456789)
[2026-05-25 17:40:01] Target ready: Alerts Room (-1001234567890)
[2026-05-25 17:40:01] Forwarder is ready. Waiting for new source messages...
```

When a message is copied or forwarded, it prints:

```text
[2026-05-25 17:41:03] Received source message #123; copying to target...
[2026-05-25 17:41:03] Mirrored source message #123 -> target message #456
```

On first run, it will ask for your phone number and Telegram login code, then create a local `.session` file. Keep that session file private.
