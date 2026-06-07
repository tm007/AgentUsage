#!/usr/bin/env bash
set -euo pipefail
APP_SUPPORT="${APP_SUPPORT:-$HOME/Library/Application Support/ai-usage-dashboard}"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8765}"
cd "$APP_SUPPORT"
exec python3 -m http.server "$PORT" --bind "$HOST"
