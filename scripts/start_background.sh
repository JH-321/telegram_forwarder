#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
PID_FILE=${PID_FILE:-"$PROJECT_DIR/telegram_forwarder.pid"}

if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
        echo "telegram_forwarder.py is already running with PID $OLD_PID"
        exit 0
    fi
fi

if [ -n "${PYTHON_BIN:-}" ]; then
    PYTHON=$PYTHON_BIN
elif [ -x "$PROJECT_DIR/venv/bin/python" ]; then
    PYTHON="$PROJECT_DIR/venv/bin/python"
else
    PYTHON=python3
fi

if [ "$#" -eq 0 ]; then
    set -- --quiet
fi

cd "$PROJECT_DIR"
nohup "$PYTHON" telegram_forwarder.py "$@" >/dev/null 2>&1 &
PID=$!
printf '%s\n' "$PID" > "$PID_FILE"
echo "Started telegram_forwarder.py with PID $PID"
