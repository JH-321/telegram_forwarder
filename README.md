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
TELEGRAM_PRICE_SPIKES_TOPIC_ID=111
TELEGRAM_NEW_ENTRIES_TOPIC_ID=222
TELEGRAM_FORWARD_MODE=copy
TELEGRAM_SESSION=telegram_forwarder
```

Fields:

- `TELEGRAM_SOURCE_CHAT`: the private chat where the alert bot sends messages, usually the bot username like `@source_alert_bot`.
- `TELEGRAM_TARGET_CHAT`: the forum-enabled group that contains both topics.
- `TELEGRAM_PRICE_SPIKES_TOPIC_ID`: topic ID for alerts that start with `Price spikes`.
- `TELEGRAM_NEW_ENTRIES_TOPIC_ID`: topic ID for every alert that does not start with `Price spikes`.
- `TELEGRAM_PRICE_SPIKES_TARGET_CHAT` and `TELEGRAM_NEW_ENTRIES_TARGET_CHAT`: optional overrides if the routes should use different chats.
- `TELEGRAM_FORWARD_MODE=copy`: sends a clean copy without a forwarded-from header.
- `TELEGRAM_FORWARD_MODE=forward`: preserves Telegram's forwarded message header.

If you do not know the source or target IDs, log in once and list visible dialogs:

```bash
python3 telegram_forwarder.py --list-dialogs
```

If you do not know the topic IDs for the configured target group:

```bash
python3 telegram_forwarder.py --list-topics
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
[2026-05-25 17:40:01] Price spikes target ready: Alerts Group (-1001234567890) topic 111
[2026-05-25 17:40:01] New entries target ready: Alerts Group (-1001234567890) topic 222
[2026-05-25 17:40:01] Forwarder is ready. Waiting for new source messages...
```

When a message is copied or forwarded, it prints:

```text
[2026-05-25 17:41:03] Received source message #123; copying to Price spikes target...
[2026-05-25 17:41:03] Mirrored source message #123 via Price spikes route -> target message #456
```

The app does not write a log file. It only prints to the terminal. To run without status logs:

```bash
python3 telegram_forwarder.py --quiet
```

Or set:

```bash
TELEGRAM_QUIET=1
```

On first run, it will ask for your phone number and Telegram login code, then create a local `.session` file. Keep that session file private.

## Keep It Running After SSH Disconnect

Run the forwarder once in the foreground first, because the first run may need phone number, login code, and two-step verification password input:

```bash
python3 telegram_forwarder.py --list-dialogs
```

After the `.session` file exists, start it in the background with no terminal logs:

```bash
./scripts/start_background.sh
```

Check or stop it:

```bash
./scripts/status_background.sh
./scripts/stop_background.sh
```

The background script uses `nohup`, redirects output to `/dev/null`, and stores only a local `telegram_forwarder.pid` process ID file. It does not create a log file.

For restart-on-crash and restart-after-reboot on a Linux server, use the systemd user-service example:

```bash
mkdir -p ~/.config/systemd/user
cp systemd/telegram-forwarder.service.example ~/.config/systemd/user/telegram-forwarder.service
```

Edit the copied service file and replace `/absolute/path/to/telegram_forwarder` with this repo's absolute path on the server. Then run:

```bash
systemctl --user daemon-reload
systemctl --user enable --now telegram-forwarder.service
loginctl enable-linger "$USER"
```

This service also discards stdout and stderr with `StandardOutput=null` and `StandardError=null`.
