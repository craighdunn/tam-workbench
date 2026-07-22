from pathlib import Path

from tam_workbench.db import WorkbenchDB, default_data_dir


def test_default_data_dir_is_predictable(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert default_data_dir() == tmp_path / ".tam-workbench"


def test_database_initializes_expected_tables(tmp_path):
    db = WorkbenchDB(tmp_path)
    db.initialize()

    rows = db.query_all("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    names = {row["name"] for row in rows}

    assert {"accounts", "tasks", "notes", "documents", "metadata"}.issubset(names)
    assert (tmp_path / "tam_workbench.db").exists()
    assert (tmp_path / "config.yaml").exists()
    assert (tmp_path / "exports").is_dir()
    assert (tmp_path / "templates").is_dir()
    assert (tmp_path / "logs").is_dir()


def test_create_get_update_account(tmp_path):
    db = WorkbenchDB(tmp_path)
    db.initialize()

    account = db.create_account(
        name="Acme",
        description="Strategic customer",
        industry="Manufacturing",
        region="NA",
        stakeholders="Admin Team",
        technical_context="SSO enabled",
        business_context="QBR next month",
        notes="Important account",
    )

    assert account["id"] == 1
    assert account["name"] == "Acme"

    fetched = db.get_account(account["id"])
    assert fetched["technical_context"] == "SSO enabled"

    updated = db.update_account(account["id"], region="EMEA", notes="Updated notes")
    assert updated["region"] == "EMEA"
    assert updated["notes"] == "Updated notes"


def test_create_task_note_document_and_export(tmp_path):
    db = WorkbenchDB(tmp_path)
    db.initialize()
    account = db.create_account(name="Acme")
    task = db.create_task(
        title="Users cannot see expected content",
        account_id=account["id"],
        type="troubleshooting",
        priority="high",
        summary="Three users affected",
        details="Admins report content visibility issue",
        next_action="Collect affected user IDs",
    )
    note = db.add_task_note(task["id"], title="Initial symptoms", body="Only three users affected", source="customer")
    doc = db.create_document(
        account_id=account["id"],
        task_id=task["id"],
        type="customer_email",
        title="Customer acknowledgement",
        body="# Thanks\nWe are investigating.",
    )

    assert task["account_id"] == account["id"]
    assert note["task_id"] == task["id"]
    assert doc["body"].startswith("# Thanks")

    export_path = db.export_document_markdown(doc["id"])
    assert export_path.exists()
    assert export_path.read_text().startswith("# Thanks")


def test_context_and_daily_snapshot(tmp_path):
    db = WorkbenchDB(tmp_path)
    db.initialize()
    account = db.create_account(name="Acme", technical_context="Uses Showpad Coach")
    task = db.create_task(title="Issue", account_id=account["id"], status="active", priority="urgent", next_action="Escalate")
    db.add_task_note(task["id"], title="Note", body="Details")
    db.create_document(account_id=account["id"], task_id=task["id"], type="internal_escalation", title="Escalation", body="Body")

    account_context = db.get_account_context(account["id"])
    task_context = db.get_task_context(task["id"])
    snapshot = db.daily_work_snapshot()

    assert account_context["account"]["name"] == "Acme"
    assert len(account_context["tasks"]) == 1
    assert task_context["task"]["title"] == "Issue"
    assert len(task_context["notes"]) == 1
    assert snapshot["urgent_tasks"][0]["next_action"] == "Escalate"


def test_contacts_are_structured_per_account_and_included_in_context(tmp_path):
    db = WorkbenchDB(tmp_path)
    db.initialize()
    account = db.create_account(name="Acme")

    contact = db.create_contact(
        account_id=account["id"],
        name="Jane Smith",
        email="jane.smith@example.com",
        role="Executive Sponsor",
        title="VP Sales Enablement",
        phone="+1 555 0100",
        notes="Prefers concise QBR summaries",
        is_primary=True,
    )

    assert contact["id"] == 1
    assert contact["account_id"] == account["id"]
    assert contact["is_primary"] == 1

    contacts = db.list_contacts(account_id=account["id"])
    assert [row["email"] for row in contacts] == ["jane.smith@example.com"]

    context = db.get_account_context(account["id"])
    assert context["contacts"][0]["role"] == "Executive Sponsor"


def test_contacts_can_be_updated_searched_and_deleted(tmp_path):
    db = WorkbenchDB(tmp_path)
    db.initialize()
    account = db.create_account(name="Acme")
    contact = db.create_contact(account_id=account["id"], name="Jane Smith", email="jane@example.com")

    updated = db.update_contact(contact["id"], email="jane.smith@example.com", role="Champion")
    assert updated["email"] == "jane.smith@example.com"
    assert updated["role"] == "Champion"

    assert db.search_contacts("champion")[0]["name"] == "Jane Smith"
    assert db.search_contacts("smith@example")[0]["role"] == "Champion"

    deleted = db.delete_contact(contact["id"])
    assert deleted == {"deleted_contact_id": contact["id"]}
    assert db.list_contacts(account_id=account["id"]) == []


def test_contact_support_level_and_showpad_owner_are_persisted(tmp_path):
    db = WorkbenchDB(tmp_path)
    db.initialize()
    account = db.create_account(name="Acme")

    owner = db.create_contact(
        account_id=account["id"],
        name="Admin One",
        support_level="supporter",
        is_showpad_owner=True,
    )
    assert owner["support_level"] == "supporter"
    assert owner["is_showpad_owner"] == 1
    assert db.search_contacts("supporter")[0]["name"] == "Admin One"

    next_owner = db.create_contact(
        account_id=account["id"],
        name="Admin Two",
        support_level="champion",
        is_showpad_owner=True,
    )
    assert next_owner["is_showpad_owner"] == 1
    assert db.get_contact(owner["id"])["is_showpad_owner"] == 0

    updated = db.update_contact(owner["id"], support_level="detractor", is_showpad_owner=True)
    assert updated["support_level"] == "detractor"
    assert updated["is_showpad_owner"] == 1
    assert db.get_contact(next_owner["id"])["is_showpad_owner"] == 0
