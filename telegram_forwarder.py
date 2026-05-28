#!/usr/bin/env python3
"""Mirror incoming Telegram private-chat bot alerts into another chat."""

from __future__ import annotations

import argparse
import asyncio
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_SESSION = "telegram_forwarder"
QUIET = False
PRICE_SPIKES_ROUTE = "Price spikes"
NEW_ENTRIES_ROUTE = "New entries"
DEFAULT_ROUTE = "default"
ROUTE_PREFIXES = (PRICE_SPIKES_ROUTE, NEW_ENTRIES_ROUTE)


class TelegramError(RuntimeError):
    """Raised when the forwarder cannot be configured or started."""


def log_event(message: str, *, force: bool = False) -> None:
    if QUIET and not force:
        return
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] {message}", flush=True)


@dataclass(frozen=True)
class ForwarderConfig:
    api_id: int
    api_hash: str
    source_chat: str | int | None
    target_chat: str | int | None
    price_spikes_target_chat: str | int | None
    new_entries_target_chat: str | int | None
    session: str
    mode: str
    dry_run: bool
    list_dialogs: bool
    quiet: bool


def load_env_file(path: Path) -> None:
    """Load simple KEY=VALUE lines into the process environment."""
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def parse_chat(value: str | None) -> str | int | None:
    if value is None:
        return None

    stripped = value.strip()
    if not stripped:
        return None

    try:
        return int(stripped)
    except ValueError:
        return stripped


def require_api_id(value: str | None) -> int:
    if not value:
        raise TelegramError("Set TELEGRAM_API_ID or pass --api-id.")
    try:
        return int(value)
    except ValueError as exc:
        raise TelegramError("TELEGRAM_API_ID must be a number.") from exc


def require_mode(value: str) -> str:
    if value not in {"copy", "forward"}:
        raise TelegramError("TELEGRAM_FORWARD_MODE must be copy or forward.")
    return value


