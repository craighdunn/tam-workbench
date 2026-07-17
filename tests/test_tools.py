from tam_workbench.tools import WorkbenchTools


def test_tool_handlers_return_clean_json_payloads(tmp_path):
    tools = WorkbenchTools(tmp_path)
    tools.initialize()

    created = tools.create_account({"name": "Acme", "region": "NA"})
    assert created["success"] is True
    assert created["account"]["name"] == "Acme"

    task = tools.create_task({"title": "Follow up", "account_id": created["account"]["id"], "type": "general"})
    assert task["success"] is True
    assert task["task"]["account_id"] == created["account"]["id"]

    note = tools.add_task_note({"task_id": task["task"]["id"], "title": "Update", "body": "Waiting on customer"})
    assert note["success"] is True

    snapshot = tools.daily_work_snapshot({})
    assert snapshot["success"] is True
    assert snapshot["snapshot"]["open_task_count"] == 1


def test_search_tools_find_accounts_tasks_and_notes(tmp_path):
    tools = WorkbenchTools(tmp_path)
    tools.initialize()
    account = tools.create_account({"name": "Acme", "technical_context": "SSO and SCIM"})["account"]
    task = tools.create_task({"title": "SCIM research", "account_id": account["id"], "type": "research", "details": "Investigate provisioning"})["task"]
    tools.create_note({"account_id": account["id"], "task_id": task["id"], "title": "Source", "body": "Provisioning docs reviewed"})

    assert tools.search_accounts({"query": "SCIM"})["accounts"][0]["name"] == "Acme"
    assert tools.search_tasks({"query": "provisioning"})["tasks"][0]["title"] == "SCIM research"
    assert tools.search_notes({"query": "docs"})["notes"][0]["title"] == "Source"


def test_contact_tool_handlers_manage_account_contacts(tmp_path):
    tools = WorkbenchTools(tmp_path)
    tools.initialize()
    account = tools.create_account({"name": "Acme"})["account"]

    created = tools.create_contact({
        "account_id": account["id"],
        "name": "Jane Smith",
        "email": "jane.smith@example.com",
        "role": "Executive Sponsor",
        "is_primary": True,
    })
    assert created["success"] is True
    assert created["contact"]["email"] == "jane.smith@example.com"

    listed = tools.list_contacts({"account_id": account["id"]})
    assert listed["contacts"][0]["name"] == "Jane Smith"

    updated = tools.update_contact({"contact_id": created["contact"]["id"], "role": "Champion"})
    assert updated["contact"]["role"] == "Champion"

    searched = tools.search_contacts({"query": "champion"})
    assert searched["contacts"][0]["email"] == "jane.smith@example.com"

    deleted = tools.delete_contact({"contact_id": created["contact"]["id"]})
    assert deleted == {"success": True, "deleted": {"deleted_contact_id": created["contact"]["id"]}}
