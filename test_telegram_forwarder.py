import asyncio
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import telegram_forwarder


class TelegramForwarderTests(unittest.TestCase):
    SELL_RISE_ALERT = """Price spikes
📈 [Sell Rise 1h] SK hynix (SKHYNIX)  +867.30%

gate.P: +867.30%
Buy  | $165.86 -> $1,604.65
Sell | $1,600.02 -> $1,604.40
Time: 2026-07-03 14:01:31 UTC"""

    BUY_DROP_ALERT = """Price spikes
📉 [Buy Drop 30s] EWTB  -45.80%

uniswap | eth: -45.80%
Buy  | $0.3757 -> $0.1751
Sell | $0.3231 -> $0.1403
CA: 0x178c820f862b14f316509ec36b13123da19a6054
Pool: 0xdc7d8cc3a22fe0ec69770e02931f43451b7b975e
CMC | DS | GMGN | OKX

Time: 2026-07-03 14:36:58 UTC"""

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
                        "TELEGRAM_TARGET_TOPIC_ID=10",
                        "TELEGRAM_PRICE_SPIKES_TARGET_CHAT=-100111",
                        "TELEGRAM_PRICE_SPIKES_TOPIC_ID=111",
                        "TELEGRAM_NEW_ENTRIES_TARGET_CHAT=-100222",
                        "TELEGRAM_NEW_ENTRIES_TOPIC_ID=222",
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
        self.assertEqual(config.target_topic_id, 10)
        self.assertEqual(config.price_spikes_target_chat, -100111)
        self.assertEqual(config.price_spikes_topic_id, 111)
        self.assertEqual(config.new_entries_target_chat, -100222)
        self.assertEqual(config.new_entries_topic_id, 222)
        self.assertEqual(config.mode, "forward")
        self.assertTrue(config.quiet)

    def test_target_specs_can_use_one_chat_with_two_topics(self) -> None:
        config = telegram_forwarder.ForwarderConfig(
            api_id=1,
            api_hash="hash",
            source_chat="@source",
            target_chat=-100999,
            target_topic_id=None,
            price_spikes_target_chat=None,
            price_spikes_topic_id=111,
            new_entries_target_chat=None,
            new_entries_topic_id=222,
            session="session",
            mode="copy",
            dry_run=False,
            list_dialogs=False,
            list_topics=False,
            quiet=True,
        )

        targets = telegram_forwarder.target_specs_from_config(config)

        self.assertNotIn(telegram_forwarder.DEFAULT_ROUTE, targets)
        self.assertEqual(
            targets[telegram_forwarder.PRICE_SPIKES_ROUTE],
            telegram_forwarder.TargetSpec(-100999, 111),
        )
        self.assertEqual(
            targets[telegram_forwarder.NEW_ENTRIES_ROUTE],
            telegram_forwarder.TargetSpec(-100999, 222),
        )

    def test_target_specs_add_default_only_when_fallback_topic_is_set(self) -> None:
        config = telegram_forwarder.ForwarderConfig(
            api_id=1,
            api_hash="hash",
            source_chat="@source",
            target_chat=-100999,
            target_topic_id=333,
            price_spikes_target_chat=None,
            price_spikes_topic_id=111,
            new_entries_target_chat=None,
            new_entries_topic_id=222,
            session="session",
            mode="copy",
            dry_run=False,
            list_dialogs=False,
            list_topics=False,
            quiet=True,
        )

        targets = telegram_forwarder.target_specs_from_config(config)

        self.assertEqual(
            targets[telegram_forwarder.DEFAULT_ROUTE],
            telegram_forwarder.TargetSpec(-100999, 333),
        )

    def test_target_specs_keep_legacy_single_target_mode(self) -> None:
        config = telegram_forwarder.ForwarderConfig(
            api_id=1,
            api_hash="hash",
            source_chat="@source",
            target_chat=-100999,
            target_topic_id=None,
            price_spikes_target_chat=None,
            price_spikes_topic_id=None,
            new_entries_target_chat=None,
            new_entries_topic_id=None,
            session="session",
            mode="copy",
            dry_run=False,
            list_dialogs=False,
            list_topics=False,
            quiet=True,
        )

        targets = telegram_forwarder.target_specs_from_config(config)

        self.assertEqual(
            targets[telegram_forwarder.DEFAULT_ROUTE],
            telegram_forwarder.TargetSpec(-100999, None),
        )

    def test_route_label_for_text_matches_requested_prefixes(self) -> None:
        self.assertEqual(
            telegram_forwarder.route_label_for_text("Price spikes\n📉 [Buy Drop on BTC"),
            telegram_forwarder.PRICE_SPIKES_ROUTE,
        )
        self.assertEqual(
            telegram_forwarder.route_label_for_text("Price spikes on BTC"),
            telegram_forwarder.DEFAULT_ROUTE,
        )
        self.assertEqual(
            telegram_forwarder.route_label_for_text("  New entries found"),
            telegram_forwarder.NEW_ENTRIES_ROUTE,
        )
        self.assertEqual(
            telegram_forwarder.route_label_for_text("Other alert"),
            telegram_forwarder.DEFAULT_ROUTE,
        )

    def test_select_target_for_text_uses_only_explicit_route_prefixes(self) -> None:
        targets = {
            telegram_forwarder.DEFAULT_ROUTE: "default-room",
            telegram_forwarder.PRICE_SPIKES_ROUTE: "price-room",
            telegram_forwarder.NEW_ENTRIES_ROUTE: "entries-room",
        }

        self.assertEqual(
            telegram_forwarder.select_target_for_text("Price spikes\n📉 [Buy Drop now", targets),
            (telegram_forwarder.PRICE_SPIKES_ROUTE, "price-room"),
        )
        self.assertEqual(
            telegram_forwarder.select_target_for_text("Price spikes now", targets),
            (telegram_forwarder.DEFAULT_ROUTE, "default-room"),
        )
        self.assertEqual(
            telegram_forwarder.select_target_for_text("New entries now", targets),
            (telegram_forwarder.NEW_ENTRIES_ROUTE, "entries-room"),
        )
        self.assertEqual(
            telegram_forwarder.select_target_for_text("Something else", targets),
            (telegram_forwarder.DEFAULT_ROUTE, "default-room"),
        )

    def test_real_price_spike_samples_route_to_expected_topics(self) -> None:
        targets = {
            telegram_forwarder.PRICE_SPIKES_ROUTE: "price-room",
            telegram_forwarder.NEW_ENTRIES_ROUTE: "entries-room",
        }

        self.assertEqual(
            telegram_forwarder.select_target_for_text(self.SELL_RISE_ALERT, targets),
            (None, None),
        )
        self.assertEqual(
            telegram_forwarder.select_target_for_text(self.BUY_DROP_ALERT, targets),
            (telegram_forwarder.PRICE_SPIKES_ROUTE, "price-room"),
        )

    def test_select_target_for_text_skips_unmatched_without_default(self) -> None:
        targets = {
            telegram_forwarder.PRICE_SPIKES_ROUTE: "price-room",
            telegram_forwarder.NEW_ENTRIES_ROUTE: "entries-room",
        }

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
            target = telegram_forwarder.ResolvedTarget(object())

            await telegram_forwarder.mirror_message(client, event, target, mode="copy")

            client.send_message.assert_awaited_once_with(target.chat, event.message, reply_to=None)
            client.forward_messages.assert_not_called()

        asyncio.run(run())

    def test_mirror_message_copies_to_topic(self) -> None:
        async def run() -> None:
            client = AsyncMock()
            event = type("Event", (), {"message": object(), "raw_text": "hello"})()
            target = telegram_forwarder.ResolvedTarget(object(), 123)

            await telegram_forwarder.mirror_message(client, event, target, mode="copy")

            client.send_message.assert_awaited_once_with(target.chat, event.message, reply_to=123)

        asyncio.run(run())

    def test_mirror_message_can_forward(self) -> None:
        async def run() -> None:
            client = AsyncMock()
            event = type("Event", (), {"message": object(), "raw_text": "hello"})()
            target = telegram_forwarder.ResolvedTarget(object())

            await telegram_forwarder.mirror_message(client, event, target, mode="forward")

            client.forward_messages.assert_awaited_once_with(target.chat, event.message)
            client.send_message.assert_not_called()

        asyncio.run(run())

    def test_mirror_message_forwards_to_topic_with_raw_request_helper(self) -> None:
        async def run() -> None:
            client = AsyncMock()
            event = type("Event", (), {"message": object(), "raw_text": "hello"})()
            target = telegram_forwarder.ResolvedTarget(object(), 123)
            source = object()

            with patch(
                "telegram_forwarder.forward_message_to_topic",
                new_callable=AsyncMock,
            ) as forward_message_to_topic:
                await telegram_forwarder.mirror_message(
                    client,
                    event,
                    target,
                    mode="forward",
                    source=source,
                )

            forward_message_to_topic.assert_awaited_once_with(
                client,
                event,
                source,
                target.chat,
                123,
            )
            client.forward_messages.assert_not_called()

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
