from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any

from .db import WorkbenchDB


KANBAN_STATUSES = ["inbox", "active", "waiting", "blocked", "done", "archived"]
PRIORITY_ORDER = ["urgent", "high", "normal", "low"]
OPEN_TASK_STATUSES = {"inbox", "active", "waiting", "blocked"}


def build_dashboard_data(data_dir: str | Path | None = None) -> dict[str, Any]:
    db = WorkbenchDB(data_dir)
    db.initialize()

    accounts = db.list_accounts(limit=500)
    contacts = db.list_contacts(limit=1000)
    tasks = db.query_all(
        """
        SELECT t.*, a.name AS account_name, a.account_color AS account_color
        FROM tasks t
        LEFT JOIN accounts a ON a.id = t.account_id
        WHERE t.status != 'archived'
        AND (a.id IS NULL OR COALESCE(a.archived_at, '') = '')
        ORDER BY t.updated_at DESC
        """
    )
    documents = db.query_all(
        """
        SELECT d.*, a.name AS account_name
        FROM documents d
        LEFT JOIN accounts a ON a.id = d.account_id
        ORDER BY d.updated_at DESC
        LIMIT 20
        """
    )
    reporting_imports = db.list_reporting_imports(limit=20)
    notes = db.query_all(
        """
        SELECT n.*, a.name AS account_name, t.title AS task_title
        FROM notes n
        LEFT JOIN accounts a ON a.id = n.account_id
        LEFT JOIN tasks t ON t.id = n.task_id
        WHERE COALESCE(n.archived_at, '') = ''
        AND (a.id IS NULL OR COALESCE(a.archived_at, '') = '')
        AND (t.id IS NULL OR t.status != 'archived')
        ORDER BY n.updated_at DESC
        LIMIT 200
        """
    )
    snapshot = db.daily_work_snapshot()

    tasks_by_status = _group_tasks_by_status(tasks)
    tasks_by_account = _summarize_accounts(accounts, tasks, contacts)
    status_counts = _ordered_counts(((task.get("status") or "inbox") for task in tasks), KANBAN_STATUSES)
    priority_counts = _ordered_counts(((task.get("priority") or "normal") for task in tasks), PRIORITY_ORDER)
    open_tasks = [task for task in tasks if task.get("status") not in {"done", "archived"}]
    focus_tasks = _build_focus_tasks(tasks)

    return {
        "db_path": str(db.db_path),
        "accounts": accounts,
        "contacts": contacts,
        "tasks": tasks,
        "documents": documents,
        "notes": notes,
        "reporting_imports": reporting_imports,
        "snapshot": snapshot,
        "kanban_statuses": KANBAN_STATUSES,
        "tasks_by_status": tasks_by_status,
        "tasks_by_account": tasks_by_account,
        "status_counts": status_counts,
        "priority_counts": priority_counts,
        "focus_tasks": focus_tasks,
        "summary": {
            "account_count": len(accounts),
            "task_count": len(tasks),
            "open_task_count": len(open_tasks),
            "document_count": db.query_one("SELECT COUNT(*) AS count FROM documents")["count"],
            "contact_count": len(contacts),
            "reporting_import_count": len(reporting_imports),
        },
    }


