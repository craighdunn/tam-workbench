import importlib.util
import json
import urllib.request
from pathlib import Path
import inspect
import sys

from tam_workbench import dashboard
from tam_workbench.dashboard_data import build_dashboard_data
from tam_workbench.db import WorkbenchDB


def test_dashboard_module_can_load_as_script(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    src_dir = project_root / "src"
    dashboard_path = src_dir / "tam_workbench" / "dashboard.py"

    sys.path.insert(0, str(src_dir))
    try:
        spec = importlib.util.spec_from_file_location("dashboard_script_test", dashboard_path)
        assert spec is not None
        assert spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)

    assert hasattr(module, "render_app")


def test_kanban_style_keeps_all_six_statuses_in_one_row():
    style = dashboard._KANBAN_STYLE

    assert "display: flex;" in style
    assert "flex-wrap: nowrap;" in style
    assert "flex: 1 1 0;" in style
    assert "align-self: flex-start;" in style
    assert "margin-top: 0 !important;" in style
    assert "min-width: 0;" in style


def test_kanban_board_renders_before_focus_queue():
    source = inspect.getsource(dashboard._render_board)

    assert source.index("_render_kanban_board") < source.index("Focus queue")


def test_kanban_board_uses_native_streamlit_controls_not_react_sortable_component():
    board_source = inspect.getsource(dashboard._render_kanban_board)
    card_source = inspect.getsource(dashboard._render_kanban_task_card)
    combined_source = board_source + card_source

    assert "_sort_items" not in combined_source
    assert "streamlit-sortables" not in combined_source
    assert "selectbox" in combined_source
    assert "set_dashboard_task_status" in combined_source


def test_kanban_style_includes_account_color_rules():
    tasks = [
        {"id": 1, "title": "Warm", "status": "inbox", "account_color": "#FFE8A3"},
        {"id": 2, "title": "Plain", "status": "inbox", "account_color": ""},
        {"id": 3, "title": "Cool", "status": "active", "account_color": "#CFE8FF"},
    ]

    style = dashboard._kanban_style_for_tasks(tasks)

    assert ".sortable-container:nth-of-type(1) .sortable-item:nth-child(1)" in style
    assert "background: #FFE8A3 !important;" in style
    assert "color: #FFFFFF !important;" in style
    assert "text-shadow: 0 1px 1px rgba(0, 0, 0, 0.35);" in style
    assert ".sortable-container:nth-of-type(2) .sortable-item:nth-child(1)" in style
    assert "background: #CFE8FF !important;" in style
    assert "Plain" not in style


def test_dragdrop_status_changes_persist_to_database(tmp_path):
    db = WorkbenchDB(tmp_path)
    db.initialize()
    inbox = db.create_task(title="Drag me", status="inbox")
    active = db.create_task(title="Leave me active", status="active")
    tasks = [dict(db.get_task(inbox["id"])), dict(db.get_task(active["id"]))]

    moved = dashboard._apply_dragdrop_status_changes(
        tmp_path,
        tasks,
        [
            {"header": "Inbox (0)", "items": []},
            {
                "header": "Active (2)",
                "items": [
                    dashboard._task_card_label(tasks[0]),
                    dashboard._task_card_label(tasks[1]),
                ],
            },
        ],
    )

    assert moved == [{"title": "Drag me", "status": "active"}]
    assert db.get_task(inbox["id"])["status"] == "active"
    assert db.get_task(active["id"])["status"] == "active"


def test_dashboard_query_actions_create_task_contact_and_note(tmp_path):
    db = WorkbenchDB(tmp_path)
    db.initialize()
    account = db.create_account(name="Acme")

    task_result = dashboard._handle_dashboard_action(
        tmp_path,
        {
            "tw_action": "create_task",
            "account_id": str(account["id"]),
            "title": "Dashboard task",
            "summary": "Created from the dashboard",
            "status": "active",
            "priority": "medium",
            "due_date": "2026-07-20",
        },
    )
    contact_result = dashboard._handle_dashboard_action(
        tmp_path,
        {
            "tw_action": "create_contact",
            "account_id": str(account["id"]),
            "name": "Jane Smith",
            "title": "Executive Sponsor",
            "email": "jane@example.com",
        },
    )
    note_result = dashboard._handle_dashboard_action(
        tmp_path,
        {
            "tw_action": "create_note",
            "account_id": str(account["id"]),
            "body": "Dashboard note body",
            "source": "Dashboard",
        },
    )

    tasks = db.list_tasks(account_id=account["id"])
    contacts = db.list_contacts(account_id=account["id"])
    notes = db.list_notes(account_id=account["id"])

    assert task_result["task"]["title"] == "Dashboard task"
    assert tasks[0]["status"] == "active"
    assert tasks[0]["priority"] == "normal"
    assert contact_result["contact"]["email"] == "jane@example.com"
    assert contacts[0]["name"] == "Jane Smith"
    assert note_result["note"]["body"] == "Dashboard note body"
    assert notes[0]["source"] == "Dashboard"


