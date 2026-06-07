#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_SUPPORT="${APP_SUPPORT:-$HOME/Library/Application Support/ai-usage-dashboard}"
mkdir -p "$APP_SUPPORT"
cp "$ROOT/generate_usage_dashboard.py" "$APP_SUPPORT/generate_usage_dashboard.py"
cd "$APP_SUPPORT"
python3 ./generate_usage_dashboard.py
