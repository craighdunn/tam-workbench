#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

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

UV_BIN="$(resolve_uv)"

# macOS Finder sometimes creates custom-folder-icon files named literally
# $'Icon\r'. In Python package directories these can be mistaken for schema
# or package data directories and crash MCP startup. Keep stdout pristine for
# MCP protocol; silently remove the files before launching.
find "$PROJECT_DIR" -name $'Icon\r' -delete 2>/dev/null || true

exec "$UV_BIN" --directory "$PROJECT_DIR" run tam-workbench-mcp
