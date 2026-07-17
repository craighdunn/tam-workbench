# Client Workbench Pilot Zip Packaging Plan

> **For Hermes:** Use this as the implementation and release checklist for a coworker-shareable pilot package.

**Goal:** Create a sanitized, coworker-installable pilot zip named `client-workbench-pilot.zip` that installs a local Claude Desktop MCP server called **Client Workbench**. Current pilot update: **v0.2.0 Contacts** adds structured per-client stakeholder/contact records.

**Architecture:** The pilot package remains a local-first Python/FastMCP project with local SQLite storage. The outward product name, MCP server name, command names, data directory, docs, and installer use `client-workbench`; the internal Python package can stay `tam_workbench` during the pilot to minimize code churn and reduce regression risk.

**Tech Stack:** Python 3.11+, `uv`, FastMCP via `mcp`, Streamlit dashboard, SQLite, Claude Desktop local MCP config.

---

## Package Contents

The zip should include only portable source/distribution files:

```text
client-workbench/
  README.md
  INSTALL.md
  SECURITY.md
  install.sh
  pyproject.toml
  uv.lock
  scripts/launch-mcp.sh
  src/tam_workbench/*.py
  tests/*.py
  PACKAGING_PLAN.md
  CHANGELOG.md
```

Exclude:

```text
.venv/
.pytest_cache/
__pycache__/
.DS_Store
Icon\r
local SQLite databases
~/.tam-workbench or ~/.client-workbench data
any customer/client files
credentials/tokens/cookies
```

---

## Pilot User Experience

### Install

Coworker unzips the package, opens Terminal in the folder, then runs:

```bash
./install.sh
```

The installer should:

1. Check/install `uv` if missing, using the official Astral installer.
2. Run `uv sync --dev`.
3. Run `uv run client-workbench init` to create a blank local database.
4. Add/update the `client-workbench` MCP entry in Claude Desktop config:
   - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
5. Point Claude at `scripts/launch-mcp.sh` using an absolute path.
6. Tell the user to fully quit/restart Claude Desktop.

### Claude config entry

```json
{
  "mcpServers": {
    "client-workbench": {
      "command": "/absolute/path/to/client-workbench/scripts/launch-mcp.sh",
      "args": []
    }
  }
}
```

### Local data

Each pilot user gets a private local data directory:

```text
~/.client-workbench/
  client_workbench.db
  config.yaml
  templates/
  exports/
  reporting/
  logs/
```

---

## Implementation Tasks

### Task 1: Build a sanitized package tree

**Objective:** Create a temporary `client-workbench` folder containing only distributable files.

**Files:**
- Create: `/tmp/client-workbench-build/client-workbench/`

**Steps:**
1. Copy source files from `/Users/craigdunn/CoworkOS/tam-workbench`.
2. Exclude `.venv`, `.pytest_cache`, `__pycache__`, `.DS_Store`, `Icon\r`, local data, and generated zip files.
3. Confirm no `Icon\r` files remain.

**Verification:**

```bash
find /tmp/client-workbench-build/client-workbench -name $'Icon\r' -o -name '__pycache__' -o -name '.venv'
```

Expected: no output.

---

### Task 2: Rebrand pilot metadata to Client Workbench

**Objective:** Update outward-facing project names while keeping internal imports stable.

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/tam_workbench/db.py`
- Modify: `src/tam_workbench/server.py`
- Modify: tests that assert product name/data directory

**Changes:**
- `project.name`: `client-workbench`
- description: `Local MCP-enabled Client Workbench for Claude Desktop`
- scripts:
  - `client-workbench = tam_workbench.cli:main`
  - `client-workbench-mcp = tam_workbench.server:main`
  - `client-workbench-dashboard = tam_workbench.dashboard:main`
- default data dir: `~/.client-workbench`
- database filename: `client_workbench.db`
- FastMCP server name: `client-workbench`

**Verification:**

```bash
uv run pytest -q
```

Expected: all tests pass.

---

### Task 3: Add coworker-facing docs

**Objective:** Make the pilot understandable without Craig-specific context.

**Files:**
- Create/overwrite: `README.md`
- Create: `INSTALL.md`
- Create: `SECURITY.md`

**README must explain:**
- What Client Workbench does
- What it does not do
- How to install
- How to verify in Claude Desktop
- Example prompts
- How to run dashboard
- Where local data lives

**SECURITY must explain:**
- Local-only SQLite storage
- No Showpad credentials collected
- No direct Showpad API writes
- CSV exports remain local
- Users decide what they share with Claude

---

### Task 4: Add portable launcher and installer

**Objective:** Replace Craig-specific paths with scripts that work from any unzip location.

**Files:**
- Create/overwrite: `scripts/launch-mcp.sh`
- Create: `install.sh`

**Launcher behavior:**
- Resolve project root relative to script location.
- Resolve `uv` from PATH, Homebrew path, or `~/.local/bin/uv`.
- Silently delete macOS `Icon\r` files before startup.
- Exec `uv --directory "$PROJECT_DIR" run client-workbench-mcp`.
- Write nothing to stdout before MCP starts.

**Installer behavior:**
- Check/install `uv`.
- Run `uv sync --dev`.
- Initialize blank local database.
- Merge MCP config into Claude Desktop config.
- Keep existing MCP servers intact.

---

### Task 5: Create the zip

**Objective:** Produce a single sendable artifact.

**Output:**

```text
/Users/craigdunn/CoworkOS/tam-workbench/dist/client-workbench-pilot.zip
```

**Command:**

```bash
cd /tmp/client-workbench-build
zip -r /Users/craigdunn/CoworkOS/tam-workbench/dist/client-workbench-pilot.zip client-workbench
```

---

### Task 6: Verify the zip

**Objective:** Prove the sent artifact can unpack and pass tests.

**Steps:**
1. Unzip into `/tmp/client-workbench-verify`.
2. Run `uv sync --dev`.
3. Run `uv run pytest -q`.
4. Run a stdio MCP probe for initialize + tools/list.
5. Confirm the zip contains no `.venv`, `__pycache__`, `.pytest_cache`, `.DS_Store`, `Icon\r`, database, or local customer data.

**Expected:**
- Tests pass.
- MCP `initialize` succeeds.
- MCP `tools/list` returns Client Workbench tools.
- No excluded files found.

---

## Known Pilot Limitations

- This pilot still asks coworkers to run a shell installer.
- It assumes macOS + Claude Desktop.
- It uses `uv` and will install it if absent.
- It is not yet a one-click `.mcpb` Claude Desktop Extension.
- Internal Python package name remains `tam_workbench` for pilot stability.

## Future MCP Bundle Phase

After the pilot validates usefulness, package Client Workbench as `client-workbench.mcpb` so colleagues can install through Claude Desktop Extensions without Terminal or manual setup.
