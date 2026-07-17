from datetime import date, timedelta

import pytest

from tam_workbench.dashboard_data import (
    build_dashboard_data,
    delete_dashboard_task,
    set_dashboard_account_color,
    set_dashboard_task_status,
)
from tam_workbench.db import WorkbenchDB


def test_build_dashboard_data_groups_tasks_and_accounts(tmp_path):
    db = WorkbenchDB(tmp_path)
    db.initialize()

    acme = db.create_account(name="Acme", region="NA")
    beta = db.create_account(name="Beta", region="EMEA")
    db.create_task(title="Inbox task", account_id=acme["id"], status="inbox", priority="high", next_action="Triage")
    db.create_task(title="Blocked task", account_id=acme["id"], status="blocked", priority="urgent")
    db.create_task(title="Done task", account_id=beta["id"], status="done", priority="low")
    db.create_document(account_id=acme["id"], type="general", title="Doc", body="Body")

    data = build_dashboard_data(tmp_path)

    assert data["summary"]["account_count"] == 2
    assert data["summary"]["open_task_count"] == 2
    assert data["status_counts"]["inbox"] == 1
    assert data["status_counts"]["blocked"] == 1
    assert data["priority_counts"]["urgent"] == 1
    assert data["tasks_by_status"]["blocked"][0]["title"] == "Blocked task"
    assert data["tasks_by_account"][0]["account_name"] == "Acme"
    assert data["tasks_by_account"][0]["open_task_count"] == 2
    assert data["tasks_by_account"][0]["account_color"] == ""


def test_build_dashboard_data_includes_contacts_and_primary_contact_summary(tmp_path):
    db = WorkbenchDB(tmp_path)
    db.initialize()
    acme = db.create_account(name="Acme", region="NA")
    db.create_contact(account_id=acme["id"], name="Jane Smith", email="jane@example.com", role="Executive Sponsor", is_primary=True)
    db.create_contact(account_id=acme["id"], name="Alex Admin", email="alex@example.com", role="Admin")

    data = build_dashboard_data(tmp_path)

    assert data["summary"]["contact_count"] == 2
    assert [row["email"] for row in data["contacts"]] == ["jane@example.com", "alex@example.com"]
    assert data["tasks_by_account"][0]["contact_count"] == 2
    assert data["tasks_by_account"][0]["primary_contact"] == "Jane Smith <jane@example.com>"


def test_dashboard_account_color_persists_and_flows_to_tasks(tmp_path):
    db = WorkbenchDB(tmp_path)
    db.initialize()
    account = db.create_account(name="ColorCo")
    db.create_task(title="Color-coded task", account_id=account["id"], status="inbox")

    updated = set_dashboard_account_color(tmp_path, account["id"], "#FFE8A3")
    data = build_dashboard_data(tmp_path)

    assert updated["account_color"] == "#FFE8A3"
    assert data["accounts"][0]["account_color"] == "#FFE8A3"
    assert data["tasks"][0]["account_color"] == "#FFE8A3"
    assert data["tasks_by_status"]["inbox"][0]["account_color"] == "#FFE8A3"
    assert data["tasks_by_account"][0]["account_color"] == "#FFE8A3"


def test_dashboard_account_color_rejects_invalid_values(tmp_path):
    db = WorkbenchDB(tmp_path)
    db.initialize()
    account = db.create_account(name="ColorCo")

    with pytest.raises(ValueError, match="hex color"):
        set_dashboard_account_color(tmp_path, account["id"], "not-a-color")


def test_build_dashboard_data_surfaces_focus_queue(tmp_path):
    db = WorkbenchDB(tmp_path)
    db.initialize()

    acme = db.create_account(name="Acme", region="NA")
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()

    db.create_task(
        title="Blocked urgent task",
        account_id=acme["id"],
        status="blocked",
        priority="urgent",
        next_action="Escalate blocker",
    )
    db.create_task(
        title="Overdue high task",
        account_id=acme["id"],
        status="active",
        priority="high",
        due_date=yesterday,
        next_action="Follow up today",
    )
    db.create_task(
        title="Upcoming normal task",
        account_id=acme["id"],
        status="waiting",
        priority="normal",
        due_date=tomorrow,
    )
    db.create_task(
        title="Completed urgent task",
        account_id=acme["id"],
        status="done",
        priority="urgent",
        due_date=yesterday,
    )

    data = build_dashboard_data(tmp_path)

    assert [task["title"] for task in data["focus_tasks"]] == [
        "Blocked urgent task",
        "Overdue high task",
        "Upcoming normal task",
    ]
    assert data["focus_tasks"][0]["focus_reason"] == "blocked"
    assert data["focus_tasks"][1]["focus_reason"] == "overdue"


def test_set_dashboard_task_status_persists_board_transition(tmp_path):
    db = WorkbenchDB(tmp_path)
    db.initialize()
    task = db.create_task(title="Move me", status="inbox", priority="high")

    updated = set_dashboard_task_status(tmp_path, task["id"], "active")
    data = build_dashboard_data(tmp_path)

    assert updated["status"] == "active"
    assert db.get_task(task["id"])["status"] == "active"
    assert [row["title"] for row in data["tasks_by_status"]["active"]] == ["Move me"]
    assert data["status_counts"]["inbox"] == 0
    assert data["status_counts"]["active"] == 1


def test_set_dashboard_task_status_rejects_unknown_status(tmp_path):
    db = WorkbenchDB(tmp_path)
    db.initialize()
    task = db.create_task(title="Keep me", status="inbox")

    with pytest.raises(ValueError, match="invalid status"):
        set_dashboard_task_status(tmp_path, task["id"], "plot_complete")

    assert db.get_task(task["id"])["status"] == "inbox"


def test_delete_dashboard_task_archives_without_deleting_account(tmp_path):
    db = WorkbenchDB(tmp_path)
    db.initialize()
    account = db.create_account(name="Acme")
    task = db.create_task(title="No longer needed", account_id=account["id"], status="waiting")

    result = delete_dashboard_task(tmp_path, task["id"])
    data = build_dashboard_data(tmp_path)

    assert result == {"deleted_task_id": task["id"]}
    assert db.get_task(task["id"])["status"] == "archived"
    assert db.get_account(account["id"])["name"] == "Acme"
    assert data["tasks"] == []
    assert data["summary"]["open_task_count"] == 0


def test_archived_records_are_hidden_from_dashboard_and_default_lists(tmp_path):
    db = WorkbenchDB(tmp_path)
    db.initialize()
    account = db.create_account(name="Archive Me")
    kept = db.create_account(name="Keep Me")
    task = db.create_task(title="Hidden task", account_id=account["id"], status="active")
    contact = db.create_contact(account_id=account["id"], name="Hidden Contact", email="hidden@example.com")
    note = db.create_note(account_id=account["id"], body="Hidden note")

    archived = db.archive_account(account["id"])
    data = build_dashboard_data(tmp_path)

    assert archived["archived_at"]
    assert [row["name"] for row in db.list_accounts()] == ["Keep Me"]
    assert db.list_accounts(include_archived=True)[0]["name"] == "Archive Me"
    assert db.list_tasks() == []
    assert db.list_contacts() == []
    assert db.list_notes() == []
    assert db.get_task(task["id"])["status"] == "archived"
    assert db.get_contact(contact["id"])["archived_at"]
    assert db.get_note(note["id"])["archived_at"]
    assert [row["name"] for row in data["accounts"]] == [kept["name"]]