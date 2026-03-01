#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export DISPLAY="${DISPLAY:-:0}"
export DBUS_SESSION_BUS_ADDRESS="${DBUS_SESSION_BUS_ADDRESS:-unix:path=/run/user/$(id -u)/bus}"

exec "$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/ai_helper.py" Rewrite >> "$SCRIPT_DIR/ai_helper.log" 2>&1
