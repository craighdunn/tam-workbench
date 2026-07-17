#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_CONFIG="$HOME/Library/Application Support/Claude/claude_desktop_config.json"
START_DASHBOARD=false
OPEN_DASHBOARD=false

usage() {
  cat <<'USAGE'
TAM Workbench installer

Usage:
  ./install.sh [--start-dashboard-at-login] [--open-dashboard]

Options:
  --start-dashboard-at-login   Install a macOS LaunchAgent so the dashboard starts at login.
  --open-dashboard             Start/open the dashboard after install.
  -h, --help                   Show this help.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --start-dashboard-at-login) START_DASHBOARD=true ;;
    --open-dashboard) OPEN_DASHBOARD=true ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 2 ;;
  esac
  shift
done

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

ensure_uv() {
  if UV_BIN="$(resolve_uv)"; then
    echo "Using uv: $UV_BIN"
    return 0
  fi
  echo "uv was not found. Installing uv using Astral's official installer..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
  UV_BIN="$(resolve_uv)" || {
    echo "uv installation did not finish successfully. Please install uv, then rerun ./install.sh" >&2
    exit 1
  }
  echo "Installed uv: $UV_BIN"
}

merge_claude_config() {
  mkdir -p "$(dirname "$CLAUDE_CONFIG")"
  PROJECT_DIR="$PROJECT_DIR" CLAUDE_CONFIG="$CLAUDE_CONFIG" python3 - <<'PY'
from __future__ import annotations
import json
import os
from pathlib import Path

config_path = Path(os.environ["CLAUDE_CONFIG"])
project_dir = Path(os.environ["PROJECT_DIR"])
launcher = project_dir / "scripts" / "launch-mcp.sh"

if config_path.exists():
    try:
        data = json.loads(config_path.read_text())
    except json.JSONDecodeError as exc:
        backup = config_path.with_suffix(config_path.suffix + ".invalid-json.bak")
        backup.write_text(config_path.read_text())
        raise SystemExit(f"Claude Desktop config is not valid JSON. Backed it up to {backup}; please fix it and rerun install.sh. Error: {exc}")
else:
    data = {}

if not isinstance(data, dict):
    data = {}
servers = data.setdefault("mcpServers", {})
servers["tam-workbench"] = {"command": str(launcher), "args": []}
config_path.write_text(json.dumps(data, indent=2) + "\n")
print(config_path)
PY
}

install_dashboard_launch_agent() {
  "$PROJECT_DIR/scripts/install-dashboard-autostart.sh"
}

start_dashboard_once() {
  echo "Starting dashboard in the background..."
  pkill -f "tam-workbench-dashboard" >/dev/null 2>&1 || true
  nohup "$UV_BIN" --directory "$PROJECT_DIR" run tam-workbench-dashboard > "$HOME/.tam-workbench/logs/dashboard.manual.log" 2>&1 &
  sleep 2
  if command -v open >/dev/null 2>&1; then
    open "http://127.0.0.1:8501" || true
  fi
}

main() {
  echo "Installing TAM Workbench from: $PROJECT_DIR"
  ensure_uv
  chmod +x "$PROJECT_DIR/scripts/launch-mcp.sh" "$PROJECT_DIR/scripts/install-dashboard-autostart.sh" "$PROJECT_DIR/scripts/uninstall-dashboard-autostart.sh" 2>/dev/null || true
  find "$PROJECT_DIR" -name $'Icon\r' -delete 2>/dev/null || true

  echo "Installing Python dependencies..."
  "$UV_BIN" --directory "$PROJECT_DIR" sync --dev

  echo "Initializing local database and templates..."
  "$UV_BIN" --directory "$PROJECT_DIR" run tam-workbench init

  echo "Registering TAM Workbench with Claude Desktop..."
  merge_claude_config

  if [[ "$START_DASHBOARD" == true ]]; then
    install_dashboard_launch_agent
  fi

  if [[ "$OPEN_DASHBOARD" == true ]]; then
    start_dashboard_once
  fi

  cat <<EOF

TAM Workbench installed successfully.

Next steps:
1. Fully quit Claude Desktop, then reopen it.
2. In Claude, ask: "What TAM Workbench tools do you have?"
3. Dashboard URL: http://127.0.0.1:8501

Local data lives in:
  $HOME/.tam-workbench/

EOF
}

main
