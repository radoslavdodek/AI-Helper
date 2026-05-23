#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"

if [[ ! -f "$VENV_DIR/bin/activate" ]]; then
  echo "Virtual environment not found at $VENV_DIR/bin/activate" >&2
  exit 1
fi

# shellcheck disable=SC1090
source "$VENV_DIR/bin/activate"

exec python "$SCRIPT_DIR/ai_helper.py" "$@"
