#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
PID_FILE=${PID_FILE:-"$PROJECT_DIR/telegram_forwarder.pid"}

if [ ! -f "$PID_FILE" ]; then
    echo "telegram_forwarder.py is not running"
    exit 1
fi

PID=$(cat "$PID_FILE")
if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
    echo "telegram_forwarder.py is running with PID $PID"
    exit 0
fi

echo "telegram_forwarder.py is not running"
exit 1
