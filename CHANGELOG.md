# Changelog

## v0.3.7 — Search cursor fix

### Fixed

- Account search now preserves the text cursor position after each live-filter re-render, preventing typed text from appearing backwards.

## v0.3.6 — Alphabetical account sidebar

### Changed

- Account sidebar now shows a single alphabetical list instead of grouping accounts by region/geographic reach.

## v0.3.5 — Dashboard edit panels and Kanban height polish

### Changed

- Kanban columns now extend to the available dashboard height and scroll inside the column.
- Task editing now uses an in-dashboard editor panel for title, description, weight, and due date.
- Contact editing now uses an in-dashboard editor panel for name, title, email, phone, contact type, and notes.
- Note editing now uses a large in-dashboard text area instead of a browser prompt for long note bodies.

## v0.3.4 — Same-page dashboard saves

Dashboard save actions now use a local async save bridge instead of opening a query-param tab.

### Changed

- Add/edit/archive actions save through a localhost API and keep the user in the same dashboard tab.
- The dashboard updates optimistically and shows a small `Saved` status instead of opening a new browser tab.

## v0.3.3 — Dashboard edit/archive controls

Adds dashboard-side contact typing, edits, and archive-based deletes.

### Added

- `+ Add Contact` now includes a Client Contact / Showpad Contact dropdown.
- Dashboard edit controls for accounts, tasks, contacts, and notes.
- Dashboard archive controls for accounts, tasks, contacts, and notes.
- Archive behavior hides records from the dashboard and default Claude list/search flows while preserving records for continuity.

### Changed

- Dashboard task delete now archives tasks by setting status to `archived` instead of hard-deleting them.
- Contact and note deletes now set `archived_at` instead of hard-deleting rows.
- Account archive also archives that account's tasks, contacts, and notes.

## v0.3.2 — Contact sections

Contacts tab now separates customer-side contacts from the internal Showpad account team.

### Added

- Clients section appears first in the Contacts tab.
- Showpad Account Team section appears below Clients.
- Contacts with `@showpad.com`, Showpad, TAM, CSM, account-team, or customer-success markers are grouped into the Showpad Account Team section.

## v0.3.1 — Dashboard persistence

Dashboard add actions now persist to the local TAM Workbench SQLite database.

### Added

- The dashboard `+` task flow creates real tasks in `~/.tam-workbench/tam_workbench.db`.
- The dashboard `+ Add Contact` flow creates real contacts in the database.
- The dashboard `+ Write a note` flow creates real notes in the database.
- Dragging an existing task between dashboard columns persists the task status change.
- Regression tests for dashboard-backed create and status update actions.

## v0.3.0 — Account dashboard fresh-install package

Added a coworker-ready fresh-install package with the redesigned TAM account dashboard.

### Added

- New dark TAM account dashboard shell with account sidebar, account header, task board, contacts view, and notes view.
- Fresh-install `install.sh` for macOS + Claude Desktop.
- Portable MCP launcher script that works from any unzip location.
- Optional macOS LaunchAgent installer so the dashboard starts at login.
- Coworker-facing `INSTALL.md` and `SECURITY.md`.

### Notes

- The install package starts with a blank local database for each coworker.
- Local data remains in `~/.tam-workbench/` and is not included in the package.

## v0.2.0-pilot — Contacts

Added structured client/account contacts so pilot users can store stakeholder names, email addresses, roles, titles, phone numbers, notes, and a primary-contact flag.

### Added

- New local `contacts` SQLite table linked to `accounts`.
- New Claude Desktop MCP tools:
  - `create_contact`
  - `list_contacts`
  - `get_contact`
  - `update_contact`
  - `delete_contact`
  - `search_contacts`
- `get_account_context` now includes account contacts alongside tasks, notes, and documents.
- Dashboard data now includes contact totals and primary-contact summaries per account.
- Dashboard now has a Contacts tab.

### Data safety

- Existing local account/task/note/document data is preserved.
- The database initializes or upgrades in place by creating the contacts table if it is missing.
- Contact data remains local in the user's SQLite database.

## v0.1.0-pilot — Initial pilot

Initial local Client Workbench/TAM Workbench pilot with accounts, tasks, notes, documents, dashboard views, local CSV reporting imports, and Claude Desktop MCP tools.
