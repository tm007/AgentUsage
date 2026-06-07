#!/usr/bin/env bash
set -euo pipefail

APP_NAME="${APP_NAME:-AgentUsage}"
BUNDLE_ID="${BUNDLE_ID:-io.github.agentusage.AgentUsage}"
INSTALL_DIR="${INSTALL_DIR:-$HOME/Applications}"
APP_DIR="$INSTALL_DIR/${APP_NAME}.app"
CONTENTS_DIR="$APP_DIR/Contents"
MACOS_DIR="$CONTENTS_DIR/MacOS"
RESOURCES_DIR="$CONTENTS_DIR/Resources"
# SwiftPM target/product is still named AIUsage; the installed bundle is AgentUsage.
BINARY_PATH=".build/release/AIUsage"

swift build -c release

ICON_BACKUP=""
if [ -f "$APP_DIR/Contents/Resources/AppIcon.icns" ]; then
    ICON_BACKUP="$(mktemp /tmp/agentusage-icon.XXXXXX.icns)"
    cp "$APP_DIR/Contents/Resources/AppIcon.icns" "$ICON_BACKUP"
fi

rm -rf "$APP_DIR"
mkdir -p "$MACOS_DIR" "$RESOURCES_DIR"

cp "$BINARY_PATH" "$MACOS_DIR/$APP_NAME"
chmod +x "$MACOS_DIR/$APP_NAME"

cat > "$CONTENTS_DIR/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleIdentifier</key>
    <string>$BUNDLE_ID</string>
    <key>CFBundleName</key>
    <string>$APP_NAME</string>
    <key>CFBundleExecutable</key>
    <string>$APP_NAME</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleVersion</key>
    <string>1</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>LSMinimumSystemVersion</key>
    <string>14.0</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
</dict>
</plist>
PLIST

ICON_PATH="${ICON_PATH:-/tmp/AppIcon.icns}"
if [ -f "$ICON_PATH" ]; then
    cp "$ICON_PATH" "$RESOURCES_DIR/AppIcon.icns"
elif [ -n "$ICON_BACKUP" ] && [ -f "$ICON_BACKUP" ]; then
    cp "$ICON_BACKUP" "$RESOURCES_DIR/AppIcon.icns"
else
    echo "Warning: icon not found at $ICON_PATH and no existing AgentUsage icon to preserve; creating placeholder"
    : > "$RESOURCES_DIR/AppIcon.icns"
fi
rm -f "${ICON_BACKUP:-}"

/usr/bin/codesign --force --deep --sign - "$APP_DIR" >/dev/null 2>&1 || true

echo "Success: created $APP_DIR"