def _group_tasks_by_status(tasks: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {status: [] for status in KANBAN_STATUSES}
    extras: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for task in tasks:
        status = task.get("status") or "inbox"
        if status in grouped:
            grouped[status].append(task)
        else:
            extras[status].append(task)
    for status, rows in extras.items():
        grouped[status] = rows
    for rows in grouped.values():
        rows.sort(key=_task_sort_key)
    return grouped


def _task_sort_key(task: dict[str, Any]) -> tuple[int, str, str]:
    priority = task.get("priority") or "normal"
    try:
        priority_idx = PRIORITY_ORDER.index(priority)
    except ValueError:
        priority_idx = len(PRIORITY_ORDER)
    due_date = task.get("due_date") or "9999-99-99"
    updated_at = task.get("updated_at") or ""
    return (priority_idx, due_date, updated_at)


def _focus_sort_key(task: dict[str, Any]) -> tuple[int, int, str, str]:
    reason = task.get("focus_reason") or "priority"
    reason_rank = {"blocked": 0, "overdue": 1, "due_soon": 2, "priority": 3}
    priority = task.get("priority") or "normal"
    try:
        priority_idx = PRIORITY_ORDER.index(priority)
    except ValueError:
        priority_idx = len(PRIORITY_ORDER)
    due_date = task.get("due_date") or "9999-99-99"
    updated_at = task.get("updated_at") or ""
    return (reason_rank.get(reason, 4), priority_idx, due_date, updated_at)


def _build_focus_tasks(tasks: list[dict[str, Any]], limit: int = 8) -> list[dict[str, Any]]:
    today = date.today().isoformat()
    focus_tasks: list[dict[str, Any]] = []
    for task in tasks:
        status = task.get("status") or "inbox"
        if status not in OPEN_TASK_STATUSES:
            continue

        due_date = task.get("due_date")
        priority = task.get("priority") or "normal"
        focus_reason = None
        if status == "blocked":
            focus_reason = "blocked"
        elif due_date and due_date < today:
            focus_reason = "overdue"
        elif due_date and due_date <= today:
            focus_reason = "due_soon"
        elif priority in {"urgent", "high"}:
            focus_reason = "priority"
        elif due_date:
            focus_reason = "due_soon"

        if focus_reason:
            focus_tasks.append({**task, "focus_reason": focus_reason})

    focus_tasks.sort(key=_focus_sort_key)
    return focus_tasks[:limit]


def _ordered_counts(values: Any, order: list[str]) -> dict[str, int]:
    counts = Counter(values)
    ordered = {name: counts.get(name, 0) for name in order}
    for key, count in counts.items():
        if key not in ordered:
            ordered[key] = count
    return ordered


def _summarize_accounts(accounts: list[dict[str, Any]], tasks: list[dict[str, Any]], contacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    task_counts: dict[int, Counter[str]] = defaultdict(Counter)
    contact_counts: Counter[int] = Counter()
    primary_contacts: dict[int, str] = {}
    next_actions: dict[int, str] = {}
    for contact in contacts:
        account_id = contact.get("account_id")
        if account_id is None:
            continue
        contact_counts[account_id] += 1
        if contact.get("is_primary") and account_id not in primary_contacts:
            primary_contacts[account_id] = _format_contact_label(contact)
    for task in tasks:
        account_id = task.get("account_id")
        if account_id is None:
            continue
        status = task.get("status") or "inbox"
        task_counts[account_id][status] += 1
        if not next_actions.get(account_id) and (task.get("next_action") or "").strip():
            next_actions[account_id] = task["next_action"]

    rows: list[dict[str, Any]] = []
    for account in accounts:
        counts = task_counts.get(account["id"], Counter())
        rows.append(
            {
                "account_id": account["id"],
                "account_name": account["name"],
                "region": account.get("region") or "",
                "industry": account.get("industry") or "",
                "account_color": account.get("account_color") or "",
                "contact_count": contact_counts.get(account["id"], 0),
                "primary_contact": primary_contacts.get(account["id"], ""),
                "open_task_count": sum(count for status, count in counts.items() if status not in {"done", "archived"}),
                "active_task_count": counts.get("active", 0),
                "waiting_task_count": counts.get("waiting", 0),
                "blocked_task_count": counts.get("blocked", 0),
                "next_action": next_actions.get(account["id"], ""),
            }
        )
    rows.sort(key=lambda row: (-row["open_task_count"], row["account_name"].lower()))
    return rows


def _format_contact_label(contact: dict[str, Any]) -> str:
    name = contact.get("name") or ""
    email = contact.get("email") or ""
    if name and email:
        return f"{name} <{email}>"
    return name or email


def set_dashboard_account_color(data_dir: str | Path | None, account_id: int, account_color: str) -> dict[str, Any]:
    db = WorkbenchDB(data_dir)
    db.initialize()
    return db.update_account(account_id, account_color=account_color)


def set_dashboard_task_status(data_dir: str | Path | None, task_id: int, status: str) -> dict[str, Any]:
    db = WorkbenchDB(data_dir)
    db.initialize()
    return db.set_task_status(task_id, status)


def delete_dashboard_task(data_dir: str | Path | None, task_id: int) -> dict[str, int]:
    db = WorkbenchDB(data_dir)
    db.initialize()
    return db.delete_task(task_id)


__all__ = [
    "KANBAN_STATUSES",
    "PRIORITY_ORDER",
    "build_dashboard_data",
    "delete_dashboard_task",
    "set_dashboard_account_color",
    "set_dashboard_task_status",
]
