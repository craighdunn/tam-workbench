from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from .db import WorkbenchDB


class WorkbenchTools:
    def __init__(self, data_dir: str | Path | None = None):
        self.db = WorkbenchDB(data_dir)

    def initialize(self) -> None:
        self.db.initialize()

    def _wrap(self, key: str, fn: Callable[[], Any]) -> dict[str, Any]:
        try:
            return {"success": True, key: fn()}
        except Exception as exc:
            return {"success": False, "error": str(exc), "error_type": type(exc).__name__}

    def create_account(self, args: dict[str, Any]) -> dict[str, Any]:
        return self._wrap("account", lambda: self.db.create_account(**_filter(args, {
            "name", "description", "industry", "region", "stakeholders", "technical_context", "business_context", "notes"
        })))

    def list_accounts(self, args: dict[str, Any]) -> dict[str, Any]:
        return self._wrap("accounts", lambda: self.db.list_accounts(limit=int(args.get("limit", 100))))

    def get_account(self, args: dict[str, Any]) -> dict[str, Any]:
        return self._wrap("account", lambda: self.db.get_account(int(args["account_id"])))

    def update_account(self, args: dict[str, Any]) -> dict[str, Any]:
        account_id = int(args["account_id"])
        fields = _filter(args, {"name", "description", "industry", "region", "stakeholders", "technical_context", "business_context", "notes"})
        return self._wrap("account", lambda: self.db.update_account(account_id, **fields))

    def search_accounts(self, args: dict[str, Any]) -> dict[str, Any]:
        return self._wrap("accounts", lambda: self.db.search_accounts(args.get("query", ""), int(args.get("limit", 25))))

    def create_contact(self, args: dict[str, Any]) -> dict[str, Any]:
        return self._wrap("contact", lambda: self.db.create_contact(**_filter(args, {
            "account_id", "name", "email", "role", "title", "phone", "notes", "is_primary", "support_level", "is_showpad_owner"
        })))

    def list_contacts(self, args: dict[str, Any]) -> dict[str, Any]:
        return self._wrap("contacts", lambda: self.db.list_contacts(
            account_id=args.get("account_id"),
            limit=int(args.get("limit", 100)),
        ))

    def get_contact(self, args: dict[str, Any]) -> dict[str, Any]:
        return self._wrap("contact", lambda: self.db.get_contact(int(args["contact_id"])))

    def update_contact(self, args: dict[str, Any]) -> dict[str, Any]:
        contact_id = int(args["contact_id"])
        fields = _filter(args, {"account_id", "name", "email", "role", "title", "phone", "notes", "is_primary", "support_level", "is_showpad_owner"})
        return self._wrap("contact", lambda: self.db.update_contact(contact_id, **fields))

    def delete_contact(self, args: dict[str, Any]) -> dict[str, Any]:
        return self._wrap("deleted", lambda: self.db.delete_contact(int(args["contact_id"])))

    def search_contacts(self, args: dict[str, Any]) -> dict[str, Any]:
        return self._wrap("contacts", lambda: self.db.search_contacts(args.get("query", ""), int(args.get("limit", 25))))

    def create_task(self, args: dict[str, Any]) -> dict[str, Any]:
        return self._wrap("task", lambda: self.db.create_task(**_filter(args, {
            "title", "account_id", "type", "status", "priority", "summary", "details", "next_action", "due_date"
        })))

    def list_tasks(self, args: dict[str, Any]) -> dict[str, Any]:
        return self._wrap("tasks", lambda: self.db.list_tasks(status=args.get("status"), account_id=args.get("account_id"), limit=int(args.get("limit", 100))))

    def get_task(self, args: dict[str, Any]) -> dict[str, Any]:
        return self._wrap("task", lambda: self.db.get_task(int(args["task_id"])))

    def update_task(self, args: dict[str, Any]) -> dict[str, Any]:
        task_id = int(args["task_id"])
        fields = _filter(args, {"title", "account_id", "type", "status", "priority", "summary", "details", "next_action", "due_date"})
        return self._wrap("task", lambda: self.db.update_task(task_id, **fields))

    def set_task_status(self, args: dict[str, Any]) -> dict[str, Any]:
        return self._wrap("task", lambda: self.db.set_task_status(int(args["task_id"]), args["status"]))

    def add_task_note(self, args: dict[str, Any]) -> dict[str, Any]:
        return self._wrap("note", lambda: self.db.add_task_note(int(args["task_id"]), title=args.get("title", ""), body=args.get("body", ""), source=args.get("source", "")))

    def search_tasks(self, args: dict[str, Any]) -> dict[str, Any]:
        return self._wrap("tasks", lambda: self.db.search_tasks(args.get("query", ""), int(args.get("limit", 25))))

    def create_note(self, args: dict[str, Any]) -> dict[str, Any]:
        return self._wrap("note", lambda: self.db.create_note(**_filter(args, {"account_id", "task_id", "title", "body", "source"})))

    def list_notes(self, args: dict[str, Any]) -> dict[str, Any]:
        return self._wrap("notes", lambda: self.db.list_notes(account_id=args.get("account_id"), task_id=args.get("task_id"), limit=int(args.get("limit", 100))))

    def search_notes(self, args: dict[str, Any]) -> dict[str, Any]:
        return self._wrap("notes", lambda: self.db.search_notes(args.get("query", ""), int(args.get("limit", 25))))

    def get_note(self, args: dict[str, Any]) -> dict[str, Any]:
        return self._wrap("note", lambda: self.db.get_note(int(args["note_id"])))

    def create_document(self, args: dict[str, Any]) -> dict[str, Any]:
        return self._wrap("document", lambda: self.db.create_document(**_filter(args, {"account_id", "task_id", "type", "title", "body"})))

    def list_documents(self, args: dict[str, Any]) -> dict[str, Any]:
        return self._wrap("documents", lambda: self.db.list_documents(account_id=args.get("account_id"), task_id=args.get("task_id"), type=args.get("type"), limit=int(args.get("limit", 100))))

    def get_document(self, args: dict[str, Any]) -> dict[str, Any]:
        return self._wrap("document", lambda: self.db.get_document(int(args["document_id"])))

    def update_document(self, args: dict[str, Any]) -> dict[str, Any]:
        document_id = int(args["document_id"])
        fields = _filter(args, {"account_id", "task_id", "type", "title", "body"})
        return self._wrap("document", lambda: self.db.update_document(document_id, **fields))

    def export_document_markdown(self, args: dict[str, Any]) -> dict[str, Any]:
        return self._wrap("path", lambda: str(self.db.export_document_markdown(int(args["document_id"]))))

    def create_link(self, args: dict[str, Any]) -> dict[str, Any]:
        return self._wrap("link", lambda: self.db.create_link(
            account_id=int(args["account_id"]),
            link_type=args.get("link_type", "other"),
            label=args.get("label", ""),
            url=args.get("url", ""),
        ))

    def list_links(self, args: dict[str, Any]) -> dict[str, Any]:
        return self._wrap("links", lambda: self.db.list_links(account_id=args.get("account_id")))

    def get_link(self, args: dict[str, Any]) -> dict[str, Any]:
        return self._wrap("link", lambda: self.db.get_link(int(args["link_id"])))

    def update_link(self, args: dict[str, Any]) -> dict[str, Any]:
        link_id = int(args["link_id"])
        fields = _filter(args, {"link_type", "label", "url"})
        return self._wrap("link", lambda: self.db.update_link(link_id, **fields))

    def archive_link(self, args: dict[str, Any]) -> dict[str, Any]:
        return self._wrap("link", lambda: self.db.archive_link(int(args["link_id"])))

    def get_account_context(self, args: dict[str, Any]) -> dict[str, Any]:
        return self._wrap("context", lambda: self.db.get_account_context(int(args["account_id"])))

    def get_task_context(self, args: dict[str, Any]) -> dict[str, Any]:
        return self._wrap("context", lambda: self.db.get_task_context(int(args["task_id"])))

    def summarize_open_work(self, args: dict[str, Any]) -> dict[str, Any]:
        return self._wrap("summary", self.db.summarize_open_work)

    def daily_work_snapshot(self, args: dict[str, Any]) -> dict[str, Any]:
        return self._wrap("snapshot", self.db.daily_work_snapshot)


    def import_reporting_csv(self, args: dict[str, Any]) -> dict[str, Any]:
        return self._wrap("import", lambda: self.db.import_reporting_csv(
            file_path=args["file_path"],
            report_type=args.get("report_type", "general_export"),
            account_id=args.get("account_id"),
            label=args.get("label", ""),
        ))

    def list_reporting_imports(self, args: dict[str, Any]) -> dict[str, Any]:
        return self._wrap("imports", lambda: self.db.list_reporting_imports(
            report_type=args.get("report_type"),
            account_id=args.get("account_id"),
            limit=int(args.get("limit", 50)),
        ))

    def get_reporting_import(self, args: dict[str, Any]) -> dict[str, Any]:
        return self._wrap("import", lambda: self.db.get_reporting_import(
            int(args["import_id"]), sample_size=int(args.get("sample_size", 10))
        ))

    def summarize_course_usage(self, args: dict[str, Any]) -> dict[str, Any]:
        return self._wrap("summary", lambda: self.db.summarize_course_usage(
            import_id=int(args["import_id"]),
            user_column=args.get("user_column", ""),
            course_column=args.get("course_column", ""),
            status_column=args.get("status_column", ""),
            active_statuses=args.get("active_statuses", "completed,in progress,passed,started"),
            last_activity_column=args.get("last_activity_column", ""),
        ))

    def summarize_user_activity(self, args: dict[str, Any]) -> dict[str, Any]:
        course_usage_import_id = args.get("course_usage_import_id")
        return self._wrap("summary", lambda: self.db.summarize_user_activity(
            user_import_id=int(args["user_import_id"]),
            course_usage_import_id=int(course_usage_import_id) if course_usage_import_id is not None else None,
            user_id_column=args.get("user_id_column", ""),
            email_column=args.get("email_column", ""),
            name_column=args.get("name_column", ""),
            active_column=args.get("active_column", ""),
            last_login_column=args.get("last_login_column", ""),
        ))

    def summarize_asset_metadata(self, args: dict[str, Any]) -> dict[str, Any]:
        return self._wrap("summary", lambda: self.db.summarize_asset_metadata(
            import_id=int(args["import_id"]),
            asset_id_column=args.get("asset_id_column", ""),
            title_column=args.get("title_column", ""),
            type_column=args.get("type_column", ""),
            owner_column=args.get("owner_column", ""),
            status_column=args.get("status_column", ""),
        ))

    def export_showpad_update_csv(self, args: dict[str, Any]) -> dict[str, Any]:
        return self._wrap("export", lambda: self.db.export_showpad_update_csv(
            source_import_id=int(args["source_import_id"]),
            output_name=args.get("output_name", "showpad-update.csv"),
            columns=args.get("columns", ""),
            filters_json=args.get("filters_json", "{}"),
            updates_json=args.get("updates_json", "{}"),
        ))


def _filter(args: dict[str, Any], allowed: set[str]) -> dict[str, Any]:
    return {k: v for k, v in args.items() if k in allowed and v is not None}
