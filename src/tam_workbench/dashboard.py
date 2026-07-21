from __future__ import annotations

import json
import re
import secrets
import sys
import threading
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import quote

import streamlit as st

try:
    from .dashboard_data import (
        KANBAN_STATUSES,
        build_dashboard_data,
        delete_dashboard_task,
        set_dashboard_account_color,
        set_dashboard_task_status,
    )
    from .db import WorkbenchDB, default_data_dir
except ImportError:  # pragma: no cover - used when Streamlit loads this file as a script
    from tam_workbench.dashboard_data import (
        KANBAN_STATUSES,
        build_dashboard_data,
        delete_dashboard_task,
        set_dashboard_account_color,
        set_dashboard_task_status,
    )
    from tam_workbench.db import WorkbenchDB, default_data_dir


DESIGN_STATUSES = ["inbox", "active", "waiting", "blocked", "done"]


@st.cache_resource(show_spinner=False)
def _start_dashboard_action_server(data_dir: str) -> dict[str, str]:
    """Start a tiny localhost API so iframe saves do not open tabs or reload the dashboard."""
    token = secrets.token_urlsafe(24)

    class DashboardActionHandler(BaseHTTPRequestHandler):
        def _send(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "content-type")
            self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self) -> None:  # noqa: N802 - stdlib handler hook
            self._send(200, {"ok": True})

        def do_POST(self) -> None:  # noqa: N802 - stdlib handler hook
            try:
                content_length = int(self.headers.get("Content-Length") or "0")
                payload = json.loads(self.rfile.read(content_length).decode("utf-8") or "{}")
                if payload.get("token") != token:
                    self._send(403, {"ok": False, "error": "invalid token"})
                    return
                fields = payload.get("fields") or {}
                params = {"tw_action": str(payload.get("action") or "")}
                params.update({str(key): str(value) for key, value in fields.items()})
                result = _handle_dashboard_action(data_dir, params)
                self._send(200, {"ok": True, "result": result})
            except Exception as exc:  # pragma: no cover - exercised by browser tests/smokes
                self._send(400, {"ok": False, "error": str(exc)})

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - stdlib signature
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), DashboardActionHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return {"url": f"http://127.0.0.1:{server.server_port}", "token": token}


def _param_value(params: dict[str, Any], key: str, default: str = "") -> str:
    value = params.get(key, default)
    if isinstance(value, list):
        value = value[0] if value else default
    return str(value or default).strip()


def _handle_dashboard_action(data_dir: str | Path, params: dict[str, Any]) -> dict[str, Any] | None:
    """Persist simple dashboard iframe actions encoded as Streamlit query params."""
    action = _param_value(params, "tw_action")
    if not action:
        return None

    db = WorkbenchDB(data_dir)
    db.initialize()

    if action == "create_task":
        account_id = _dashboard_account_id(params)
        title = _param_value(params, "title")
        if not title:
            raise ValueError("Task title is required")
        status = _param_value(params, "status", "inbox")
        if status not in DESIGN_STATUSES:
            status = "inbox"
        priority = _param_value(params, "priority", "normal")
        if priority == "medium":
            priority = "normal"
        task = db.create_task(
            title=title,
            account_id=account_id,
            type="general",
            status=status,
            priority=priority,
            summary=_param_value(params, "summary"),
            details=_param_value(params, "details"),
            next_action=_param_value(params, "next_action"),
            due_date=_param_value(params, "due_date") or None,
        )
        return {"message": f"Saved task: {task['title']}", "task": task}

    if action == "create_contact":
        account_id = _dashboard_account_id(params)
        name = _param_value(params, "name")
        if not name:
            raise ValueError("Contact name is required")
        contact_kind = _param_value(params, "contact_kind", "client")
        role = _param_value(params, "role")
        if contact_kind == "showpad" and "showpad" not in role.lower():
            role = role or "Showpad Contact"
        elif contact_kind == "client" and not role:
            role = "Client Contact"
        contact = db.create_contact(
            account_id=account_id,
            name=name,
            email=_param_value(params, "email"),
            title=_param_value(params, "title"),
            role=role,
            phone=_param_value(params, "phone"),
            notes=_param_value(params, "notes"),
            is_primary=False,
        )
        return {"message": f"Saved contact: {contact['name']}", "contact": contact}

    if action == "update_account":
        account_id = _dashboard_account_id(params)
        account = db.update_account(
            account_id,
            name=_param_value(params, "name") or None,
            industry=_param_value(params, "industry") or None,
            region=_param_value(params, "region") or None,
        )
        return {"message": f"Updated account: {account['name']}", "account": account}

    if action == "archive_account":
        account_id = _dashboard_account_id(params)
        account = db.archive_account(account_id)
        return {"message": f"Archived account: {account['name']}", "account": account}

    if action == "update_task":
        task_id = int(_param_value(params, "task_id"))
        priority = _param_value(params, "priority")
        if priority == "medium":
            priority = "normal"
        task = db.update_task(
            task_id,
            title=_param_value(params, "title") or None,
            summary=_param_value(params, "summary") or None,
            priority=priority or None,
            due_date=_param_value(params, "due_date") or None,
        )
        return {"message": f"Updated task: {task['title']}", "task": task}

    if action == "archive_task":
        task_id = int(_param_value(params, "task_id"))
        task = db.archive_task(task_id)
        return {"message": f"Archived task: {task['title']}", "task": task}

    if action == "update_contact":
        contact_id = int(_param_value(params, "contact_id"))
        contact_kind = _param_value(params, "contact_kind")
        role = _param_value(params, "role")
        if contact_kind == "showpad" and "showpad" not in role.lower():
            role = role or "Showpad Contact"
        elif contact_kind == "client" and not role:
            role = "Client Contact"
        contact = db.update_contact(
            contact_id,
            name=_param_value(params, "name") or None,
            title=_param_value(params, "title") or None,
            email=_param_value(params, "email") or None,
            phone=_param_value(params, "phone") or None,
            notes=_param_value(params, "notes") or None,
            role=role or None,
        )
        return {"message": f"Updated contact: {contact['name']}", "contact": contact}

    if action == "archive_contact":
        contact_id = int(_param_value(params, "contact_id"))
        contact = db.archive_contact(contact_id)
        return {"message": f"Archived contact: {contact['name']}", "contact": contact}

    if action == "update_note":
        note_id = int(_param_value(params, "note_id"))
        note = db.update_note(
            note_id,
            body=_param_value(params, "body") or None,
            title=_param_value(params, "title") or None,
            source=_param_value(params, "source") or None,
        )
        return {"message": "Updated note", "note": note}

    if action == "archive_note":
        note_id = int(_param_value(params, "note_id"))
        note = db.archive_note(note_id)
        return {"message": "Archived note", "note": note}

    if action == "create_note":
        account_id = _dashboard_account_id(params)
        body = _param_value(params, "body")
        if not body:
            raise ValueError("Note body is required")
        note = db.create_note(
            account_id=account_id,
            title=_param_value(params, "title", "Dashboard note"),
            body=body,
            source=_param_value(params, "source", "Dashboard"),
        )
        return {"message": "Saved note", "note": note}

    if action == "set_task_status":
        task_id = int(_param_value(params, "task_id"))
        status = _param_value(params, "status")
        if status not in DESIGN_STATUSES:
            raise ValueError(f"invalid status: {status}")
        task = db.set_task_status(task_id, status)
        return {"message": f"Moved task to {status}", "task": task}

    raise ValueError(f"Unknown dashboard action: {action}")


def _dashboard_account_id(params: dict[str, Any]) -> int:
    raw = _param_value(params, "account_id")
    if not raw or raw == "__empty__":
        raise ValueError("Create an account in Claude Desktop before adding dashboard items")
    return int(raw)


