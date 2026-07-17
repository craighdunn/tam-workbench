# Security and Data Notes

TAM Workbench is designed as a local-first Claude Desktop helper.

## Local storage

TAM Workbench stores its data in a local SQLite database on your Mac:

```text
~/.tam-workbench/tam_workbench.db
```

The database is not included in this install package. Every coworker starts with a fresh local database.

## No Showpad credential storage

TAM Workbench does not collect, store, or require Showpad credentials, cookies, browser sessions, or API tokens.

## No direct Showpad API writes

TAM Workbench does not directly update Showpad. Reporting features work from local CSV exports and can create local review files for you to inspect.

## Claude Desktop access

When Claude Desktop uses TAM Workbench, Claude can ask the local MCP server to create/read/update records in your local TAM Workbench database. Only put information into TAM Workbench that you are comfortable using with Claude Desktop under your organization's AI/data policies.

## Local files

Exports and reports are written locally under:

```text
~/.tam-workbench/exports/
~/.tam-workbench/reporting/
```

You decide what to share externally.

## Removing local data

To remove TAM Workbench data from your Mac, first quit Claude Desktop and stop the dashboard, then delete:

```bash
rm -rf ~/.tam-workbench
```

To remove dashboard auto-start:

```bash
./scripts/uninstall-dashboard-autostart.sh
```
