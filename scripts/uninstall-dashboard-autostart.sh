#!/usr/bin/env bash
set -euo pipefail

LABEL="com.tam-workbench.dashboard"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

launchctl bootout "gui/$(id -u)" "$PLIST" >/dev/null 2>&1 || true
rm -f "$PLIST"

echo "Removed dashboard LaunchAgent. The dashboard will no longer auto-start at login."
