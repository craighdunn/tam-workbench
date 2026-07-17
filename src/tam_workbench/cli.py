from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .db import default_data_dir
from .templates import ensure_default_templates
from .tools import WorkbenchTools


def print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="tam-workbench", description="Inspect and debug TAM Workbench local data")
    parser.add_argument("--data-dir", default=str(default_data_dir()))
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="Initialize database and templates")
    sub.add_parser("snapshot", help="Print daily work snapshot")

    accounts = sub.add_parser("accounts", help="Account commands")
    accounts_sub = accounts.add_subparsers(dest="accounts_command", required=True)
    accounts_sub.add_parser("list")
    account_show = accounts_sub.add_parser("show")
    account_show.add_argument("id", type=int)

    tasks = sub.add_parser("tasks", help="Task commands")
    tasks_sub = tasks.add_subparsers(dest="tasks_command", required=True)
    tasks_sub.add_parser("list")
    task_show = tasks_sub.add_parser("show")
    task_show.add_argument("id", type=int)


    reporting = sub.add_parser("reporting", help="Reporting CSV import and analysis commands")
    reporting_sub = reporting.add_subparsers(dest="reporting_command", required=True)
    reporting_import = reporting_sub.add_parser("import")
    reporting_import.add_argument("report_type", choices=["course_usage", "asset_metadata", "user_metadata", "general_export"])
    reporting_import.add_argument("file_path")
    reporting_import.add_argument("--label", default="")
    reporting_import.add_argument("--account-id", type=int)
    reporting_sub.add_parser("list")
    course_summary = reporting_sub.add_parser("course-usage")
    course_summary.add_argument("import_id", type=int)
    user_summary = reporting_sub.add_parser("user-activity")
    user_summary.add_argument("user_import_id", type=int)
    user_summary.add_argument("--course-usage-import-id", type=int)
    asset_summary = reporting_sub.add_parser("asset-metadata")
    asset_summary.add_argument("import_id", type=int)

    export = sub.add_parser("export", help="Export commands")
    export_sub = export.add_subparsers(dest="export_command", required=True)
    doc_export = export_sub.add_parser("document")
    doc_export.add_argument("id", type=int)

    args = parser.parse_args(argv)
    tools = WorkbenchTools(Path(args.data_dir))
    tools.initialize()
    ensure_default_templates(tools.db.templates_dir)

    if args.command == "init":
        print_json({"success": True, "data_dir": str(tools.db.data_dir), "db_path": str(tools.db.db_path)})
    elif args.command == "snapshot":
        print_json(tools.daily_work_snapshot({}))
    elif args.command == "accounts" and args.accounts_command == "list":
        print_json(tools.list_accounts({}))
    elif args.command == "accounts" and args.accounts_command == "show":
        print_json(tools.get_account({"account_id": args.id}))
    elif args.command == "tasks" and args.tasks_command == "list":
        print_json(tools.list_tasks({}))
    elif args.command == "tasks" and args.tasks_command == "show":
        print_json(tools.get_task_context({"task_id": args.id}))
    elif args.command == "reporting" and args.reporting_command == "import":
        print_json(tools.import_reporting_csv({"report_type": args.report_type, "file_path": args.file_path, "label": args.label, "account_id": args.account_id}))
    elif args.command == "reporting" and args.reporting_command == "list":
        print_json(tools.list_reporting_imports({}))
    elif args.command == "reporting" and args.reporting_command == "course-usage":
        print_json(tools.summarize_course_usage({"import_id": args.import_id}))
    elif args.command == "reporting" and args.reporting_command == "user-activity":
        print_json(tools.summarize_user_activity({"user_import_id": args.user_import_id, "course_usage_import_id": args.course_usage_import_id}))
    elif args.command == "reporting" and args.reporting_command == "asset-metadata":
        print_json(tools.summarize_asset_metadata({"import_id": args.import_id}))
    elif args.command == "export" and args.export_command == "document":
        print_json(tools.export_document_markdown({"document_id": args.id}))


if __name__ == "__main__":
    main()