def test_dashboard_query_action_moves_task_status(tmp_path):
    db = WorkbenchDB(tmp_path)
    db.initialize()
    task = db.create_task(title="Move from dashboard", status="inbox")

    dashboard._handle_dashboard_action(
        tmp_path,
        {"tw_action": "set_task_status", "task_id": str(task["id"]), "status": "blocked"},
    )

    assert db.get_task(task["id"])["status"] == "blocked"


def test_contact_payload_separates_clients_from_showpad_account_team(tmp_path):
    db = WorkbenchDB(tmp_path)
    db.initialize()
    account = db.create_account(name="Acme")
    db.create_contact(account_id=account["id"], name="Client Admin", email="admin@example.com", role="Admin")
    db.create_contact(account_id=account["id"], name="Showpad TAM", email="tam@showpad.com", role="TAM")

    payload = dashboard._build_design_payload(
        {
            "summary": {},
            "accounts": db.list_accounts(),
            "tasks": [],
            "contacts": db.list_contacts(),
            "notes": [],
            "tasks_by_account": [
                {
                    "account_id": account["id"],
                    "account_name": account["name"],
                    "open_task_count": 0,
                    "blocked_task_count": 0,
                    "contact_count": 2,
                }
            ],
        }
    )

    contacts = payload["contacts"][str(account["id"])]
    assert contacts[0]["name"] == "Client Admin"
    assert contacts[0]["isShowpadTeam"] is False
    assert contacts[1]["name"] == "Showpad TAM"
    assert contacts[1]["isShowpadTeam"] is True


def test_dashboard_query_action_creates_showpad_contact_from_dropdown(tmp_path):
    db = WorkbenchDB(tmp_path)
    db.initialize()
    account = db.create_account(name="Acme")

    result = dashboard._handle_dashboard_action(
        tmp_path,
        {
            "tw_action": "create_contact",
            "account_id": str(account["id"]),
            "name": "Showpad TAM",
            "email": "tam@example.com",
            "contact_kind": "showpad",
        },
    )

    contact = db.list_contacts(account_id=account["id"])[0]
    assert result["contact"]["name"] == "Showpad TAM"
    assert contact["role"] == "Showpad Contact"
    assert dashboard._is_showpad_team_contact(contact) is True


