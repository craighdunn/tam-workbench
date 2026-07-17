# TAM Workbench

TAM Workbench is a local Claude Desktop MCP tool for Technical Account Manager work. It gives Claude a small local database for accounts, contacts, tasks, notes, reusable documents, and local reporting/import helpers. It also includes a local dashboard at `http://127.0.0.1:8501`.

The tool is intentionally local-first: Claude Desktop is the reasoning interface, while TAM Workbench provides local storage and structured tools.

## What it provides

- Local SQLite storage
- Account records
- Structured account contacts and stakeholder email addresses
- Task tracking and open-work snapshots
- Notes and reusable Markdown documents
- Markdown export
- Local CSV reporting import/analysis for Showpad exports
- Course usage summaries and active-user identification
- Asset/user metadata review and local CSV export helpers
- Claude Desktop MCP tools
- A local Streamlit dashboard
- Optional dashboard auto-start at Mac login

## What it does not provide

- No Showpad credential storage
- No direct Showpad API updates
- No browser automation
- No arbitrary shell execution through MCP
- No cloud database or shared server

## Fresh install

See [`INSTALL.md`](INSTALL.md).

Quick version:

```bash
./install.sh
```

Install and configure dashboard auto-start at login:

```bash
./install.sh --start-dashboard-at-login
```

After install, fully quit and reopen Claude Desktop.

## Dashboard

Start manually:

```bash
uv run tam-workbench-dashboard
```

Open:

```text
http://127.0.0.1:8501
```

Auto-start at login:

```bash
./scripts/install-dashboard-autostart.sh
```

Remove auto-start:

```bash
./scripts/uninstall-dashboard-autostart.sh
```

## Local data

Each user has a private local data directory:

```text
~/.tam-workbench/
  tam_workbench.db
  config.yaml
  templates/
  exports/
  reporting/
  logs/
```

The install package does not include Craig's data or any coworker's data.

## Claude Desktop MCP configuration

The installer adds this server to Claude Desktop:

```json
{
  "mcpServers": {
    "tam-workbench": {
      "command": "/absolute/path/to/tam-workbench/scripts/launch-mcp.sh",
      "args": []
    }
  }
}
```

Config path on macOS:

```text
~/Library/Application Support/Claude/claude_desktop_config.json
```

The installer preserves existing MCP servers.

## MCP tools

Account tools:

- `create_account`
- `list_accounts`
- `get_account`
- `update_account`
- `search_accounts`

Contact tools:

- `create_contact`
- `list_contacts`
- `get_contact`
- `update_contact`
- `delete_contact`
- `search_contacts`

Task tools:

- `create_task`
- `list_tasks`
- `get_task`
- `update_task`
- `set_task_status`
- `add_task_note`
- `search_tasks`

Note tools:

- `create_note`
- `list_notes`
- `search_notes`
- `get_note`

Document tools:

- `create_document`
- `list_documents`
- `get_document`
- `update_document`
- `export_document_markdown`

Context tools:

- `get_account_context`
- `get_task_context`
- `summarize_open_work`
- `daily_work_snapshot`

Reporting tools:

- `import_reporting_csv`
- `list_reporting_imports`
- `get_reporting_import`
- `summarize_course_usage`
- `summarize_user_activity`
- `summarize_asset_metadata`
- `export_showpad_update_csv`

## Example Claude prompts

```text
Create an account for Acme in TAM Workbench.
```

```text
Add Jane Smith as the executive sponsor for Acme with email jane@example.com.
```

```text
Create a high-priority task for Acme to follow up on the QBR deck by Friday.
```

```text
What are my active customer issues and next actions?
```

```text
Import this Showpad course usage CSV and summarize active learners, course engagement, and completion statuses.
```

## Development / verification

```bash
uv sync --dev
uv run pytest -q
uv run tam-workbench init
```

Implementation files:

- `src/tam_workbench/db.py` — SQLite schema and data operations
- `src/tam_workbench/tools.py` — MCP tool wrappers
- `src/tam_workbench/server.py` — MCP server
- `src/tam_workbench/dashboard.py` — local dashboard
- `src/tam_workbench/cli.py` — local inspection/debugging CLI
- `tests/` — regression tests

## Security

See [`SECURITY.md`](SECURITY.md).
