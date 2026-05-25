import asyncio
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import telegram_forwarder


class TelegramForwarderTests(unittest.TestCase):
    def test_parse_chat_keeps_usernames_and_converts_ids(self) -> None:
        self.assertEqual(telegram_forwarder.parse_chat("@alert_bot"), "@alert_bot")
        self.assertEqual(telegram_forwarder.parse_chat("-100123"), -100123)
        self.assertIsNone(telegram_forwarder.parse_chat(""))

    def test_sent_message_label_handles_single_and_multiple_messages(self) -> None:
        message_1 = type("Message", (), {"id": 10})()
        message_2 = type("Message", (), {"id": 11})()

        self.assertEqual(
            telegram_forwarder.sent_message_label(message_1),
            " -> target message #10",
        )
        self.assertEqual(
            telegram_forwarder.sent_message_label([message_1, message_2]),
            " -> target messages #10, #11",
        )
        self.assertEqual(telegram_forwarder.sent_message_label(None), "")

    def test_config_reads_env_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            env_file = Path(tmp_dir) / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        "TELEGRAM_API_ID=12345",
                        "TELEGRAM_API_HASH=hash",
                        "TELEGRAM_SOURCE_CHAT=@source_bot",
                        "TELEGRAM_TARGET_CHAT=-100777",
                        "TELEGRAM_FORWARD_MODE=forward",
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                config = telegram_forwarder.config_from_args(["--env-file", str(env_file)])

        self.assertEqual(config.api_id, 12345)
        self.assertEqual(config.api_hash, "hash")
        self.assertEqual(config.source_chat, "@source_bot")
        self.assertEqual(config.target_chat, -100777)
        self.assertEqual(config.mode, "forward")

    def test_mirror_message_copies_by_default(self) -> None:
        async def run() -> None:
            client = AsyncMock()
            event = type("Event", (), {"message": object(), "raw_text": "hello"})()
            target = object()

            await telegram_forwarder.mirror_message(client, event, target, mode="copy")

            client.send_message.assert_awaited_once_with(target, event.message)
            client.forward_messages.assert_not_called()

        asyncio.run(run())

    def test_mirror_message_can_forward(self) -> None:
        async def run() -> None:
            client = AsyncMock()
            event = type("Event", (), {"message": object(), "raw_text": "hello"})()
            target = object()

            await telegram_forwarder.mirror_message(client, event, target, mode="forward")

            client.forward_messages.assert_awaited_once_with(target, event.message)
            client.send_message.assert_not_called()

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
