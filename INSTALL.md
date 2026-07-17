# Install TAM Workbench

This is a fresh-install package for TAM Workbench, a local Claude Desktop MCP tool and local dashboard for account work.

## What gets installed

- A local SQLite database at `~/.tam-workbench/tam_workbench.db`
- Claude Desktop MCP tools under the server name `tam-workbench`
- A local dashboard at `http://127.0.0.1:8501`
- Optional macOS login auto-start for the dashboard

TAM Workbench runs locally. It does not store Showpad credentials and does not call Showpad APIs directly.

## Requirements

- macOS
- Claude Desktop
- Python 3.11 or newer
- Internet access for first install, so `uv` can install Python dependencies

The installer will install `uv` automatically if it cannot find it.

## Quick install

1. Unzip the package.
2. Move the folder somewhere stable, for example:

   ```text
   ~/Applications/tam-workbench
   ```

   The folder location matters because Claude Desktop and the optional dashboard auto-start point to this folder.

3. Open Terminal in the unzipped `tam-workbench` folder.
4. Run:

   ```bash
   ./install.sh
   ```

5. Fully quit Claude Desktop, then reopen it.
6. In Claude, ask:

   ```text
   What TAM Workbench tools do you have?
   ```

## Install and start the dashboard at login

If you want the dashboard to start automatically when you log into your Mac, run:

```bash
./install.sh --start-dashboard-at-login
```

Or, if TAM Workbench is already installed:

```bash
./scripts/install-dashboard-autostart.sh
```

Then open:

```text
http://127.0.0.1:8501
```

To remove the dashboard auto-start later:

```bash
./scripts/uninstall-dashboard-autostart.sh
```

## Install with Claude or Claude Code

If you prefer Claude to walk through the install, unzip the package and give Claude this prompt:

```text
Please install TAM Workbench from this folder as a fresh local Claude Desktop MCP tool.

Folder: /full/path/to/tam-workbench

Please:
1. Read INSTALL.md and README.md.
2. Run ./install.sh from that folder.
3. If I want the dashboard to start at login, run ./scripts/install-dashboard-autostart.sh.
4. Verify `uv run pytest -q` passes.
5. Tell me to fully quit and reopen Claude Desktop.
6. Confirm the dashboard URL is http://127.0.0.1:8501.
```

If Claude cannot run shell commands in your setup, use the Quick install steps above in Terminal.

## Verify the install

From the `tam-workbench` folder:

```bash
uv run pytest -q
uv run tam-workbench init
uv run tam-workbench snapshot
```

Start the dashboard manually:

```bash
uv run tam-workbench-dashboard
```

Then open:

```text
http://127.0.0.1:8501
```

## Claude Desktop config

The installer adds this MCP server entry to:

```text
~/Library/Application Support/Claude/claude_desktop_config.json
```

The entry looks like this:

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

The installer preserves existing MCP servers.

## Example Claude prompts

After restarting Claude Desktop, try:

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
What are my open TAM Workbench tasks today?
```

```text
Create a meeting recap for Acme and store it in TAM Workbench.
```

## Important notes

- Keep the `tam-workbench` folder in the same location after installing. If you move it, rerun `./install.sh` so Claude Desktop points to the new path.
- Each user has their own private local database in `~/.tam-workbench/`.
- The dashboard is local-only and served from your Mac.
- If port `8501` is already in use, stop the other Streamlit app or run the dashboard manually on another port with Streamlit options.
