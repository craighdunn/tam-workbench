from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from .db import default_data_dir
from .templates import ensure_default_templates
from .tools import WorkbenchTools


def build_server(data_dir: str | Path | None = None) -> FastMCP:
    tools = WorkbenchTools(data_dir or default_data_dir())
    tools.initialize()
    ensure_default_templates(tools.db.templates_dir)

    mcp = FastMCP("tam-workbench")

    @mcp.tool()
    def create_account(name: str, description: str = "", industry: str = "", region: str = "",
                       stakeholders: str = "", technical_context: str = "", business_context: str = "",
                       notes: str = "") -> dict[str, Any]:
        """Create a structured account record."""
        return tools.create_account(locals())

    @mcp.tool()
    def list_accounts(limit: int = 100) -> dict[str, Any]:
        """List account records."""
        return tools.list_accounts(locals())

    @mcp.tool()
    def get_account(account_id: int) -> dict[str, Any]:
        """Retrieve one account by ID."""
        return tools.get_account(locals())

    @mcp.tool()
    def update_account(account_id: int, name: str | None = None, description: str | None = None,
                       industry: str | None = None, region: str | None = None, stakeholders: str | None = None,
                       technical_context: str | None = None, business_context: str | None = None,
                       notes: str | None = None) -> dict[str, Any]:
        """Update fields on an account."""
        return tools.update_account(locals())

    @mcp.tool()
    def search_accounts(query: str, limit: int = 25) -> dict[str, Any]:
        """Search accounts across account fields."""
        return tools.search_accounts(locals())

    @mcp.tool()
    def create_contact(account_id: int, name: str, email: str = "", role: str = "", title: str = "",
                       phone: str = "", notes: str = "", is_primary: bool = False,
                       support_level: str = "neutral", is_showpad_owner: bool = False) -> dict[str, Any]:
        """Create a structured contact/stakeholder linked to an account."""
        return tools.create_contact(locals())

    @mcp.tool()
    def list_contacts(account_id: int | None = None, limit: int = 100) -> dict[str, Any]:
        """List contacts, optionally filtered by account."""
        return tools.list_contacts(locals())

    @mcp.tool()
    def get_contact(contact_id: int) -> dict[str, Any]:
        """Retrieve one contact by ID."""
        return tools.get_contact(locals())

    @mcp.tool()
    def update_contact(contact_id: int, account_id: int | None = None, name: str | None = None,
                       email: str | None = None, role: str | None = None, title: str | None = None,
                       phone: str | None = None, notes: str | None = None,
                       is_primary: bool | None = None, support_level: str | None = None,
                       is_showpad_owner: bool | None = None) -> dict[str, Any]:
        """Update fields on a contact/stakeholder."""
        return tools.update_contact(locals())

    @mcp.tool()
    def delete_contact(contact_id: int) -> dict[str, Any]:
        """Delete a contact/stakeholder."""
        return tools.delete_contact(locals())

    @mcp.tool()
    def search_contacts(query: str, limit: int = 25) -> dict[str, Any]:
        """Search contacts across name, email, role, title, phone, notes, and account name."""
        return tools.search_contacts(locals())

    @mcp.tool()
    def create_task(title: str, account_id: int | None = None, type: str = "general", status: str = "inbox",
                    priority: str = "normal", summary: str = "", details: str = "", next_action: str = "",
                    due_date: str | None = None) -> dict[str, Any]:
        """Create a task, optionally linked to an account."""
        return tools.create_task(locals())

    @mcp.tool()
    def list_tasks(status: str | None = None, account_id: int | None = None, limit: int = 100) -> dict[str, Any]:
        """List tasks, optionally filtered by status or account."""
        return tools.list_tasks(locals())

    @mcp.tool()
    def get_task(task_id: int) -> dict[str, Any]:
        """Retrieve one task by ID."""
        return tools.get_task(locals())

    @mcp.tool()
    def update_task(task_id: int, title: str | None = None, account_id: int | None = None,
                    type: str | None = None, status: str | None = None, priority: str | None = None,
                    summary: str | None = None, details: str | None = None, next_action: str | None = None,
                    due_date: str | None = None) -> dict[str, Any]:
        """Update fields on a task."""
        return tools.update_task(locals())

    @mcp.tool()
    def set_task_status(task_id: int, status: str) -> dict[str, Any]:
        """Set a task status."""
        return tools.set_task_status(locals())

    @mcp.tool()
    def add_task_note(task_id: int, title: str = "", body: str = "", source: str = "") -> dict[str, Any]:
        """Add a note linked to a task."""
        return tools.add_task_note(locals())

    @mcp.tool()
    def search_tasks(query: str, limit: int = 25) -> dict[str, Any]:
        """Search tasks across task fields."""
        return tools.search_tasks(locals())

    @mcp.tool()
    def create_note(account_id: int | None = None, task_id: int | None = None, title: str = "",
                    body: str = "", source: str = "") -> dict[str, Any]:
        """Create a freeform note linked to an account and/or task."""
        return tools.create_note(locals())

    @mcp.tool()
    def list_notes(account_id: int | None = None, task_id: int | None = None, limit: int = 100) -> dict[str, Any]:
        """List notes."""
        return tools.list_notes(locals())

    @mcp.tool()
    def search_notes(query: str, limit: int = 25) -> dict[str, Any]:
        """Search notes."""
        return tools.search_notes(locals())

    @mcp.tool()
    def get_note(note_id: int) -> dict[str, Any]:
        """Retrieve one note by ID."""
        return tools.get_note(locals())

    @mcp.tool()
    def create_document(account_id: int | None = None, task_id: int | None = None, type: str = "general",
                        title: str = "", body: str = "") -> dict[str, Any]:
        """Create a Markdown document linked to an account and/or task."""
        return tools.create_document(locals())

    @mcp.tool()
    def list_documents(account_id: int | None = None, task_id: int | None = None,
                       type: str | None = None, limit: int = 100) -> dict[str, Any]:
        """List documents."""
        return tools.list_documents(locals())

    @mcp.tool()
    def get_document(document_id: int) -> dict[str, Any]:
        """Retrieve one document by ID."""
        return tools.get_document(locals())

    @mcp.tool()
    def update_document(document_id: int, account_id: int | None = None, task_id: int | None = None,
                        type: str | None = None, title: str | None = None, body: str | None = None) -> dict[str, Any]:
        """Update fields on a document."""
        return tools.update_document(locals())

    @mcp.tool()
    def export_document_markdown(document_id: int) -> dict[str, Any]:
        """Export a stored document body to a Markdown file."""
        return tools.export_document_markdown(locals())

    @mcp.tool()
    def get_account_context(account_id: int) -> dict[str, Any]:
        """Return account details with linked tasks, notes, and documents."""
        return tools.get_account_context(locals())

    @mcp.tool()
    def get_task_context(task_id: int) -> dict[str, Any]:
        """Return task details with account, notes, and documents."""
        return tools.get_task_context(locals())

    @mcp.tool()
    def summarize_open_work() -> dict[str, Any]:
        """Summarize open work across inbox, active, waiting, and blocked tasks."""
        return tools.summarize_open_work({})

    @mcp.tool()
    def daily_work_snapshot() -> dict[str, Any]:
        """Return urgent, blocked, waiting, next-action, and recent-document snapshot."""
        return tools.daily_work_snapshot({})


    @mcp.tool()
    def import_reporting_csv(file_path: str, report_type: str = "general_export", account_id: int | None = None,
                             label: str = "") -> dict[str, Any]:
        """Import a local Showpad/reporting CSV into TAM Workbench for analysis. report_type: course_usage, asset_metadata, user_metadata, or general_export."""
        return tools.import_reporting_csv(locals())

    @mcp.tool()
    def list_reporting_imports(report_type: str | None = None, account_id: int | None = None,
                               limit: int = 50) -> dict[str, Any]:
        """List previously imported reporting CSV files."""
        return tools.list_reporting_imports(locals())

    @mcp.tool()
    def get_reporting_import(import_id: int, sample_size: int = 10) -> dict[str, Any]:
        """Show metadata, detected columns, and sample rows for a reporting import."""
        return tools.get_reporting_import(locals())

    @mcp.tool()
    def summarize_course_usage(import_id: int, user_column: str = "", course_column: str = "",
                               status_column: str = "", active_statuses: str = "completed,in progress,passed,started",
                               last_activity_column: str = "") -> dict[str, Any]:
        """Summarize a course usage CSV: active users, course counts, status counts, and detected columns."""
        return tools.summarize_course_usage(locals())

    @mcp.tool()
    def summarize_user_activity(user_import_id: int, course_usage_import_id: int | None = None,
                                user_id_column: str = "", email_column: str = "", name_column: str = "",
                                active_column: str = "", last_login_column: str = "") -> dict[str, Any]:
        """Identify active and inactive users from a user metadata CSV, optionally cross-referenced with course usage."""
        return tools.summarize_user_activity(locals())

    @mcp.tool()
    def summarize_asset_metadata(import_id: int, asset_id_column: str = "", title_column: str = "",
                                 type_column: str = "", owner_column: str = "", status_column: str = "") -> dict[str, Any]:
        """Summarize asset metadata CSV exports and flag rows with missing key metadata."""
        return tools.summarize_asset_metadata(locals())

    @mcp.tool()
    def export_showpad_update_csv(source_import_id: int, output_name: str = "showpad-update.csv",
                                  columns: str = "", filters_json: str = "{}", updates_json: str = "{}") -> dict[str, Any]:
        """Create a local CSV export for Showpad bulk updates from an imported CSV. filters_json and updates_json are JSON objects."""
        return tools.export_showpad_update_csv(locals())

    return mcp


def main() -> None:
    build_server().run()


if __name__ == "__main__":
    main()
