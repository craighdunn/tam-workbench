#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LABEL="com.tam-workbench.dashboard"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG_DIR="$HOME/.tam-workbench/logs"
mkdir -p "$(dirname "$PLIST")" "$LOG_DIR"

resolve_uv() {
  if command -v uv >/dev/null 2>&1; then
    command -v uv
    return 0
  fi
  for candidate in "$HOME/.local/bin/uv" "/opt/homebrew/bin/uv" "/usr/local/bin/uv"; do
    if [[ -x "$candidate" ]]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

UV_BIN="$(resolve_uv)" || {
  echo "uv was not found. Run ./install.sh first, then rerun this script." >&2
  exit 1
}

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$UV_BIN</string>
    <string>--directory</string>
    <string>$PROJECT_DIR</string>
    <string>run</string>
    <string>tam-workbench-dashboard</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <false/>
  <key>StandardOutPath</key>
  <string>$LOG_DIR/dashboard.launchd.log</string>
  <key>StandardErrorPath</key>
  <string>$LOG_DIR/dashboard.launchd.err</string>
  <key>WorkingDirectory</key>
  <string>$PROJECT_DIR</string>
</dict>
</plist>
EOF

launchctl bootout "gui/$(id -u)" "$PLIST" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
launchctl enable "gui/$(id -u)/$LABEL" >/dev/null 2>&1 || true
launchctl kickstart -k "gui/$(id -u)/$LABEL" >/dev/null 2>&1 || true

echo "Installed dashboard LaunchAgent: $PLIST"
echo "Dashboard should start at login and is available at: http://127.0.0.1:8501"
