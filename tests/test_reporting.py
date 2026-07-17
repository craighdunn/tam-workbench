import csv
import json

from tam_workbench.db import WorkbenchDB
from tam_workbench.tools import WorkbenchTools


def write_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def test_reporting_import_and_course_usage_summary(tmp_path):
    usage_csv = tmp_path / "course_usage.csv"
    write_csv(usage_csv, [
        {"User Email": "active@example.com", "Course Title": "Pitch Certification", "Status": "Completed", "Last Activity": "2026-05-01"},
        {"User Email": "active2@example.com", "Course Title": "Pitch Certification", "Status": "In Progress", "Last Activity": "2026-05-02"},
        {"User Email": "inactive@example.com", "Course Title": "Value Selling", "Status": "Not Started", "Last Activity": ""},
    ])

    db = WorkbenchDB(tmp_path / "data")
    db.initialize()
    imp = db.import_reporting_csv(usage_csv, "course_usage", label="May usage")
    summary = db.summarize_course_usage(imp["id"])

    assert imp["row_count"] == 3
    assert "User Email" in imp["columns"]
    assert summary["unique_user_count"] == 3
    assert summary["active_user_count"] == 2
    assert summary["status_counts"]["Completed"] == 1
    assert summary["top_courses_by_rows"][0] == ("Pitch Certification", 2)


def test_user_activity_can_cross_reference_course_usage(tmp_path):
    usage_csv = tmp_path / "course_usage.csv"
    users_csv = tmp_path / "users.csv"
    write_csv(usage_csv, [
        {"User Email": "used@example.com", "Course Title": "Course A", "Status": "Completed"},
    ])
    write_csv(users_csv, [
        {"User ID": "1", "Email": "used@example.com", "Name": "Used User", "Status": "Inactive"},
        {"User ID": "2", "Email": "enabled@example.com", "Name": "Enabled User", "Status": "Active"},
        {"User ID": "3", "Email": "off@example.com", "Name": "Off User", "Status": "Disabled"},
    ])

    tools = WorkbenchTools(tmp_path / "data")
    tools.initialize()
    usage = tools.import_reporting_csv({"file_path": str(usage_csv), "report_type": "course_usage"})["import"]
    users = tools.import_reporting_csv({"file_path": str(users_csv), "report_type": "user_metadata"})["import"]
    summary = tools.summarize_user_activity({"user_import_id": users["id"], "course_usage_import_id": usage["id"]})

    assert summary["success"] is True
    assert summary["summary"]["active_user_count"] == 2
    assert summary["summary"]["inactive_user_count"] == 1


def test_asset_metadata_summary_and_showpad_update_export(tmp_path):
    assets_csv = tmp_path / "assets.csv"
    write_csv(assets_csv, [
        {"Asset ID": "a1", "Title": "Deck", "Type": "PDF", "Owner": "Craig", "Status": "Published"},
        {"Asset ID": "a2", "Title": "", "Type": "Video", "Owner": "", "Status": "Draft"},
    ])

    db = WorkbenchDB(tmp_path / "data")
    db.initialize()
    imp = db.import_reporting_csv(assets_csv, "asset_metadata")
    summary = db.summarize_asset_metadata(imp["id"])
    export = db.export_showpad_update_csv(
        imp["id"],
        output_name="asset-updates.csv",
        columns="Asset ID,Title,Status",
        filters_json=json.dumps({"Status": "Draft"}),
        updates_json=json.dumps({"Status": "Archived"}),
    )

    assert summary["type_counts"] == {"PDF": 1, "Video": 1}
    assert summary["missing_metadata_count"] == 1
    assert export["row_count"] == 1
    exported = (tmp_path / "data" / "exports" / "asset-updates.csv").read_text()
    assert "Archived" in exported
    assert "a2" in exported