def test_dashboard_action_server_saves_without_query_param_navigation(tmp_path):
    db = WorkbenchDB(tmp_path)
    db.initialize()
    account = db.create_account(name="Acme")
    bridge = dashboard._start_dashboard_action_server(str(tmp_path))
    payload = json.dumps(
        {
            "token": bridge["token"],
            "action": "create_task",
            "fields": {"account_id": account["id"], "title": "Async task", "status": "active"},
        }
    ).encode("utf-8")

    request = urllib.request.Request(
        bridge["url"],
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        body = json.loads(response.read().decode("utf-8"))

    assert body["ok"] is True
    assert db.list_tasks(account_id=account["id"])[0]["title"] == "Async task"


def test_imported_dashboard_uses_editor_panels_and_tall_kanban_columns(tmp_path):
    db = WorkbenchDB(tmp_path)
    db.initialize()
    account = db.create_account(name="Acme")
    db.create_task(account_id=account["id"], title="Review", status="active", priority="high", summary="Longer task details")
    db.create_contact(account_id=account["id"], name="Alex Client", email="alex@example.com", phone="555-0100", notes="Decision maker")
    db.create_note(account_id=account["id"], body="A long note body", source="Dashboard")

    html = dashboard._design_html(dashboard._build_design_payload(build_dashboard_data(tmp_path)))

    assert "height:calc(100vh - 226px)" in html
    assert "Edit Task" in html
    assert "edit-task-desc" in html
    assert "edit-task-priority" in html
    assert "Edit Contact" in html
    assert "edit-contact-phone" in html
    assert "edit-contact-notes" in html
    assert "Edit Note" in html
    assert "edit-note-body" in html
    assert "prompt('Task title'" not in html
    assert "prompt('Contact name'" not in html
    assert "prompt('Note body'" not in html


def test_dashboard_query_actions_update_and_archive_records(tmp_path):
    db = WorkbenchDB(tmp_path)
    db.initialize()
    account = db.create_account(name="Acme")
    task = db.create_task(title="Old task", account_id=account["id"], status="active")
    contact = db.create_contact(account_id=account["id"], name="Old Contact")
    note = db.create_note(account_id=account["id"], body="Old note")

    dashboard._handle_dashboard_action(tmp_path, {"tw_action": "update_account", "account_id": str(account["id"]), "name": "New Acme"})
    dashboard._handle_dashboard_action(tmp_path, {"tw_action": "update_task", "task_id": str(task["id"]), "title": "New task"})
    dashboard._handle_dashboard_action(tmp_path, {"tw_action": "update_contact", "contact_id": str(contact["id"]), "name": "New Contact", "contact_kind": "client"})
    dashboard._handle_dashboard_action(tmp_path, {"tw_action": "update_note", "note_id": str(note["id"]), "body": "New note"})

    assert db.get_account(account["id"])["name"] == "New Acme"
    assert db.get_task(task["id"])["title"] == "New task"
    assert db.get_contact(contact["id"])["name"] == "New Contact"
    assert db.get_note(note["id"])["body"] == "New note"

    dashboard._handle_dashboard_action(tmp_path, {"tw_action": "archive_contact", "contact_id": str(contact["id"])} )
    dashboard._handle_dashboard_action(tmp_path, {"tw_action": "archive_note", "note_id": str(note["id"])} )
    dashboard._handle_dashboard_action(tmp_path, {"tw_action": "archive_task", "task_id": str(task["id"])} )

    assert db.list_contacts(account_id=account["id"]) == []
    assert db.list_notes(account_id=account["id"]) == []
    assert db.list_tasks(account_id=account["id"]) == []
    assert db.get_contact(contact["id"])["archived_at"]
    assert db.get_note(note["id"])["archived_at"]
    assert db.get_task(task["id"])["status"] == "archived"


def test_contacts_tab_renders_clients_before_showpad_account_team():
    html = dashboard._design_html(
        {
            "summary": {"account_count": 1, "contact_count": 2},
            "accounts": [
                {
                    "id": 1,
                    "name": "Acme",
                    "region": "NA",
                    "industry": "Software",
                    "health": "healthy",
                    "openTasks": 0,
                    "blocked": 0,
                    "contacts": 2,
                    "nextAction": "",
                }
            ],
            "kanban": {"1": {"inbox": [], "active": [], "waiting": [], "blocked": [], "done": []}},
            "contacts": {"1": []},
            "notes": {"1": []},
            "selectedId": 1,
        }
    )

    assert "Clients" in html
    assert "Showpad Account Team" in html
    assert "Task Health" in html
    assert "Client Contact" in html
    assert "Showpad Contact" in html
    assert "data-edit-account" in html
    assert "data-archive-contact" in html
    assert html.index("Clients") < html.index("Showpad Account Team")


def test_sidebar_accounts_render_as_single_alphabetical_list():
    html = dashboard._design_html(
        {
            "summary": {"account_count": 2, "contact_count": 0},
            "accounts": [
                {"id": 1, "name": "Beta Co", "region": "EMEA", "industry": "Software", "health": "healthy", "openTasks": 0, "blocked": 0, "contacts": 0, "nextAction": ""},
                {"id": 2, "name": "Alpha Co", "region": "North America", "industry": "Software", "health": "healthy", "openTasks": 0, "blocked": 0, "contacts": 0, "nextAction": ""},
            ],
            "kanban": {"1": {"inbox": [], "active": [], "waiting": [], "blocked": [], "done": []}},
            "contacts": {"1": []},
            "notes": {"1": []},
            "selectedId": 1,
        }
    )

    assert "groupedAccounts" not in html
    assert "visibleAccounts().map(a => renderSidebarAccount(a))" in html
    assert "localeCompare" in html
