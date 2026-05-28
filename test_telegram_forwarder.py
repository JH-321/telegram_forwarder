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
                        "TELEGRAM_PRICE_SPIKES_TARGET_CHAT=-100111",
                        "TELEGRAM_NEW_ENTRIES_TARGET_CHAT=-100222",
                        "TELEGRAM_FORWARD_MODE=forward",
                        "TELEGRAM_QUIET=1",
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
        self.assertEqual(config.price_spikes_target_chat, -100111)
        self.assertEqual(config.new_entries_target_chat, -100222)
        self.assertEqual(config.mode, "forward")
        self.assertTrue(config.quiet)

    def test_route_label_for_text_matches_requested_prefixes(self) -> None:
        self.assertEqual(
            telegram_forwarder.route_label_for_text("Price spikes on BTC"),
            telegram_forwarder.PRICE_SPIKES_ROUTE,
        )
        self.assertEqual(
            telegram_forwarder.route_label_for_text("  New entries found"),
            telegram_forwarder.NEW_ENTRIES_ROUTE,
        )
        self.assertEqual(
            telegram_forwarder.route_label_for_text("Other alert"),
            telegram_forwarder.NEW_ENTRIES_ROUTE,
        )

    def test_select_target_for_text_sends_non_price_to_new_entries(self) -> None:
        targets = {
            telegram_forwarder.DEFAULT_ROUTE: "default-room",
            telegram_forwarder.PRICE_SPIKES_ROUTE: "price-room",
            telegram_forwarder.NEW_ENTRIES_ROUTE: "entries-room",
        }

        self.assertEqual(
            telegram_forwarder.select_target_for_text("Price spikes now", targets),
            (telegram_forwarder.PRICE_SPIKES_ROUTE, "price-room"),
        )
        self.assertEqual(
            telegram_forwarder.select_target_for_text("New entries now", targets),
            (telegram_forwarder.NEW_ENTRIES_ROUTE, "entries-room"),
        )
        self.assertEqual(
            telegram_forwarder.select_target_for_text("Something else", targets),
            (telegram_forwarder.NEW_ENTRIES_ROUTE, "entries-room"),
        )

    def test_select_target_for_text_skips_unmatched_without_default(self) -> None:
        targets = {telegram_forwarder.PRICE_SPIKES_ROUTE: "price-room"}

        self.assertEqual(
            telegram_forwarder.select_target_for_text("Something else", targets),
            (None, None),
        )

    def test_select_target_for_text_keeps_legacy_default_fallback(self) -> None:
        targets = {telegram_forwarder.DEFAULT_ROUTE: "default-room"}

        self.assertEqual(
            telegram_forwarder.select_target_for_text("Price spikes now", targets),
            (telegram_forwarder.DEFAULT_ROUTE, "default-room"),
        )
        self.assertEqual(
            telegram_forwarder.select_target_for_text("Something else", targets),
            (telegram_forwarder.DEFAULT_ROUTE, "default-room"),
        )

    def test_log_event_respects_quiet_mode(self) -> None:
        with patch("telegram_forwarder.print") as mocked_print:
            telegram_forwarder.QUIET = True
            telegram_forwarder.log_event("hidden")
            telegram_forwarder.log_event("visible", force=True)
            telegram_forwarder.QUIET = False

        self.assertEqual(mocked_print.call_count, 1)
        self.assertIn("visible", mocked_print.call_args.args[0])

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
