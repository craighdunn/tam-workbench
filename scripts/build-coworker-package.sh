#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_ROOT="/tmp/tam-workbench-package-build"
PACKAGE_DIR="$BUILD_ROOT/tam-workbench"
DIST_DIR="$ROOT/dist"
ZIP_PATH="$DIST_DIR/tam-workbench-v0.3.7-fresh-install.zip"

rm -rf "$BUILD_ROOT"
mkdir -p "$PACKAGE_DIR" "$DIST_DIR"

copy_file() {
  local src="$1"
  local dst="$PACKAGE_DIR/$src"
  mkdir -p "$(dirname "$dst")"
  cp "$ROOT/$src" "$dst"
}

copy_dir() {
  local src="$1"
  mkdir -p "$PACKAGE_DIR/$src"
  rsync -a \
    --exclude '__pycache__/' \
    --exclude '.DS_Store' \
    --exclude $'Icon\r' \
    "$ROOT/$src/" "$PACKAGE_DIR/$src/"
}

copy_file README.md
copy_file INSTALL.md
copy_file SECURITY.md
copy_file CHANGELOG.md
copy_file pyproject.toml
copy_file uv.lock
copy_file install.sh
copy_dir scripts
copy_dir src
copy_dir tests

chmod +x "$PACKAGE_DIR/install.sh" "$PACKAGE_DIR/scripts/launch-mcp.sh" "$PACKAGE_DIR/scripts/install-dashboard-autostart.sh" "$PACKAGE_DIR/scripts/uninstall-dashboard-autostart.sh"

# Remove any accidental generated or local-only files.
find "$PACKAGE_DIR" \
  \( -name '__pycache__' -o -name '.pytest_cache' -o -name '.venv' -o -name '.DS_Store' -o -name $'Icon\r' \) -prune -exec rm -rf {} +
find "$PACKAGE_DIR" \
  \( -name '*.pyc' -o -name '*.pyo' -o -name '*.db' -o -name '*.sqlite' -o -name '*.sqlite3' \) -delete

rm -f "$ZIP_PATH"
(
  cd "$BUILD_ROOT"
  zip -qr "$ZIP_PATH" tam-workbench
)

echo "$ZIP_PATH"