def render_app(data_dir: str | Path | None = None) -> None:
    """Render the TAM Account Dashboard design handoff as the dashboard shell."""
    st.set_page_config(page_title="TAM Workbench", page_icon="▦", layout="wide", initial_sidebar_state="collapsed")
    requested_dir = data_dir or st.query_params.get("data_dir") or str(default_data_dir())
    action_result = _handle_dashboard_action(requested_dir, dict(st.query_params))
    if action_result:
        st.query_params.clear()
        message = action_result.get("message") or "Dashboard update saved."
        if hasattr(st, "toast"):
            st.toast(message)
    data = build_dashboard_data(requested_dir)
    payload = _build_design_payload(data)
    save_bridge = _start_dashboard_action_server(str(Path(requested_dir).expanduser()))
    payload["saveEndpoint"] = save_bridge["url"]
    payload["saveToken"] = save_bridge["token"]

    st.markdown(
        """
        <style>
        [data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stSidebar"], footer { display: none !important; }
        .block-container { padding: 0 !important; max-width: 100% !important; }
        html, body, [data-testid="stAppViewContainer"], [data-testid="stApp"] { background: #0C0E15 !important; overflow: hidden !important; }
        iframe { display: block; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    html = _design_html(payload)
    st.iframe(f"data:text/html;charset=utf-8,{quote(html)}", height=900)


def _build_design_payload(data: dict[str, Any]) -> dict[str, Any]:
    accounts_by_id = {int(account["id"]): account for account in data.get("accounts", [])}
    account_rows = data.get("tasks_by_account", [])
    tasks = data.get("tasks", [])
    contacts = data.get("contacts", [])
    notes = data.get("notes", [])

    task_groups: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for task in tasks:
        account_id = task.get("account_id")
        if account_id is None:
            continue
        account_key = str(account_id)
        status = task.get("status") or "inbox"
        if status == "archived":
            continue
        if status not in DESIGN_STATUSES:
            status = "inbox"
        task_groups.setdefault(account_key, {status_name: [] for status_name in DESIGN_STATUSES})[status].append(
            {
                "id": str(task["id"]),
                "title": task.get("title") or "Untitled task",
                "desc": _first_nonempty(task.get("summary"), task.get("next_action"), task.get("details")),
                "summary": task.get("summary") or "",
                "due": task.get("due_date") or "",
                "priority": _design_priority(task.get("priority") or "normal"),
            }
        )

    contact_groups: dict[str, list[dict[str, Any]]] = {}
    for contact in contacts:
        account_id = contact.get("account_id")
        if account_id is None:
            continue
        influence = _contact_influence(contact)
        contact_groups.setdefault(str(account_id), []).append(
            {
                "id": str(contact.get("id") or len(contact_groups.get(str(account_id), []))),
                "name": contact.get("name") or "Unnamed contact",
                "title": contact.get("title") or contact.get("role") or "Contact",
                "role": contact.get("role") or "",
                "email": contact.get("email") or "",
                "phone": contact.get("phone") or "",
                "notes": contact.get("notes") or "",
                "influence": influence,
                "isPrimary": bool(contact.get("is_primary")),
                "isShowpadTeam": _is_showpad_team_contact(contact),
            }
        )

    note_groups: dict[str, list[dict[str, Any]]] = {}
    task_to_account = {task.get("id"): task.get("account_id") for task in tasks}
    for note in notes:
        account_id = note.get("account_id") or task_to_account.get(note.get("task_id"))
        if account_id is None:
            continue
        note_groups.setdefault(str(account_id), []).append(
            {
                "id": str(note.get("id")),
                "ts": _format_note_date(note.get("updated_at") or note.get("created_at") or ""),
                "author": note.get("source") or "Craig",
                "text": _first_nonempty(note.get("body"), note.get("title"), "No note body captured."),
                "body": note.get("body") or "",
            }
        )

    accounts: list[dict[str, Any]] = []
    for row in account_rows:
        account_id = int(row["account_id"])
        account = accounts_by_id.get(account_id, {})
        blocked = int(row.get("blocked_task_count") or 0)
        open_tasks = int(row.get("open_task_count") or 0)
        contacts_count = int(row.get("contact_count") or len(contact_groups.get(str(account_id), [])))
        accounts.append(
            {
                "id": account_id,
                "name": row.get("account_name") or account.get("name") or "Unnamed account",
                "region": account.get("region") or row.get("region") or "Other",
                "industry": account.get("industry") or row.get("industry") or "No industry captured",
                "health": "at-risk" if blocked else "healthy",
                "color": account.get("account_color") or None,
                "openTasks": open_tasks,
                "blocked": blocked,
                "contacts": contacts_count,
                "nextAction": row.get("next_action") or _next_action_for_account(account_id, tasks),
            }
        )
        task_groups.setdefault(str(account_id), {status_name: [] for status_name in DESIGN_STATUSES})
        contact_groups.setdefault(str(account_id), [])
        note_groups.setdefault(str(account_id), [])

    if not accounts:
        accounts.append(
            {
                "id": "__empty__",
                "name": "No accounts yet",
                "region": "Other",
                "industry": "Create your first account from Claude Desktop",
                "health": "healthy",
                "color": None,
                "openTasks": 0,
                "blocked": 0,
                "contacts": 0,
                "nextAction": "Ask Claude to create your first TAM Workbench account",
            }
        )
        task_groups["__empty__"] = {column: [] for column in ["inbox", "active", "waiting", "blocked", "done"]}
        contact_groups["__empty__"] = []
        note_groups["__empty__"] = []

    spectrum = next((account for account in accounts if str(account["name"]).lower() == "spectrum"), None)
    selected_id = spectrum["id"] if spectrum else accounts[0]["id"]
    return {
        "summary": data.get("summary", {}),
        "accounts": accounts,
        "kanban": task_groups,
        "contacts": contact_groups,
        "notes": note_groups,
        "selectedId": selected_id,
    }


def _design_priority(priority: str) -> str:
    if priority in {"urgent", "high"}:
        return "high"
    if priority == "low":
        return "low"
    return "medium"


def _contact_influence(contact: dict[str, Any]) -> str:
    notes = f"{contact.get('role') or ''} {contact.get('title') or ''} {contact.get('notes') or ''}".lower()
    if contact.get("is_primary") or "champion" in notes or "sponsor" in notes:
        return "champion"
    if "detractor" in notes or "blocker" in notes:
        return "detractor"
    return "neutral"


def _is_showpad_team_contact(contact: dict[str, Any]) -> bool:
    """Identify internal Showpad account-team contacts for dashboard grouping."""
    haystack = " ".join(
        str(contact.get(field) or "")
        for field in ["email", "role", "title", "notes"]
    ).lower()
    return any(
        marker in haystack
        for marker in ["@showpad.com", "showpad", "account team", "tam", "csm", "customer success"]
    )


def _first_nonempty(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _next_action_for_account(account_id: int, tasks: list[dict[str, Any]]) -> str:
    for task in tasks:
        if task.get("account_id") == account_id and (task.get("next_action") or "").strip():
            return str(task["next_action"]).strip()
    return ""


def _format_note_date(value: str) -> str:
    if not value:
        return ""
    return value[:10]


def _json_for_html(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False).replace("</", "<\\/")


def _design_html(payload: dict[str, Any]) -> str:
    payload_json = _json_for_html(payload)
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700&display=swap" rel="stylesheet">
<style>
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
html, body {{ height: 100%; overflow: hidden; background: #0C0E15; }}
body {{ font-family: 'DM Sans', system-ui, sans-serif; }}
::-webkit-scrollbar {{ width: 4px; height: 4px; }}
::-webkit-scrollbar-track {{ background: transparent; }}
::-webkit-scrollbar-thumb {{ background: rgba(255,255,255,0.07); border-radius: 2px; }}
.sb-acct {{ transition: background 0.1s; }}
.sb-acct:hover {{ background: rgba(255,255,255,0.035) !important; }}
.k-card {{ transition: border-color 0.1s; user-select: none; }}
.k-card:hover {{ border-color: rgba(99,130,240,0.35) !important; }}
.k-card:active {{ opacity: 0.7; }}
.tab-btn {{ transition: color 0.12s, border-color 0.12s; }}
.con-card {{ transition: border-color 0.1s; }}
.con-card:hover {{ border-color: rgba(99,130,240,0.3) !important; }}
.col-add-btn:hover {{ opacity: 1 !important; color: #6382F0 !important; }}
.form-input {{ background: #090D16; border: 1px solid #1E2A3A; border-radius: 7px; padding: 8px 10px; font-size: 12.5px; color: #C4CFDF; outline: none; font-family: inherit; width: 100%; }}
.form-input::placeholder {{ color: #354258; }}
.editor-primary {{ font-size: 13px; font-weight: 700; background: #6382F0; color: #fff; border: none; border-radius: 9px; padding: 9px 16px; cursor: pointer; font-family: inherit; }}
.editor-secondary {{ font-size: 13px; font-weight: 600; background: rgba(255,255,255,0.05); color: #8090A8; border: 1px solid #1E2A3A; border-radius: 9px; padding: 9px 14px; cursor: pointer; font-family: inherit; }}
.editor-primary:hover, .editor-secondary:hover {{ filter: brightness(1.08); }}
a {{ color: #6382F0; text-decoration: none; }}
a:hover {{ opacity: 0.8; }}
button, input, textarea {{ font-family: inherit; }}
</style>
</head>
<body>
<div id="app"></div>
<script>
const BOOT = {payload_json};
const STATUSES = [
  {{ id: 'inbox', label: 'Inbox', dot: '#64748B', alertOn: false }},
  {{ id: 'active', label: 'Active', dot: '#6382F0', alertOn: false }},
  {{ id: 'waiting', label: 'Waiting', dot: '#EAB308', alertOn: false }},
  {{ id: 'blocked', label: 'Blocked', dot: '#EF4444', alertOn: true }},
  {{ id: 'done', label: 'Done', dot: '#22C55E', alertOn: false }},
];
const state = {{
  selectedId: BOOT.selectedId,
  accounts: JSON.parse(JSON.stringify(BOOT.accounts || [])),
  search: '',
  activeTab: 'tasks',
  kanban: JSON.parse(JSON.stringify(BOOT.kanban || {{}})),
  contacts: JSON.parse(JSON.stringify(BOOT.contacts || {{}})),
  notes: JSON.parse(JSON.stringify(BOOT.notes || {{}})),
  expandedNotes: {{}},
  drag: null,
  dropTarget: null,
  addingToCol: null,
  showAddContact: false,
  showAddNote: false,
  editor: null,
}};
function esc(v) {{ return String(v ?? '').replace(/[&<>\"']/g, ch => ({{'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}}[ch])); }}
function getAccount() {{ return (state.accounts || []).find(a => String(a.id) === String(state.selectedId)) || (state.accounts || [])[0] || {{}}; }}
function getHealth(h) {{
  if (h === 'healthy') return {{ dot: '#22C55E', text: '#4ADE80', bg: 'rgba(34,197,94,0.09)', label: 'Healthy' }};
  if (h === 'at-risk') return {{ dot: '#EAB308', text: '#FCD34D', bg: 'rgba(234,179,8,0.09)', label: 'At Risk' }};
  return {{ dot: '#EF4444', text: '#F87171', bg: 'rgba(239,68,68,0.09)', label: 'Critical' }};
}}
function getPri(p) {{
  if (p === 'high') return {{ color: '#F87171', bg: 'rgba(239,68,68,0.12)' }};
  if (p === 'medium') return {{ color: '#FCD34D', bg: 'rgba(234,179,8,0.09)' }};
  return {{ color: '#516070', bg: 'rgba(255,255,255,0.04)' }};
}}
function getInf(i) {{
  if (i === 'champion') return {{ color: '#4ADE80', bg: 'rgba(34,197,94,0.1)', label: 'Champion' }};
  if (i === 'detractor') return {{ color: '#F87171', bg: 'rgba(239,68,68,0.1)', label: 'Detractor' }};
  return {{ color: '#6B7A90', bg: 'rgba(255,255,255,0.05)', label: 'Neutral' }};
}}
function styleObj(o) {{ return Object.entries(o).map(([k,v]) => k.replace(/[A-Z]/g, m => '-' + m.toLowerCase()) + ':' + v).join(';'); }}
function accountTaskLabel(a) {{ return a.openTasks === 1 ? '1 open task' : `${{a.openTasks}} open tasks`; }}
function visibleAccounts() {{
  const q = state.search.trim().toLowerCase();
  return (state.accounts || [])
    .filter(a => !q || a.name.toLowerCase().includes(q))
    .slice()
    .sort((a, b) => (a.name || '').localeCompare(b.name || '', undefined, {{ sensitivity: 'base' }}));
}}
function kanbanFor(id) {{
  const key = String(id);
  if (!state.kanban[key]) state.kanban[key] = {{ inbox: [], active: [], waiting: [], blocked: [], done: [] }};
  return state.kanban[key];
}}
function contactsFor(id) {{ return state.contacts[String(id)] || []; }}
function notesFor(id) {{ return state.notes[String(id)] || []; }}
function persistDashboardAction(action, fields) {{
  if (!BOOT.saveEndpoint || !BOOT.saveToken) {{
    alert('Dashboard save bridge is not ready yet. Please refresh and try again.');
    return;
  }}
  fetch(BOOT.saveEndpoint, {{
    method: 'POST',
    headers: {{ 'Content-Type': 'application/json' }},
    body: JSON.stringify({{ token: BOOT.saveToken, action, fields: fields || {{}} }})
  }})
    .then(async response => {{
      const payload = await response.json().catch(() => ({{ ok: false, error: response.statusText }}));
      if (!response.ok || !payload.ok) throw new Error(payload.error || 'Save failed');
      showSaveStatus('Saved');
      return payload;
    }})
    .catch(err => {{
      console.error('Dashboard save failed', err);
      alert('Could not save this dashboard change: ' + err.message);
      showSaveStatus('Save failed');
    }});
}}
function showSaveStatus(text) {{
  let el = document.getElementById('save-status');
  if (!el) {{
    el = document.createElement('div'); el.id = 'save-status';
    el.style.cssText = 'position:fixed;right:18px;bottom:16px;z-index:9999;background:#101727;border:1px solid #26344d;color:#9fb3d9;border-radius:8px;padding:8px 11px;font-size:12px;box-shadow:0 8px 24px rgba(0,0,0,.25)';
    document.body.appendChild(el);
  }}
  el.textContent = text;
  clearTimeout(el._timer);
  el._timer = setTimeout(() => el.remove(), 1800);
}}
function openCount(kan) {{ return ['inbox','active','waiting','blocked'].reduce((s,k) => s + ((kan[k] || []).length), 0); }}
function renderSidebar() {{
  return `<aside style="width: 256px; flex-shrink: 0; background: #07090F; border-right: 1px solid #161B28; display: flex; flex-direction: column; overflow: hidden;">
    <div style="padding: 16px 14px 13px; border-bottom: 1px solid #161B28; flex-shrink: 0;">
      <div style="display: flex; align-items: center; gap: 9px; margin-bottom: 13px;">
        <div style="width: 27px; height: 27px; background: linear-gradient(135deg, #6382F0 0%, #9B59F5 100%); border-radius: 7px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; color:white; font-weight:800; font-size:13px;">▦</div>
        <div><div style="font-size: 13px; font-weight: 600; color: #DCE4F0; letter-spacing: -0.015em; line-height: 1.2;">TAM Workbench</div>
        <div style="font-size: 10.5px; color: #354258; line-height: 1.3;">${{BOOT.summary.account_count || 0}} accounts · ${{BOOT.summary.contact_count || 0}} contacts</div></div>
      </div>
      <div style="position: relative;">
        <svg style="position: absolute; left: 8px; top: 50%; transform: translateY(-50%); pointer-events: none;" width="13" height="13" viewBox="0 0 14 14" fill="none"><circle cx="6" cy="6" r="4" stroke="#354258" stroke-width="1.5"/><path d="M9.5 9.5L12 12" stroke="#354258" stroke-width="1.5" stroke-linecap="round"/></svg>
        <input id="search" type="text" placeholder="Search accounts…" value="${{esc(state.search)}}" style="width: 100%; background: #0E1018; border: 1px solid #1C2232; border-radius: 7px; padding: 7px 8px 7px 27px; font-size: 12.5px; color: #C4CFDF; outline: none; font-family: inherit;" />
      </div>
    </div>
    <div style="flex: 1; overflow-y: auto; padding: 6px 0;">${{visibleAccounts().map(a => renderSidebarAccount(a)).join('')}}</div>
    <div style="padding: 10px 13px; border-top: 1px solid #161B28; display: flex; align-items: center; gap: 9px; flex-shrink: 0;">
      <div style="width: 28px; height: 28px; background: linear-gradient(135deg, #6382F0, #9B59F5); border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 700; color: white; flex-shrink: 0;">CD</div>
      <div style="flex: 1; min-width: 0;"><div style="font-size: 12.5px; font-weight: 500; color: #C4CFDF; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">Craig Dunn</div><div style="font-size: 10.5px; color: #354258;">Technical Account Manager</div></div>
    </div>
  </aside>`;
}}
function renderSidebarAccount(a) {{
  const ah = getHealth(a.health); const isSel = String(a.id) === String(state.selectedId);
  return `<div class="sb-acct" data-account="${{a.id}}" style="display:flex;align-items:flex-start;gap:9px;padding:7px 13px 7px 11px;cursor:pointer;user-select:none;background:${{isSel ? 'rgba(99,130,240,0.07)' : 'transparent'}};border-left:2px solid ${{isSel ? '#6382F0' : 'transparent'}};font-weight:${{isSel ? '500' : '400'}};">
    <div style="width:6px;height:6px;border-radius:50%;background:${{ah.dot}};flex-shrink:0;margin-top:4px;"></div>
    <div style="flex:1;min-width:0;"><div style="font-size:13px;color:#C4CFDF;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${{esc(a.name)}}</div>${{a.openTasks > 0 ? `<div style="font-size:10.5px;color:#354258;margin-top:1px;">${{accountTaskLabel(a)}}</div>` : ''}}</div>
    ${{a.blocked > 0 ? `<span style="font-size:9.5px;font-weight:600;background:rgba(239,68,68,0.14);color:#F87171;border-radius:4px;padding:1px 5px;flex-shrink:0;">${{a.blocked}} blocked</span>` : ''}}
  </div>`;
}}
function renderTopBar(acct) {{
  return `<div style="height: 42px; flex-shrink: 0; background: #07090F; border-bottom: 1px solid #161B28; padding: 0 22px; display: flex; align-items: center; justify-content: space-between;">
    <div style="display:flex;align-items:center;gap:5px;font-size:12.5px;"><span style="color:#354258;">Accounts</span><span style="color:#2A3444;">›</span><span style="color:#C4CFDF;font-weight:500;">${{esc(acct.name || '')}}</span></div>
    <div style="display:flex;gap:14px;align-items:center;">${{miniStat(BOOT.summary.open_task_count || 0, 'open')}}<div style="width:1px;height:20px;background:#161B28;"></div>${{miniStat(BOOT.summary.blocked_count || (BOOT.accounts || []).reduce((s,a)=>s+a.blocked,0), 'blocked', '#F87171')}}<div style="width:1px;height:20px;background:#161B28;"></div>${{miniStat(BOOT.summary.account_count || 0, 'accounts')}}</div>
  </div>`;
}}
function miniStat(n, label, color='#C4CFDF') {{ return `<div style="text-align:center;"><div style="font-size:13px;font-weight:600;color:${{color}};line-height:1;">${{n}}</div><div style="font-size:9.5px;color:#354258;margin-top:1px;">${{label}}</div></div>`; }}
function renderHeader(acct, kan) {{
  const hi = getHealth(acct.health); const accent = acct.color || '#6382F0'; const oc = openCount(kan); const bc = (kan.blocked || []).length; const cc = contactsFor(acct.id).length;
  return `<div style="flex-shrink:0;background:#0A0C13;border-bottom:1px solid #161B28;padding:16px 22px;"><div style="display:flex;align-items:flex-start;gap:14px;">
    <div style="width:3px;background:${{accent}};border-radius:2px;align-self:stretch;margin-top:2px;flex-shrink:0;"></div>
    <div style="flex:1;min-width:0;"><div style="display:flex;align-items:center;gap:10px;margin-bottom:4px;flex-wrap:wrap;"><h1 style="font-size:21px;font-weight:700;color:#E8EDF8;letter-spacing:-0.03em;line-height:1.2;">${{esc(acct.name)}}</h1><div title="Task Health" style="display:inline-flex;align-items:center;gap:5px;background:${{hi.bg}};border-radius:20px;padding:3px 9px 3px 6px;flex-shrink:0;"><div style="width:6px;height:6px;border-radius:50%;background:${{hi.dot}};"></div><span style="font-size:10px;font-weight:700;color:#516070;text-transform:uppercase;letter-spacing:0.06em;">Task Health</span><span style="font-size:11.5px;font-weight:600;color:${{hi.text}};">${{hi.label}}</span></div><button data-edit-account style="font-size:11px;background:rgba(99,130,240,0.08);color:#6382F0;border:1px solid rgba(99,130,240,0.18);border-radius:6px;padding:3px 8px;cursor:pointer;">Edit</button><button data-archive-account style="font-size:11px;background:rgba(239,68,68,0.06);color:#F87171;border:1px solid rgba(239,68,68,0.18);border-radius:6px;padding:3px 8px;cursor:pointer;">Archive</button></div>
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;"><span style="font-size:12px;color:#425268;">${{esc(acct.industry || 'No industry captured')}}</span><span style="color:#1E2A3A;">·</span><span style="font-size:12px;color:#425268;">${{esc(acct.region || 'Other')}}</span></div>
    ${{acct.nextAction ? `<div style="display:inline-flex;align-items:baseline;gap:8px;background:rgba(99,130,240,0.06);border:1px solid rgba(99,130,240,0.14);border-radius:7px;padding:6px 11px;"><span style="font-size:9.5px;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:#6382F0;flex-shrink:0;">Next</span><span style="font-size:12.5px;color:#8090A8;">${{esc(acct.nextAction)}}</span></div>` : ''}}</div>
    <div style="display:flex;gap:7px;flex-shrink:0;align-items:stretch;">${{statCard(oc,'open tasks')}}${{statCard(bc,'blocked', bc>0)}}${{statCard(cc,'contacts')}}</div>
  </div></div>`;
}}
function statCard(n, label, alert=false) {{ return `<div style="background:${{alert ? 'rgba(239,68,68,0.05)' : '#0F1220'}};border:1px solid ${{alert ? 'rgba(239,68,68,0.2)' : '#1A2232'}};border-radius:8px;padding:8px 14px;text-align:center;min-width:54px;"><div style="font-size:20px;font-weight:700;color:${{alert ? '#F87171' : '#E8EDF8'}};line-height:1;letter-spacing:-0.04em;">${{n}}</div><div style="font-size:9.5px;color:${{alert ? '#F87171' : '#425268'}};margin-top:2px;">${{label}}</div></div>`; }}
function renderTabs(acct, kan) {{
  const tabs = [ ['tasks', `Tasks${{openCount(kan)>0 ? '  ('+openCount(kan)+')' : ''}}`], ['contacts', `Contacts${{contactsFor(acct.id).length ? '  ('+contactsFor(acct.id).length+')' : ''}}`], ['notes', `Notes${{notesFor(acct.id).length ? '  ('+notesFor(acct.id).length+')' : ''}}`] ];
  const accent = acct.color || '#6382F0';
  return `<div style="flex-shrink:0;background:#0A0C13;border-bottom:1px solid #161B28;padding:0 22px;display:flex;align-items:center;">${{tabs.map(([id,label]) => `<button class="tab-btn" data-tab="${{id}}" style="background:transparent;border:none;cursor:pointer;font-family:inherit;padding:11px 16px;font-size:13px;font-weight:${{state.activeTab===id?'600':'400'}};color:${{state.activeTab===id?'#DCE4F0':'#425268'}};border-bottom:2px solid ${{state.activeTab===id?accent:'transparent'}};white-space:nowrap;">${{esc(label)}}</button>`).join('')}}</div>`;
}}
function renderTasks(acct, kan) {{
  return `<div style="padding:16px 22px 18px;height:100%;box-sizing:border-box;"><div style="display:flex;gap:10px;overflow-x:auto;padding-bottom:6px;height:100%;align-items:stretch;">${{STATUSES.map(c => renderColumn(c, kan, acct)).join('')}}</div></div>`;
}}
function renderColumn(c, kan, acct) {{
  const cards = kan[c.id] || []; const isAlert = c.alertOn && cards.length > 0; const isDrop = state.dropTarget === c.id; const isAdding = state.addingToCol === c.id; const accent = acct.color || '#6382F0';
  return `<div class="kan-col" data-col="${{c.id}}" style="flex-shrink:0;width:220px;min-width:220px;display:flex;flex-direction:column;background:#0F1220;border-radius:10px;overflow:hidden;border:1px solid ${{isDrop ? accent : (isAlert ? 'rgba(239,68,68,0.22)' : (isAdding ? 'rgba(99,130,240,0.25)' : '#1A2232'))}};transition:border-color 0.12s;height:calc(100vh - 226px);max-height:calc(100vh - 226px);">
    <div style="padding:9px 11px 8px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid #1A2232;background:${{isAlert ? 'rgba(239,68,68,0.04)' : (isAdding ? 'rgba(99,130,240,0.04)' : '#0C0F19')}};"><div style="display:flex;align-items:center;gap:6px;"><div style="width:6px;height:6px;border-radius:50%;background:${{c.dot}};"></div><span style="font-size:10.5px;font-weight:700;color:${{isAlert ? '#F87171' : c.dot}};text-transform:uppercase;letter-spacing:0.07em;">${{c.label}}</span></div><div style="display:flex;align-items:center;gap:7px;"><span style="font-size:10.5px;font-weight:600;background:${{isAlert ? 'rgba(239,68,68,0.14)' : 'rgba(255,255,255,0.05)'}};color:${{isAlert ? '#F87171' : '#425268'}};border-radius:8px;padding:1px 7px;">${{cards.length}}</span><button class="col-add-btn" data-add-col="${{c.id}}" style="background:transparent;border:none;cursor:pointer;font-family:inherit;font-size:16px;line-height:1;padding:0 2px;color:${{isAdding ? '#6382F0' : '#354258'}};opacity:0.8;font-weight:300;" title="Add task">+</button></div></div>
    <div style="overflow-y:auto;padding:7px;display:flex;flex-direction:column;gap:5px;min-height:40px;flex:1;">${{cards.map(card => renderCard(card, c.id)).join('')}}${{cards.length===0 ? '<div style="border:1px dashed #1A2232;border-radius:8px;padding:14px 10px;text-align:center;font-size:11px;color:#2A3444;">drop here</div>' : ''}}</div>
    ${{isAdding ? renderAddTaskForm(c.id) : ''}}
  </div>`;
}}
function renderCard(card, colId) {{
  const ps = getPri(card.priority);
  return `<div draggable="true" class="k-card" data-card="${{esc(card.id)}}" data-card-col="${{colId}}" style="background:#141826;border:1px solid #1E2A3A;border-radius:8px;padding:10px 11px;cursor:grab;">
    <div style="display:flex;gap:6px;align-items:flex-start;margin-bottom:4px;"><div style="font-size:12.5px;font-weight:500;color:#D0D8EC;line-height:1.45;text-wrap:pretty;flex:1;">${{esc(card.title)}}</div><button data-edit-task="${{esc(card.id)}}" style="background:transparent;border:none;color:#425268;font-size:11px;cursor:pointer;">Edit</button><button data-archive-task="${{esc(card.id)}}" style="background:transparent;border:none;color:#F87171;font-size:11px;cursor:pointer;">Archive</button></div>
    ${{card.desc ? `<div style="font-size:11.5px;color:#516070;line-height:1.5;margin-bottom:5px;text-wrap:pretty;">${{esc(card.desc.length>95 ? card.desc.slice(0,95)+'…' : card.desc)}}</div>` : ''}}
    <div style="display:flex;align-items:center;gap:5px;flex-wrap:wrap;"><span style="font-size:10.5px;font-weight:600;background:${{ps.bg}};color:${{ps.color}};border-radius:4px;padding:1px 6px;text-transform:capitalize;">${{esc(card.priority)}}</span>${{card.due ? `<span style="font-size:10.5px;color:#354258;">${{esc(card.due)}}</span>` : ''}}</div>
  </div>`;
}}
function renderAddTaskForm(col) {{
  return `<div style="border-top:1px solid #1A2232;padding:8px;flex-shrink:0;"><textarea id="new-task-title" placeholder="Task title…" rows="2" style="width:100%;background:#090D16;border:1px solid #1E2A3A;border-radius:6px;padding:7px 9px;font-size:12.5px;color:#C4CFDF;outline:none;font-family:inherit;resize:none;display:block;"></textarea><textarea id="new-task-desc" placeholder="Short description (optional)…" rows="2" style="width:100%;background:#090D16;border:1px solid #1A2232;border-radius:6px;padding:6px 9px;font-size:12px;color:#8090A8;outline:none;font-family:inherit;resize:none;display:block;margin-top:5px;line-height:1.5;"></textarea><div style="display:flex;gap:4px;margin-top:5px;align-items:center;flex-wrap:wrap;"><select id="new-task-pri" style="background:#090D16;border:1px solid #1E2A3A;border-radius:5px;padding:3px 7px;font-size:11px;color:#C4CFDF;"><option value="high">High</option><option value="medium" selected>Med</option><option value="low">Low</option></select><input id="new-task-due" type="text" placeholder="Due date" style="flex:1;background:#090D16;border:1px solid #1E2A3A;border-radius:5px;padding:3px 7px;font-size:11px;color:#C4CFDF;outline:none;min-width:0;" /></div><div style="display:flex;gap:5px;margin-top:7px;"><button data-save-task="${{col}}" style="font-size:12.5px;font-weight:600;background:#6382F0;color:#fff;border:none;border-radius:7px;padding:7px 14px;cursor:pointer;">Add task</button><button data-cancel-task style="font-size:12.5px;font-weight:500;background:rgba(255,255,255,0.05);color:#425268;border:1px solid #1E2A3A;border-radius:7px;padding:7px 12px;cursor:pointer;">Cancel</button></div></div>`;
}}
function renderContacts(acct) {{
  const raw = contactsFor(acct.id);
  const clients = raw.filter(c => !c.isShowpadTeam);
  const showpadTeam = raw.filter(c => c.isShowpadTeam);
  return `<div style="padding:14px 22px 10px;display:flex;align-items:center;justify-content:space-between;"><span style="font-size:13px;font-weight:600;color:#8090A8;">${{raw.length}} Contacts</span><button data-toggle-contact style="font-size:12px;font-weight:600;background:${{state.showAddContact ? 'rgba(255,255,255,0.05)' : 'rgba(99,130,240,0.1)'}};color:${{state.showAddContact ? '#425268' : '#6382F0'}};border:1px solid ${{state.showAddContact ? '#1E2A3A' : 'rgba(99,130,240,0.2)'}};border-radius:7px;padding:5px 12px;cursor:pointer;">${{state.showAddContact ? 'Cancel' : '+ Add Contact'}}</button></div><div style="padding:0 22px 28px;">${{state.showAddContact ? renderAddContactForm() : ''}}${{renderContactSection('Clients', clients, 'Client stakeholders and customer-side contacts', 'No client contacts yet. Add one above.')}}${{renderContactSection('Showpad Account Team', showpadTeam, 'Internal Showpad teammates supporting this account', 'No Showpad account team contacts yet. Add Showpad teammates with a showpad.com email or Showpad role.')}}</div>`;
}}
function renderContactSection(title, contacts, helper, emptyText) {{
  return `<section style="margin-bottom:18px;"><div style="display:flex;align-items:baseline;gap:8px;margin:12px 0 9px;"><h3 style="font-size:12.5px;font-weight:700;color:#D8E2F0;text-transform:uppercase;letter-spacing:0.08em;margin:0;">${{esc(title)}}</h3><span style="font-size:11px;color:#354258;">${{contacts.length}}</span></div><div style="font-size:11.5px;color:#425268;margin:-4px 0 10px;">${{esc(helper)}}</div>${{contacts.length ? `<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(290px,1fr));gap:10px;">${{contacts.map(renderContactCard).join('')}}</div>` : `<div style="padding:20px 0 24px;text-align:center;color:#354258;font-size:13px;border:1px dashed #1A2232;border-radius:10px;background:rgba(255,255,255,0.01);">${{esc(emptyText)}}</div>`}}</section>`;
}}
function renderContactCard(c) {{
  const inf = getInf(c.influence); const initials = (c.name || '?').split(' ').slice(0,2).map(w=>w[0]).join('').toUpperCase(); const avatarBg = c.influence === 'champion' ? 'rgba(99,130,240,0.14)' : c.influence === 'detractor' ? 'rgba(239,68,68,0.12)' : 'rgba(255,255,255,0.05)';
  return `<div class="con-card" style="background:#0F1320;border:1px solid #1A2232;border-radius:10px;padding:14px 16px;display:flex;align-items:flex-start;gap:12px;"><div style="width:40px;height:40px;border-radius:50%;background:${{avatarBg}};color:${{inf.color}};display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;flex-shrink:0;letter-spacing:-0.02em;">${{esc(initials)}}</div><div style="flex:1;min-width:0;"><div style="display:flex;gap:6px;align-items:center;margin-bottom:2px;"><div style="font-size:13.5px;font-weight:600;color:#D8E2F0;flex:1;">${{esc(c.name)}}</div><button data-edit-contact="${{esc(c.id)}}" style="background:transparent;border:none;color:#425268;font-size:11px;cursor:pointer;">Edit</button><button data-archive-contact="${{esc(c.id)}}" style="background:transparent;border:none;color:#F87171;font-size:11px;cursor:pointer;">Archive</button></div><div style="font-size:12px;color:#425268;margin-bottom:5px;">${{esc(c.title || 'Contact')}}</div><div style="font-size:11.5px;color:#6382F0;font-family:ui-monospace,monospace;margin-bottom:7px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${{esc(c.email || '')}}</div><div style="display:flex;gap:5px;flex-wrap:wrap;"><span style="font-size:10.5px;font-weight:600;background:${{inf.bg}};color:${{inf.color}};border-radius:4px;padding:1px 6px;">${{inf.label}}</span>${{c.isShowpadTeam ? '<span style="font-size:10.5px;font-weight:600;background:rgba(99,130,240,0.1);color:#6382F0;border-radius:4px;padding:1px 6px;">Showpad</span>' : '<span style="font-size:10.5px;font-weight:600;background:rgba(255,255,255,0.05);color:#8090A8;border-radius:4px;padding:1px 6px;">Client</span>'}}${{c.isPrimary ? '<span style="font-size:10.5px;font-weight:600;background:rgba(99,130,240,0.1);color:#6382F0;border-radius:4px;padding:1px 6px;">Primary</span>' : ''}}</div></div></div>`;
}}
function renderAddContactForm() {{ return `<div style="background:#0D1020;border:1px solid #1A2232;border-radius:10px;padding:16px;margin-bottom:14px;"><div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px;"><input id="new-con-name" class="form-input" placeholder="Name *" /><input id="new-con-title" class="form-input" placeholder="Title / Role" /></div><div style="display:grid;grid-template-columns:1fr 180px;gap:8px;margin-bottom:10px;"><input id="new-con-email" class="form-input" placeholder="Email address" /><select id="new-con-kind" class="form-input" title="Contact type"><option value="client" selected>Client Contact</option><option value="showpad">Showpad Contact</option></select></div><div style="display:flex;gap:6px;"><button data-save-contact style="font-size:12.5px;font-weight:600;background:#6382F0;color:#fff;border:none;border-radius:7px;padding:7px 14px;cursor:pointer;">Add Contact</button><button data-toggle-contact style="font-size:12.5px;font-weight:500;background:rgba(255,255,255,0.05);color:#425268;border:1px solid #1E2A3A;border-radius:7px;padding:7px 12px;cursor:pointer;">Cancel</button></div></div>`; }}
function renderNotes(acct) {{
  const raw = notesFor(acct.id);
  return `<div style="padding:14px 22px 10px;display:flex;align-items:center;justify-content:space-between;"><span style="font-size:13px;font-weight:600;color:#8090A8;">${{raw.length}} Notes</span><button data-toggle-note style="font-size:12px;font-weight:600;background:${{state.showAddNote ? 'rgba(255,255,255,0.05)' : 'rgba(99,130,240,0.1)'}};color:${{state.showAddNote ? '#425268' : '#6382F0'}};border:1px solid ${{state.showAddNote ? '#1E2A3A' : 'rgba(99,130,240,0.2)'}};border-radius:7px;padding:5px 12px;cursor:pointer;">${{state.showAddNote ? 'Cancel' : '+ Write a note'}}</button></div><div style="padding:0 22px 28px;max-width:760px;">${{state.showAddNote ? renderAddNoteForm() : ''}}${{raw.length ? raw.map(renderNote).join('') : '<div style="padding:36px 0;text-align:center;color:#354258;font-size:13px;">No notes yet. Write one above.</div>'}}</div>`;
}}
function renderAddNoteForm() {{ return `<div style="background:#0D1020;border:1px solid #1A2232;border-radius:10px;padding:14px 16px;margin-bottom:6px;"><textarea id="new-note" placeholder="Write a note…" rows="4" style="width:100%;background:#090D16;border:1px solid #1E2A3A;border-radius:7px;padding:9px 11px;font-size:13px;color:#C4CFDF;outline:none;font-family:inherit;resize:vertical;display:block;line-height:1.55;"></textarea><div style="display:flex;gap:6px;margin-top:10px;align-items:center;"><button data-save-note style="font-size:12.5px;font-weight:600;background:#6382F0;color:#fff;border:none;border-radius:7px;padding:7px 14px;cursor:pointer;">Save Note</button><button data-toggle-note style="font-size:12.5px;font-weight:500;background:rgba(255,255,255,0.05);color:#425268;border:1px solid #1E2A3A;border-radius:7px;padding:7px 12px;cursor:pointer;">Cancel</button><span style="font-size:11px;color:#2A3444;margin-left:auto;">Saving as Craig</span></div></div>`; }}
function renderNote(n) {{
  const expanded = !!state.expandedNotes[n.id]; const text = expanded || (n.text || '').length <= 130 ? (n.text || '') : n.text.slice(0,130) + '…';
  return `<div data-note="${{esc(n.id)}}" style="padding:14px 0;border-bottom:1px solid #161B28;cursor:pointer;"><div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;"><span style="font-size:10.5px;color:#354258;font-family:ui-monospace,monospace;">${{esc(n.ts)}}</span><span style="font-size:11px;font-weight:600;color:#6382F0;">${{esc(n.author || 'Craig')}}</span>${{expanded ? '<span style="font-size:10px;color:#354258;margin-left:auto;">collapse ↑</span>' : '<span style="margin-left:auto;"></span>'}}<button data-edit-note="${{esc(n.id)}}" style="background:transparent;border:none;color:#425268;font-size:11px;cursor:pointer;">Edit</button><button data-archive-note="${{esc(n.id)}}" style="background:transparent;border:none;color:#F87171;font-size:11px;cursor:pointer;">Archive</button></div><p style="font-size:13px;color:#7A8BA0;line-height:1.6;margin:0;text-wrap:pretty;">${{esc(text)}}</p></div>`;
}}
function renderEditorOverlay() {{
  if (!state.editor) return '';
  const e = state.editor;
  const title = e.type === 'task' ? 'Edit Task' : e.type === 'contact' ? 'Edit Contact' : 'Edit Note';
  return `<div class="editor-backdrop" style="position:fixed;inset:0;z-index:9998;background:rgba(3,6,12,0.72);backdrop-filter:blur(5px);display:flex;align-items:center;justify-content:center;padding:26px;">
    <div class="editor-panel" style="width:min(720px,94vw);max-height:88vh;overflow:auto;background:#0D1020;border:1px solid #26344D;border-radius:16px;box-shadow:0 24px 80px rgba(0,0,0,.45);">
      <div style="display:flex;align-items:center;justify-content:space-between;padding:18px 20px;border-bottom:1px solid #1A2232;"><div style="font-size:18px;font-weight:700;color:#DCE4F0;">${{title}}</div><button data-editor-cancel onclick="state.editor=null;render();" style="background:rgba(255,255,255,0.04);border:1px solid #1E2A3A;border-radius:8px;color:#8090A8;padding:6px 10px;cursor:pointer;">Close</button></div>
      <div style="padding:18px 20px;">${{e.type === 'task' ? renderTaskEditor(e.item) : e.type === 'contact' ? renderContactEditor(e.item) : renderNoteEditor(e.item)}}</div>
    </div>
  </div>`;
}}
function fieldStyle() {{ return 'width:100%;box-sizing:border-box;background:#090D16;border:1px solid #1E2A3A;border-radius:8px;padding:9px 10px;font-size:13px;color:#C4CFDF;outline:none;font-family:inherit;'; }}
function label(text, inputHtml) {{ return `<label style="display:block;font-size:11px;font-weight:700;color:#516070;text-transform:uppercase;letter-spacing:.07em;">${{text}}<div style="margin-top:6px;">${{inputHtml}}</div></label>`; }}
function renderTaskEditor(card) {{
  return `<div style="display:grid;gap:14px;">
    ${{label('Title', `<input id="edit-task-title" value="${{esc(card.title || '')}}" style="${{fieldStyle()}}" />`)}}
    ${{label('Description', `<textarea id="edit-task-desc" rows="7" style="${{fieldStyle()}}resize:vertical;line-height:1.55;">${{esc(card.summary || card.desc || '')}}</textarea>`)}}
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
      ${{label('Weight', `<select id="edit-task-priority" style="${{fieldStyle()}}"><option value="high" ${{card.priority==='high'?'selected':''}}>High</option><option value="medium" ${{(card.priority||'medium')==='medium'?'selected':''}}>Medium</option><option value="low" ${{card.priority==='low'?'selected':''}}>Low</option></select>`)}}
      ${{label('Due date', `<input id="edit-task-due" value="${{esc(card.due || '')}}" style="${{fieldStyle()}}" />`)}}
    </div>
    <div style="display:flex;justify-content:flex-end;gap:8px;margin-top:4px;"><button data-editor-cancel onclick="state.editor=null;render();" class="editor-secondary">Cancel</button><button data-editor-save-task="${{esc(card.id)}}" onclick="saveActiveEditor()" class="editor-primary">Save task</button></div>
  </div>`;
}}
function renderContactEditor(c) {{
  const kind = c.isShowpadTeam ? 'showpad' : 'client';
  return `<div style="display:grid;gap:14px;">
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">${{label('Name', `<input id="edit-contact-name" value="${{esc(c.name || '')}}" style="${{fieldStyle()}}" />`)}}${{label('Title / role', `<input id="edit-contact-title" value="${{esc(c.title || '')}}" style="${{fieldStyle()}}" />`)}}</div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">${{label('Email', `<input id="edit-contact-email" value="${{esc(c.email || '')}}" style="${{fieldStyle()}}" />`)}}${{label('Phone', `<input id="edit-contact-phone" value="${{esc(c.phone || '')}}" style="${{fieldStyle()}}" />`)}}</div>
    ${{label('Contact type', `<select id="edit-contact-kind" style="${{fieldStyle()}}"><option value="client" ${{kind==='client'?'selected':''}}>Client Contact</option><option value="showpad" ${{kind==='showpad'?'selected':''}}>Showpad Contact</option></select>`)}}
    ${{label('Notes', `<textarea id="edit-contact-notes" rows="6" style="${{fieldStyle()}}resize:vertical;line-height:1.55;">${{esc(c.notes || '')}}</textarea>`)}}
    <div style="display:flex;justify-content:flex-end;gap:8px;margin-top:4px;"><button data-editor-cancel onclick="state.editor=null;render();" class="editor-secondary">Cancel</button><button data-editor-save-contact="${{esc(c.id)}}" onclick="saveActiveEditor()" class="editor-primary">Save contact</button></div>
  </div>`;
}}
function renderNoteEditor(n) {{
  return `<div style="display:grid;gap:14px;">
    ${{label('Note body', `<textarea id="edit-note-body" rows="12" style="${{fieldStyle()}}resize:vertical;line-height:1.6;min-height:260px;">${{esc(n.body || n.text || '')}}</textarea>`)}}
    <div style="font-size:11.5px;color:#516070;">Editing inline keeps long notes readable without a browser pop-up.</div>
    <div style="display:flex;justify-content:flex-end;gap:8px;margin-top:4px;"><button data-editor-cancel onclick="state.editor=null;render();" class="editor-secondary">Cancel</button><button data-editor-save-note="${{esc(n.id)}}" onclick="saveActiveEditor()" class="editor-primary">Save note</button></div>
  </div>`;
}}
function render() {{
  const acct = getAccount(); const kan = kanbanFor(acct.id);
  const content = state.activeTab === 'contacts' ? renderContacts(acct) : state.activeTab === 'notes' ? renderNotes(acct) : renderTasks(acct, kan);
  document.getElementById('app').innerHTML = `<div style="display:flex;height:100vh;overflow:hidden;background:#0C0E15;font-family:'DM Sans',system-ui,sans-serif;color:#DCE4F0;">${{renderSidebar()}}<main style="flex:1;min-width:0;display:flex;flex-direction:column;overflow:hidden;">${{renderTopBar(acct)}}${{renderHeader(acct, kan)}}${{renderTabs(acct, kan)}}<div style="flex:1;overflow-y:auto;overflow-x:hidden;background:#0C0E15;">${{content}}</div></main></div>${{renderEditorOverlay()}}`;
  bind();
}}
function bind() {{
  const search = document.getElementById('search'); if (search) search.addEventListener('input', e => {{ state.search = e.target.value; render(); document.getElementById('search')?.focus(); }});
  document.querySelectorAll('[data-account]').forEach(el => el.addEventListener('click', () => {{ state.selectedId = el.dataset.account; state.activeTab = 'tasks'; state.addingToCol = null; state.showAddContact=false; state.showAddNote=false; render(); }}));
  document.querySelectorAll('[data-tab]').forEach(el => el.addEventListener('click', () => {{ state.activeTab = el.dataset.tab; render(); }}));
  document.querySelectorAll('[data-add-col]').forEach(el => el.addEventListener('click', () => {{ state.addingToCol = state.addingToCol === el.dataset.addCol ? null : el.dataset.addCol; render(); }}));
  document.querySelectorAll('[data-cancel-task]').forEach(el => el.addEventListener('click', () => {{ state.addingToCol = null; render(); }}));
  document.querySelectorAll('[data-save-task]').forEach(el => el.addEventListener('click', () => addTask(el.dataset.saveTask)));
  document.querySelectorAll('[data-edit-task]').forEach(el => el.addEventListener('click', e => {{ e.stopPropagation(); editTask(el.dataset.editTask); }}));
  document.querySelectorAll('[data-archive-task]').forEach(el => el.addEventListener('click', e => {{ e.stopPropagation(); archiveTask(el.dataset.archiveTask); }}));
  document.querySelectorAll('.k-card').forEach(el => {{ el.addEventListener('dragstart', () => {{ state.drag = {{ cardId: el.dataset.card, colId: el.dataset.cardCol }}; }}); }});
  document.querySelectorAll('.kan-col').forEach(el => {{ el.addEventListener('dragover', e => {{ e.preventDefault(); state.dropTarget = el.dataset.col; }}); el.addEventListener('drop', e => {{ e.preventDefault(); dropCard(el.dataset.col); }}); el.addEventListener('dragleave', () => {{ state.dropTarget = null; }}); }});
  document.querySelectorAll('[data-toggle-contact]').forEach(el => el.addEventListener('click', () => {{ state.showAddContact = !state.showAddContact; render(); }}));
  document.querySelectorAll('[data-save-contact]').forEach(el => el.addEventListener('click', addContact));
  document.querySelectorAll('[data-edit-contact]').forEach(el => el.addEventListener('click', e => {{ e.stopPropagation(); editContact(el.dataset.editContact); }}));
  document.querySelectorAll('[data-archive-contact]').forEach(el => el.addEventListener('click', e => {{ e.stopPropagation(); archiveContact(el.dataset.archiveContact); }}));
  document.querySelectorAll('[data-toggle-note]').forEach(el => el.addEventListener('click', () => {{ state.showAddNote = !state.showAddNote; render(); }}));
  document.querySelectorAll('[data-save-note]').forEach(el => el.addEventListener('click', addNote));
  document.querySelectorAll('[data-edit-note]').forEach(el => el.addEventListener('click', e => {{ e.stopPropagation(); editNote(el.dataset.editNote); }}));
  document.querySelectorAll('[data-archive-note]').forEach(el => el.addEventListener('click', e => {{ e.stopPropagation(); archiveNote(el.dataset.archiveNote); }}));
  document.querySelectorAll('[data-note]').forEach(el => el.addEventListener('click', () => {{ state.expandedNotes[el.dataset.note] = !state.expandedNotes[el.dataset.note]; render(); }}));
  document.querySelectorAll('[data-edit-account]').forEach(el => el.addEventListener('click', editAccount));
  document.querySelectorAll('[data-archive-account]').forEach(el => el.addEventListener('click', archiveAccount));
  document.querySelectorAll('[data-editor-cancel]').forEach(el => el.addEventListener('click', () => {{ state.editor = null; render(); }}));
  document.querySelectorAll('[data-editor-save-task],[data-editor-save-contact],[data-editor-save-note]').forEach(el => el.addEventListener('click', saveActiveEditor));
}}
function saveActiveEditor() {{
  if (!state.editor) return;
  const id = state.editor.item?.id;
  if (state.editor.type === 'task') saveTaskEditor(id);
  if (state.editor.type === 'contact') saveContactEditor(id);
  if (state.editor.type === 'note') saveNoteEditor(id);
}}
function findTask(id) {{ const kan = kanbanFor(state.selectedId); for (const col of Object.keys(kan)) {{ const card = (kan[col] || []).find(c => String(c.id) === String(id)); if (card) return {{ card, col }}; }} return null; }}
function editAccount() {{
  const acct = getAccount(); if (String(acct.id) === '__empty__') return;
  const name = prompt('Account name', acct.name || ''); if (name === null || !name.trim()) return;
  const industry = prompt('Industry', acct.industry || '') ?? (acct.industry || '');
  const region = prompt('Region', acct.region || '') ?? (acct.region || '');
  acct.name = name.trim(); acct.industry = industry.trim(); acct.region = region.trim(); render();
  persistDashboardAction('update_account', {{ account_id: acct.id, name: acct.name, industry: acct.industry, region: acct.region }});
}}
function archiveAccount() {{
  const acct = getAccount(); if (String(acct.id) === '__empty__') return;
  if (!confirm(`Archive account "${{acct.name}}"? It will be hidden from the dashboard and Claude search/list results.`)) return;
  state.accounts = state.accounts.filter(a => String(a.id) !== String(acct.id)); state.selectedId = state.accounts[0]?.id || '__empty__'; render();
  persistDashboardAction('archive_account', {{ account_id: acct.id }});
}}
function editTask(id) {{
  const found = findTask(id); if (!found) return;
  state.editor = {{ type: 'task', item: {{ ...found.card }} }}; render();
}}
function saveTaskEditor(id) {{
  const found = findTask(id); if (!found) return; const card = found.card;
  const title = document.getElementById('edit-task-title')?.value.trim(); if (!title) return;
  const desc = document.getElementById('edit-task-desc')?.value.trim() || '';
  const due = document.getElementById('edit-task-due')?.value.trim() || '';
  const priority = document.getElementById('edit-task-priority')?.value || 'medium';
  card.title = title; card.desc = desc; card.summary = desc; card.due = due; card.priority = priority; state.editor = null; render();
  persistDashboardAction('update_task', {{ task_id: id, title: card.title, summary: card.summary, due_date: card.due, priority: card.priority }});
}}
function archiveTask(id) {{
  const found = findTask(id); if (!found || !confirm(`Archive task "${{found.card.title}}"?`)) return;
  const kan = kanbanFor(state.selectedId); kan[found.col] = (kan[found.col] || []).filter(c => String(c.id) !== String(id)); render();
  persistDashboardAction('archive_task', {{ task_id: id }});
}}
function findContact(id) {{ return (contactsFor(state.selectedId) || []).find(c => String(c.id) === String(id)); }}
function editContact(id) {{
  const c = findContact(id); if (!c) return;
  state.editor = {{ type: 'contact', item: {{ ...c }} }}; render();
}}
function saveContactEditor(id) {{
  const c = findContact(id); if (!c) return;
  const name = document.getElementById('edit-contact-name')?.value.trim(); if (!name) return;
  const title = document.getElementById('edit-contact-title')?.value.trim() || '';
  const email = document.getElementById('edit-contact-email')?.value.trim() || '';
  const phone = document.getElementById('edit-contact-phone')?.value.trim() || '';
  const notes = document.getElementById('edit-contact-notes')?.value.trim() || '';
  const kind = document.getElementById('edit-contact-kind')?.value || 'client';
  c.name = name; c.title = title; c.email = email; c.phone = phone; c.notes = notes; c.isShowpadTeam = kind === 'showpad'; state.editor = null; render();
  persistDashboardAction('update_contact', {{ contact_id: id, name: c.name, title: c.title, email: c.email, phone: c.phone, notes: c.notes, contact_kind: kind }});
}}
function archiveContact(id) {{
  const c = findContact(id); if (!c || !confirm(`Archive contact "${{c.name}}"?`)) return;
  const key = String(state.selectedId); state.contacts[key] = (state.contacts[key] || []).filter(x => String(x.id) !== String(id)); render();
  persistDashboardAction('archive_contact', {{ contact_id: id }});
}}
function findNote(id) {{ return (notesFor(state.selectedId) || []).find(n => String(n.id) === String(id)); }}
function editNote(id) {{
  const n = findNote(id); if (!n) return;
  state.editor = {{ type: 'note', item: {{ ...n }} }}; render();
}}
function saveNoteEditor(id) {{
  const n = findNote(id); if (!n) return;
  const body = document.getElementById('edit-note-body')?.value.trim(); if (!body) return;
  n.body = body; n.text = body; state.editor = null; render();
  persistDashboardAction('update_note', {{ note_id: id, body: n.body, source: n.author || 'Dashboard' }});
}}
function archiveNote(id) {{
  const n = findNote(id); if (!n || !confirm('Archive this note?')) return;
  const key = String(state.selectedId); state.notes[key] = (state.notes[key] || []).filter(x => String(x.id) !== String(id)); render();
  persistDashboardAction('archive_note', {{ note_id: id }});
}}
function addTask(col) {{
  if (String(state.selectedId) === '__empty__') {{ alert('Create an account in Claude Desktop before adding dashboard items.'); return; }}
  const title = document.getElementById('new-task-title')?.value.trim(); if (!title) return;
  const desc = document.getElementById('new-task-desc')?.value.trim() || '';
  const due = document.getElementById('new-task-due')?.value.trim() || '';
  const priority = document.getElementById('new-task-pri')?.value || 'medium';
  const kan = kanbanFor(state.selectedId); kan[col] = [...(kan[col] || []), {{ id: 'saving-' + Date.now(), title, desc, due, priority }}]; state.addingToCol = null; render();
  persistDashboardAction('create_task', {{ account_id: state.selectedId, status: col, title, summary: desc, due_date: due, priority }});
}}
function dropCard(targetCol) {{
  const drag = state.drag; if (!drag || drag.colId === targetCol) {{ state.drag=null; state.dropTarget=null; render(); return; }}
  const kan = kanbanFor(state.selectedId); const card = (kan[drag.colId] || []).find(c => String(c.id) === String(drag.cardId)); if (!card) return;
  kan[drag.colId] = (kan[drag.colId] || []).filter(c => String(c.id) !== String(drag.cardId)); kan[targetCol] = [...(kan[targetCol] || []), card]; state.drag=null; state.dropTarget=null; render();
  if (!String(card.id).startsWith('saving-') && !String(card.id).startsWith('u')) persistDashboardAction('set_task_status', {{ task_id: card.id, status: targetCol }});
}}
function addContact() {{
  if (String(state.selectedId) === '__empty__') {{ alert('Create an account in Claude Desktop before adding dashboard items.'); return; }}
  const name = document.getElementById('new-con-name')?.value.trim(); if (!name) return;
  const title = document.getElementById('new-con-title')?.value.trim() || 'Contact'; const email = document.getElementById('new-con-email')?.value.trim() || '';
  const contact_kind = document.getElementById('new-con-kind')?.value || 'client';
  const key = String(state.selectedId); state.contacts[key] = [...(state.contacts[key] || []), {{ id:'saving-'+Date.now(), name, title, email, influence:'neutral', isPrimary:false, isShowpadTeam: contact_kind === 'showpad' }}]; state.showAddContact=false; render();
  persistDashboardAction('create_contact', {{ account_id: state.selectedId, name, title, email, contact_kind }});
}}
function addNote() {{
  if (String(state.selectedId) === '__empty__') {{ alert('Create an account in Claude Desktop before adding dashboard items.'); return; }}
  const text = document.getElementById('new-note')?.value.trim(); if (!text) return;
  const key = String(state.selectedId); const d = new Date().toISOString().slice(0,10); state.notes[key] = [{{ id:'saving-'+Date.now(), ts:d, author:'Dashboard', text }}, ...(state.notes[key] || [])]; state.showAddNote=false; render();
  persistDashboardAction('create_note', {{ account_id: state.selectedId, body: text, source: 'Dashboard' }});
}}
render();
</script>
</body>
</html>"""


# Compatibility helpers retained for the existing Streamlit dashboard regression tests.
def _render_summary(data: dict) -> None:
    summary = data["summary"]
    snapshot = data["snapshot"]
    cols = st.columns(6)
    cols[0].metric("Accounts", summary["account_count"])
    cols[1].metric("Contacts", summary.get("contact_count", 0))
    cols[2].metric("Open tasks", summary["open_task_count"])
    cols[3].metric("Urgent", len(snapshot["urgent_tasks"]))
    cols[4].metric("Blocked", len(snapshot["blocked_tasks"]))
    cols[5].metric("Reports", summary["reporting_import_count"])


def _render_board(data: dict, data_dir: str | Path) -> None:
    filtered_tasks = data["tasks"]
    _render_kanban_board(filtered_tasks, data_dir)
    focus_tasks = data.get("focus_tasks", [])
    if focus_tasks:
        st.markdown("### Focus queue")
        for task in focus_tasks:
            _render_focus_task(task, data_dir)
    _render_task_drilldown(filtered_tasks, data_dir)


def _render_focus_task(task: dict, data_dir: str | Path) -> None:
    with st.container(border=True):
        st.markdown(f"**{task['title']}**")
        if st.button("Mark done", key=f"focus_done_{task['id']}"):
            set_dashboard_task_status(data_dir, int(task["id"]), "done")
            st.rerun()


def _render_kanban_board(tasks: list[dict], data_dir: str | Path) -> None:
    columns = st.columns(len(KANBAN_STATUSES))
    by_status = {status: [] for status in KANBAN_STATUSES}
    for task in tasks:
        by_status.setdefault(task.get("status") or "inbox", []).append(task)
    for idx, status in enumerate(KANBAN_STATUSES):
        with columns[idx]:
            st.markdown(f"#### {status.title()} ({len(by_status.get(status, []))})")
            for task in by_status.get(status, []):
                _render_kanban_task_card(task, data_dir)


def _render_kanban_task_card(task: dict, data_dir: str | Path) -> None:
    status = task.get("status") or "inbox"
    with st.container(border=True):
        st.markdown(f"**{task['title']}**")
        target_status = st.selectbox(
            "Move to",
            options=KANBAN_STATUSES,
            index=KANBAN_STATUSES.index(status) if status in KANBAN_STATUSES else 0,
            key=f"kanban_move_select_{task['id']}",
        )
        if st.button("Save move", key=f"kanban_save_move_{task['id']}", disabled=target_status == status):
            set_dashboard_task_status(data_dir, int(task["id"]), target_status)
            st.rerun()


def _render_task_drilldown(tasks: list[dict], data_dir: str | Path) -> None:
    if not tasks:
        return
    task_options = {_task_select_label(task): task for task in tasks}
    selected_label = st.selectbox("Select a task", options=list(task_options.keys()))
    task = task_options[selected_label]
    if st.button("Mark done", key=f"detail_done_{task['id']}"):
        set_dashboard_task_status(data_dir, int(task["id"]), "done")
        st.rerun()
    if st.checkbox("Confirm delete", key=f"confirm_delete_{task['id']}"):
        if st.button("Delete task", key=f"delete_{task['id']}"):
            delete_dashboard_task(data_dir, int(task["id"]))
            st.rerun()


def _kanban_containers(tasks: list[dict]) -> list[dict[str, object]]:
    containers: list[dict[str, object]] = []
    for status in KANBAN_STATUSES:
        status_tasks = [task for task in tasks if (task.get("status") or "inbox") == status]
        containers.append({"header": f"{status.title()} ({len(status_tasks)})", "items": [_task_card_label(task) for task in status_tasks]})
    return containers


def _apply_dragdrop_status_changes(data_dir: str | Path, tasks: list[dict], sorted_containers: list[dict]) -> list[dict[str, str]]:
    original_status = {int(task["id"]): task.get("status") or "inbox" for task in tasks}
    titles = {int(task["id"]): task["title"] for task in tasks}
    moved: list[dict[str, str]] = []
    for idx, container in enumerate(sorted_containers):
        if idx >= len(KANBAN_STATUSES):
            continue
        new_status = KANBAN_STATUSES[idx]
        for item in container.get("items", []):
            task_id = _task_id_from_card_label(str(item))
            if task_id is None or task_id not in original_status:
                continue
            if original_status[task_id] != new_status:
                set_dashboard_task_status(data_dir, task_id, new_status)
                moved.append({"title": titles[task_id], "status": new_status})
    return moved


def _task_card_label(task: dict) -> str:
    account = task.get("account_name") or "Unassigned"
    priority = task.get("priority") or "normal"
    due = task.get("due_date") or "no due date"
    next_action = (task.get("next_action") or "").strip()
    label = f"#{task['id']} · {task['title']} · {account} · {priority} · due {due}"
    if next_action:
        label += f" · next: {next_action}"
    return label


def _task_select_label(task: dict) -> str:
    return f"#{task['id']} · {task['title']} ({task.get('status') or 'inbox'})"


def _task_id_from_card_label(label: str) -> int | None:
    match = re.match(r"#(\d+)\b", label)
    return int(match.group(1)) if match else None


def _kanban_style_for_tasks(tasks: list[dict]) -> str:
    color_rules: list[str] = []
    for column_idx, status in enumerate(KANBAN_STATUSES, start=1):
        status_tasks = [task for task in tasks if (task.get("status") or "inbox") == status]
        for item_idx, task in enumerate(status_tasks, start=1):
            color = (task.get("account_color") or "").strip()
            if not re.fullmatch(r"#[0-9A-Fa-f]{6}", color):
                continue
            selector = f".sortable-container:nth-of-type({column_idx}) .sortable-item:nth-child({item_idx})"
            color_rules.append(f"""{selector} {{
    background: {color} !important;
    border-color: rgba(15, 23, 42, 0.18) !important;
    color: #FFFFFF !important;
    text-shadow: 0 1px 1px rgba(0, 0, 0, 0.35);
}}""")
    return _KANBAN_STYLE + ("\n" + "\n".join(color_rules) if color_rules else "")


_KANBAN_STYLE = """
.sortable-component {
    display: flex;
    flex-direction: row;
    flex-wrap: nowrap;
    gap: 0.75rem;
    align-items: stretch;
    width: 100%;
    overflow-x: auto;
}
.sortable-container {
    flex: 1 1 0;
    align-self: flex-start;
    margin-top: 0 !important;
    min-width: 0;
    max-width: calc((100% - 3.75rem) / 6);
    background: #0F1220;
    border: 1px solid #1A2232;
    border-radius: 0.75rem;
}
.sortable-container-header {
    background: #0C0F19;
    border-bottom: 1px solid #1A2232;
    color: #8090A8;
    font-weight: 700;
    padding: 0.55rem 0.75rem;
}
.sortable-container-body {
    min-height: 8rem;
    padding: 0.45rem;
}
.sortable-item {
    background: #141826;
    border: 1px solid #1E2A3A;
    border-radius: 0.55rem;
    color: #D0D8EC;
    font-size: 0.84rem;
    line-height: 1.25rem;
    margin: 0.35rem 0;
    padding: 0.55rem;
}
.sortable-item:hover {
    border-color: #6382F0;
    box-shadow: 0 2px 6px rgba(99, 130, 240, 0.20);
}
"""


def main() -> None:
    from streamlit.web import cli as stcli

    script_path = Path(__file__).resolve()
    sys.argv = [
        "streamlit",
        "run",
        str(script_path),
        "--server.headless=true",
        "--browser.gatherUsageStats=false",
    ]
    raise SystemExit(stcli.main())


if __name__ == "__main__":
    render_app()
