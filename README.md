# AgentUsage

Portable, local-first macOS dashboard for AI usage across Claude, Codex, Cursor, OpenCode, Hermes, and Pi.

This repository contains the whole source system:

- native SwiftUI macOS app (`Sources/AIUsage`)
- Python collector / dashboard renderer (`generate_usage_dashboard.py`)
- helper scripts for building, updating, and serving
- parser regression tests

No generated usage data, local caches, build artifacts, credentials, or machine-specific paths are committed.

## What it reads

The collector scans the standard local data locations for supported tools in the current user's home directory. It normalizes sessions into:

- `usage-summary.json`
- `usage-sessions.csv`
- `usage-dashboard.html`

The Swift app reads from:

```text
~/Library/Application Support/ai-usage-dashboard/usage-summary.json
```

and runs:

```text
~/Library/Application Support/ai-usage-dashboard/generate_usage_dashboard.py
```

on refresh.

## Install / update the scraper

```bash
./scripts/update-dashboard.sh
```

That copies `generate_usage_dashboard.py` into Application Support and generates the current reports there.

## Build the macOS app

Development build:

```bash
swift build
swift run AIUsage
```

Release app bundle:

```bash
./scripts/build-app.sh
```

Defaults:

- app name: `AgentUsage`
- install path: `~/Applications/AgentUsage.app`
- bundle id: `io.github.agentusage.AgentUsage`

Override if needed:

```bash
BUNDLE_ID=com.example.AgentUsage INSTALL_DIR=/Applications ./scripts/build-app.sh
```

The app is a normal Dock / Cmd-Tab macOS app (`WindowGroup`), not a menu-bar-only `LSUIElement` app.

## Optional LaunchAgent

A portable template is included at:

```text
scripts/io.github.agentusage.plist.template
```

To install it, replace `__HOME__` with your home directory and copy it to `~/Library/LaunchAgents/io.github.agentusage.plist`.

## Test

```bash
python3 -m pytest tests
swift build
```

## Privacy

Reports include project paths, aggregate usage, models, dates, costs, and read/write activity. Raw prompts and message content are not written to generated report files. Keep generated JSON/CSV/HTML files local; `.gitignore` excludes them.