def env_flag(name: str) -> bool:
    value = os.getenv(name, "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def entity_label(entity: Any) -> str:
    title = getattr(entity, "title", None)
    username = getattr(entity, "username", None)
    first_name = getattr(entity, "first_name", None)
    last_name = getattr(entity, "last_name", None)
    entity_id = getattr(entity, "id", None)

    name = title or username or " ".join(part for part in (first_name, last_name) if part)
    if name and entity_id is not None:
        return f"{name} ({entity_id})"
    if name:
        return name
    return str(entity_id or entity)


def sent_message_label(sent: Any) -> str:
    if sent is None:
        return ""

    messages = sent if isinstance(sent, (list, tuple)) else [sent]
    message_ids = [str(message.id) for message in messages if getattr(message, "id", None)]
    if not message_ids:
        return ""
    if len(message_ids) == 1:
        return f" -> target message #{message_ids[0]}"
    return f" -> target messages #{', #'.join(message_ids)}"


def route_label_for_text(text: str | None) -> str:
    stripped = (text or "").lstrip()
    for prefix in ROUTE_PREFIXES:
        if stripped.startswith(prefix):
            return prefix
    return DEFAULT_ROUTE


def target_specs_from_config(config: ForwarderConfig) -> dict[str, str | int]:
    targets = {
        DEFAULT_ROUTE: config.target_chat,
        PRICE_SPIKES_ROUTE: config.price_spikes_target_chat,
        NEW_ENTRIES_ROUTE: config.new_entries_target_chat,
    }
    return {label: target for label, target in targets.items() if target is not None}


def select_target_for_text(
    text: str | None,
    targets: dict[str, Any],
) -> tuple[str | None, Any | None]:
    route_label = route_label_for_text(text)
    if route_label in targets:
        return route_label, targets[route_label]
    if DEFAULT_ROUTE in targets:
        return DEFAULT_ROUTE, targets[DEFAULT_ROUTE]
    return None, None


async def mirror_message(
    client: Any,
    event: Any,
    target: Any,
    *,
    mode: str,
    dry_run: bool = False,
) -> Any:
    if dry_run:
        preview = event.raw_text or "<non-text message>"
        log_event(f"Dry run: would {mode} message: {preview[:120]}")
        return None

    if mode == "forward":
        return await client.forward_messages(target, event.message)

    return await client.send_message(target, event.message)


async def print_dialogs(client: Any) -> None:
    async for dialog in client.iter_dialogs():
        entity = dialog.entity
        entity_id = getattr(dialog, "id", getattr(entity, "id", ""))
        name = dialog.name or entity_label(entity)
        print(f"{entity_id}\t{dialog.is_user=}\t{dialog.is_group=}\t{dialog.is_channel=}\t{name}")


async def run_forwarder(config: ForwarderConfig) -> None:
    global QUIET
    QUIET = config.quiet

    try:
        from telethon import TelegramClient, events
    except ImportError as exc:
        raise TelegramError(
            "Telethon is required. Install it with: python3 -m pip install -r requirements.txt"
        ) from exc

    log_event("Starting Telegram forwarder")
    log_event(f"Using session name: {config.session}")
    log_event("Connecting to Telegram...")

    client = TelegramClient(config.session, config.api_id, config.api_hash)

    async with client:
        me = await client.get_me()
        log_event(f"Connected to Telegram as: {entity_label(me)}")

        if config.list_dialogs:
            log_event("Listing visible dialogs...")
            await print_dialogs(client)
            log_event("Finished listing dialogs")
            return

        if config.source_chat is None:
            raise TelegramError("Set TELEGRAM_SOURCE_CHAT or pass --source-chat.")
        target_specs = target_specs_from_config(config)
        if not target_specs:
            raise TelegramError(
                "Set TELEGRAM_PRICE_SPIKES_TARGET_CHAT, "
                "TELEGRAM_NEW_ENTRIES_TARGET_CHAT, or TELEGRAM_TARGET_CHAT."
            )

        log_event(f"Resolving source chat: {config.source_chat}")
        source = await client.get_entity(config.source_chat)
        log_event(f"Source ready: {entity_label(source)}")

        targets: dict[str, Any] = {}
        for label, target_spec in target_specs.items():
            log_event(f"Resolving {label} target chat: {target_spec}")
            targets[label] = await client.get_entity(target_spec)
            log_event(f"{label} target ready: {entity_label(targets[label])}")

        action = "forwarding" if config.mode == "forward" else "copying"
        dry_run_suffix = " (dry run; no messages will be sent)" if config.dry_run else ""
        log_event(f"Mode: {config.mode}{dry_run_suffix}")
        log_event("Forwarder is ready. Waiting for new source messages...")

        @client.on(events.NewMessage(chats=source, incoming=True))
        async def handler(event: Any) -> None:
            source_message_id = getattr(event.message, "id", "unknown")
            route_label, target = select_target_for_text(event.raw_text, targets)
            if target is None:
                log_event(f"Skipped source message #{source_message_id}; no target route matched")
                return

            log_event(
                f"Received source message #{source_message_id}; "
                f"{action} to {route_label} target..."
            )
            try:
                sent = await mirror_message(
                    client,
                    event,
                    target,
                    mode=config.mode,
                    dry_run=config.dry_run,
                )
            except Exception as exc:  # Telethon exposes many runtime RPC errors.
                log_event(f"Failed to mirror source message #{source_message_id}: {exc}")
                return

            log_event(
                f"Mirrored source message #{source_message_id} "
                f"via {route_label} route{sent_message_label(sent)}"
            )

        await client.run_until_disconnected()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Copy or forward incoming private-chat Telegram bot alerts."
    )
    parser.add_argument("--env-file", default=".env", help="env file to load first")
    parser.add_argument("--api-id", help="Telegram API ID from my.telegram.org")
    parser.add_argument("--api-hash", help="Telegram API hash from my.telegram.org")
    parser.add_argument(
        "--source-chat",
        help="private bot chat to watch, for example @source_bot or a numeric ID",
    )
    parser.add_argument(
        "--target-chat",
        help="fallback destination for messages that do not match a routed prefix",
    )
    parser.add_argument(
        "--price-spikes-target-chat",
        help="destination for messages starting with 'Price spikes'",
    )
    parser.add_argument(
        "--new-entries-target-chat",
        help="destination for messages starting with 'New entries'",
    )
    parser.add_argument("--session", help="Telethon session file name")
    parser.add_argument(
        "--mode",
        choices=("copy", "forward"),
        default=None,
        help="copy hides the forward header; forward preserves it",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print matching messages without sending them",
    )
    parser.add_argument(
        "--list-dialogs",
        action="store_true",
        help="print visible chats to help find source and target IDs",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="suppress status logs; errors and --list-dialogs output still print",
    )
    return parser


def config_from_args(argv: list[str] | None = None) -> ForwarderConfig:
    parser = build_parser()
    args = parser.parse_args(argv)

    load_env_file(Path(args.env_file))

    api_id = require_api_id(args.api_id or os.getenv("TELEGRAM_API_ID"))
    api_hash = args.api_hash or os.getenv("TELEGRAM_API_HASH")
    if not api_hash:
        raise TelegramError("Set TELEGRAM_API_HASH or pass --api-hash.")

    return ForwarderConfig(
        api_id=api_id,
        api_hash=api_hash,
        source_chat=parse_chat(args.source_chat or os.getenv("TELEGRAM_SOURCE_CHAT")),
        target_chat=parse_chat(args.target_chat or os.getenv("TELEGRAM_TARGET_CHAT")),
        price_spikes_target_chat=parse_chat(
            args.price_spikes_target_chat or os.getenv("TELEGRAM_PRICE_SPIKES_TARGET_CHAT")
        ),
        new_entries_target_chat=parse_chat(
            args.new_entries_target_chat or os.getenv("TELEGRAM_NEW_ENTRIES_TARGET_CHAT")
        ),
        session=args.session or os.getenv("TELEGRAM_SESSION") or DEFAULT_SESSION,
        mode=require_mode(args.mode or os.getenv("TELEGRAM_FORWARD_MODE", "copy")),
        dry_run=args.dry_run,
        list_dialogs=args.list_dialogs,
        quiet=args.quiet or env_flag("TELEGRAM_QUIET"),
    )


def main(argv: list[str] | None = None) -> int:
    config = config_from_args(argv)
    asyncio.run(run_forwarder(config))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("Stopped.")
        raise SystemExit(130)
    except TelegramError as exc:
        print(f"error: {exc}")
        raise SystemExit(1)
