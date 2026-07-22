from __future__ import annotations

import csv
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TASK_TYPES = {
    "customer_issue", "troubleshooting", "research", "document", "meeting_prep",
    "meeting_followup", "escalation", "internal_summary", "customer_response", "general",
}
TASK_STATUSES = {"inbox", "active", "waiting", "blocked", "done", "archived"}
TASK_PRIORITIES = {"low", "normal", "high", "urgent"}
SUPPORT_LEVELS = {"champion", "supporter", "neutral", "detractor"}
DOCUMENT_TYPES = {
    "customer_email", "internal_escalation", "meeting_agenda", "meeting_recap",
    "troubleshooting_summary", "executive_summary", "qbr_notes", "research_summary",
    "support_handoff", "general", "account_status_report", "weekly_summary",
    "monthly_summary", "customer_health_report", "qbr_report", "executive_update",
    "open_issues_report", "course_usage_report", "asset_metadata_report",
    "user_activity_report", "showpad_update_export",
}

REPORTING_IMPORT_TYPES = {"course_usage", "asset_metadata", "user_metadata", "general_export"}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def default_data_dir() -> Path:
    return Path.home() / ".tam-workbench"


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


class WorkbenchDB:
    def __init__(self, data_dir: str | Path | None = None):
        self.data_dir = Path(data_dir) if data_dir is not None else default_data_dir()
        self.db_path = self.data_dir / "tam_workbench.db"
        self.exports_dir = self.data_dir / "exports"
        self.templates_dir = self.data_dir / "templates"
        self.logs_dir = self.data_dir / "logs"
        self.reporting_dir = self.data_dir / "reporting"

    def initialize(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.exports_dir.mkdir(parents=True, exist_ok=True)
        self.templates_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.reporting_dir.mkdir(parents=True, exist_ok=True)
        config_path = self.data_dir / "config.yaml"
        if not config_path.exists():
            config_path.write_text(
                "# TAM Workbench local configuration\n"
                f"data_dir: {self.data_dir}\n"
                f"database: {self.db_path}\n"
                f"exports_dir: {self.exports_dir}\n"
                f"templates_dir: {self.templates_dir}\n"
                f"reporting_dir: {self.reporting_dir}\n",
                encoding="utf-8",
            )
        with self.connect() as conn:
            conn.executescript(SCHEMA)
            self._ensure_account_color_column(conn)
            self._ensure_archive_columns(conn)
            self._ensure_contact_relationship_columns(conn)
            conn.execute("INSERT OR REPLACE INTO metadata (key, value) VALUES ('schema_version', '4')")

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def query_all(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self.connect() as conn:
            return [dict(row) for row in conn.execute(sql, params).fetchall()]

    def query_one(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        with self.connect() as conn:
            return row_to_dict(conn.execute(sql, params).fetchone())

    def create_account(self, name: str, description: str = "", industry: str = "", region: str = "",
                       stakeholders: str = "", technical_context: str = "", business_context: str = "",
                       notes: str = "", account_color: str = "") -> dict[str, Any]:
        if not name or not name.strip():
            raise ValueError("account name is required")
        self._validate_hex_color(account_color)
        ts = now_iso()
        with self.connect() as conn:
            cur = conn.execute(
                """INSERT INTO accounts
                (name, description, industry, region, stakeholders, technical_context, business_context, notes, account_color, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (name.strip(), description, industry, region, stakeholders, technical_context, business_context, notes, account_color, ts, ts),
            )
            return self.get_account(cur.lastrowid, conn=conn)

    def get_account(self, account_id: int, conn: sqlite3.Connection | None = None) -> dict[str, Any]:
        row = self._fetch_one("SELECT * FROM accounts WHERE id = ?", (account_id,), conn)
        if row is None:
            raise KeyError(f"account not found: {account_id}")
        return row

    def list_accounts(self, limit: int = 100, include_archived: bool = False) -> list[dict[str, Any]]:
        where = "" if include_archived else "WHERE COALESCE(archived_at, '') = ''"
        return self.query_all(f"SELECT * FROM accounts {where} ORDER BY name LIMIT ?", (limit,))

    def update_account(self, account_id: int, **fields: Any) -> dict[str, Any]:
        allowed = {"name", "description", "industry", "region", "stakeholders", "technical_context", "business_context", "notes", "account_color"}
        updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
        if "account_color" in updates:
            self._validate_hex_color(str(updates["account_color"] or ""))
        if not updates:
            return self.get_account(account_id)
        updates["updated_at"] = now_iso()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        params = tuple(updates.values()) + (account_id,)
        with self.connect() as conn:
            conn.execute(f"UPDATE accounts SET {set_clause} WHERE id = ?", params)
            return self.get_account(account_id, conn=conn)

    def search_accounts(self, query: str, limit: int = 25, include_archived: bool = False) -> list[dict[str, Any]]:
        like = f"%{query}%"
        archive_clause = "" if include_archived else "AND COALESCE(archived_at, '') = ''"
        return self.query_all(
            """SELECT * FROM accounts WHERE (name LIKE ? OR description LIKE ? OR industry LIKE ? OR region LIKE ?
            OR stakeholders LIKE ? OR technical_context LIKE ? OR business_context LIKE ? OR notes LIKE ?)
            """ + archive_clause + " ORDER BY updated_at DESC LIMIT ?",
            (like, like, like, like, like, like, like, like, limit),
        )

    def archive_account(self, account_id: int) -> dict[str, Any]:
        self.get_account(account_id)
        ts = now_iso()
        with self.connect() as conn:
            conn.execute("UPDATE accounts SET archived_at = ?, updated_at = ? WHERE id = ?", (ts, ts, account_id))
            conn.execute("UPDATE tasks SET status = 'archived', updated_at = ? WHERE account_id = ?", (ts, account_id))
            conn.execute("UPDATE contacts SET archived_at = ?, updated_at = ? WHERE account_id = ?", (ts, ts, account_id))
            conn.execute("UPDATE notes SET archived_at = ?, updated_at = ? WHERE account_id = ?", (ts, ts, account_id))
            return self.get_account(account_id, conn=conn)

    def create_contact(self, account_id: int, name: str, email: str = "", role: str = "", title: str = "",
                       phone: str = "", notes: str = "", is_primary: bool | int = False,
                       support_level: str = "neutral", is_showpad_owner: bool | int = False) -> dict[str, Any]:
        if not name or not name.strip():
            raise ValueError("contact name is required")
        self.get_account(account_id)
        ts = now_iso()
        primary = 1 if bool(is_primary) else 0
        owner = 1 if bool(is_showpad_owner) else 0
        support_level = (support_level or "neutral").strip().lower()
        self._validate_choice("support_level", support_level, SUPPORT_LEVELS)
        with self.connect() as conn:
            if primary:
                conn.execute("UPDATE contacts SET is_primary = 0 WHERE account_id = ?", (account_id,))
            if owner:
                conn.execute("UPDATE contacts SET is_showpad_owner = 0 WHERE account_id = ?", (account_id,))
            cur = conn.execute(
                """INSERT INTO contacts
                (account_id, name, email, role, title, phone, notes, is_primary, support_level, is_showpad_owner, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (account_id, name.strip(), email.strip(), role, title, phone, notes, primary, support_level, owner, ts, ts),
            )
            return self.get_contact(cur.lastrowid, conn=conn)

    def get_contact(self, contact_id: int, conn: sqlite3.Connection | None = None) -> dict[str, Any]:
        row = self._fetch_one(
            """SELECT c.*, a.name AS account_name
            FROM contacts c LEFT JOIN accounts a ON a.id = c.account_id
            WHERE c.id = ?""",
            (contact_id,),
            conn,
        )
        if row is None:
            raise KeyError(f"contact not found: {contact_id}")
        return row

    def list_contacts(self, account_id: int | None = None, limit: int = 100, include_archived: bool = False) -> list[dict[str, Any]]:
        where, params = [], []
        if not include_archived:
            where.append("COALESCE(c.archived_at, '') = ''")
        if account_id is not None:
            where.append("c.account_id = ?"); params.append(account_id)
        sql = """SELECT c.*, a.name AS account_name
        FROM contacts c LEFT JOIN accounts a ON a.id = c.account_id"""
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY c.is_primary DESC, c.name COLLATE NOCASE LIMIT ?"
        params.append(limit)
        return self.query_all(sql, tuple(params))

    def update_contact(self, contact_id: int, **fields: Any) -> dict[str, Any]:
        allowed = {"account_id", "name", "email", "role", "title", "phone", "notes", "is_primary", "support_level", "is_showpad_owner"}
        updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
        if "name" in updates and not str(updates["name"]).strip():
            raise ValueError("contact name is required")
        if "email" in updates:
            updates["email"] = str(updates["email"]).strip()
        if "name" in updates:
            updates["name"] = str(updates["name"]).strip()
        if "is_primary" in updates:
            updates["is_primary"] = 1 if bool(updates["is_primary"]) else 0
        if "is_showpad_owner" in updates:
            updates["is_showpad_owner"] = 1 if bool(updates["is_showpad_owner"]) else 0
        if "support_level" in updates:
            updates["support_level"] = str(updates["support_level"] or "neutral").strip().lower()
            self._validate_choice("support_level", updates["support_level"], SUPPORT_LEVELS)
        if "account_id" in updates:
            self.get_account(int(updates["account_id"]))
        if not updates:
            return self.get_contact(contact_id)
        updates["updated_at"] = now_iso()
        with self.connect() as conn:
            existing = self.get_contact(contact_id, conn=conn)
            target_account_id = int(updates.get("account_id", existing["account_id"]))
            if updates.get("is_primary") == 1:
                conn.execute("UPDATE contacts SET is_primary = 0 WHERE account_id = ? AND id != ?", (target_account_id, contact_id))
            if updates.get("is_showpad_owner") == 1:
                conn.execute("UPDATE contacts SET is_showpad_owner = 0 WHERE account_id = ? AND id != ?", (target_account_id, contact_id))
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            params = tuple(updates.values()) + (contact_id,)
            conn.execute(f"UPDATE contacts SET {set_clause} WHERE id = ?", params)
            return self.get_contact(contact_id, conn=conn)

    def delete_contact(self, contact_id: int) -> dict[str, int]:
        self.archive_contact(contact_id)
        return {"deleted_contact_id": contact_id}

    def archive_contact(self, contact_id: int) -> dict[str, Any]:
        self.get_contact(contact_id)
        ts = now_iso()
        with self.connect() as conn:
            conn.execute("UPDATE contacts SET archived_at = ?, updated_at = ? WHERE id = ?", (ts, ts, contact_id))
            return self.get_contact(contact_id, conn=conn)

    def search_contacts(self, query: str, limit: int = 25, include_archived: bool = False) -> list[dict[str, Any]]:
        like = f"%{query}%"
        archive_clause = "" if include_archived else "AND COALESCE(c.archived_at, '') = ''"
        return self.query_all(
            """SELECT c.*, a.name AS account_name
            FROM contacts c LEFT JOIN accounts a ON a.id = c.account_id
            WHERE (c.name LIKE ? OR c.email LIKE ? OR c.role LIKE ? OR c.title LIKE ? OR c.phone LIKE ?
            OR c.notes LIKE ? OR c.support_level LIKE ? OR a.name LIKE ?)
            """ + archive_clause + """
            ORDER BY c.is_primary DESC, c.updated_at DESC LIMIT ?""",
            (like, like, like, like, like, like, like, like, limit),
        )

    def create_task(self, title: str, account_id: int | None = None, type: str = "general", status: str = "inbox",
                    priority: str = "normal", summary: str = "", details: str = "", next_action: str = "",
                    due_date: str | None = None) -> dict[str, Any]:
        if not title or not title.strip():
            raise ValueError("task title is required")
        self._validate_choice("type", type, TASK_TYPES)
        self._validate_choice("status", status, TASK_STATUSES)
        self._validate_choice("priority", priority, TASK_PRIORITIES)
        ts = now_iso()
        with self.connect() as conn:
            cur = conn.execute(
                """INSERT INTO tasks
                (title, account_id, type, status, priority, summary, details, next_action, due_date, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (title.strip(), account_id, type, status, priority, summary, details, next_action, due_date, ts, ts),
            )
            return self.get_task(cur.lastrowid, conn=conn)

    def get_task(self, task_id: int, conn: sqlite3.Connection | None = None) -> dict[str, Any]:
        row = self._fetch_one("SELECT * FROM tasks WHERE id = ?", (task_id,), conn)
        if row is None:
            raise KeyError(f"task not found: {task_id}")
        return row

    def list_tasks(self, status: str | None = None, account_id: int | None = None, limit: int = 100, include_archived: bool = False) -> list[dict[str, Any]]:
        where, params = [], []
        if not include_archived:
            where.append("status != 'archived'")
        if status:
            where.append("status = ?"); params.append(status)
        if account_id is not None:
            where.append("account_id = ?"); params.append(account_id)
        sql = "SELECT * FROM tasks" + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        return self.query_all(sql, tuple(params))

    def update_task(self, task_id: int, **fields: Any) -> dict[str, Any]:
        allowed = {"title", "account_id", "type", "status", "priority", "summary", "details", "next_action", "due_date"}
        updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
        if "type" in updates: self._validate_choice("type", updates["type"], TASK_TYPES)
        if "status" in updates: self._validate_choice("status", updates["status"], TASK_STATUSES)
        if "priority" in updates: self._validate_choice("priority", updates["priority"], TASK_PRIORITIES)
        if not updates:
            return self.get_task(task_id)
        updates["updated_at"] = now_iso()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        params = tuple(updates.values()) + (task_id,)
        with self.connect() as conn:
            conn.execute(f"UPDATE tasks SET {set_clause} WHERE id = ?", params)
            return self.get_task(task_id, conn=conn)

    def set_task_status(self, task_id: int, status: str) -> dict[str, Any]:
        return self.update_task(task_id, status=status)

    def delete_task(self, task_id: int) -> dict[str, int]:
        self.archive_task(task_id)
        return {"deleted_task_id": task_id}

    def archive_task(self, task_id: int) -> dict[str, Any]:
        self.get_task(task_id)
        return self.update_task(task_id, status="archived")

    def update_note(self, note_id: int, **fields: Any) -> dict[str, Any]:
        allowed = {"account_id", "task_id", "title", "body", "source"}
        updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
        if "account_id" in updates and updates["account_id"] is not None:
            self.get_account(int(updates["account_id"]))
        if "task_id" in updates and updates["task_id"] is not None:
            self.get_task(int(updates["task_id"]))
        if not updates:
            return self.get_note(note_id)
        updates["updated_at"] = now_iso()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        params = tuple(updates.values()) + (note_id,)
        with self.connect() as conn:
            conn.execute(f"UPDATE notes SET {set_clause} WHERE id = ?", params)
            return self.get_note(note_id, conn=conn)

    def delete_note(self, note_id: int) -> dict[str, int]:
        self.archive_note(note_id)
        return {"deleted_note_id": note_id}

    def archive_note(self, note_id: int) -> dict[str, Any]:
        self.get_note(note_id)
        ts = now_iso()
        with self.connect() as conn:
            conn.execute("UPDATE notes SET archived_at = ?, updated_at = ? WHERE id = ?", (ts, ts, note_id))
            return self.get_note(note_id, conn=conn)

    def search_tasks(self, query: str, limit: int = 25, include_archived: bool = False) -> list[dict[str, Any]]:
        like = f"%{query}%"
        archive_clause = "" if include_archived else "AND status != 'archived'"
        return self.query_all(
            """SELECT * FROM tasks WHERE (title LIKE ? OR type LIKE ? OR status LIKE ? OR priority LIKE ?
            OR summary LIKE ? OR details LIKE ? OR next_action LIKE ?) """ + archive_clause + " ORDER BY updated_at DESC LIMIT ?",
            (like, like, like, like, like, like, like, limit),
        )

    def create_note(self, account_id: int | None = None, task_id: int | None = None, title: str = "", body: str = "", source: str = "") -> dict[str, Any]:
        ts = now_iso()
        with self.connect() as conn:
            cur = conn.execute(
                "INSERT INTO notes (account_id, task_id, title, body, source, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (account_id, task_id, title, body, source, ts, ts),
            )
            return self.get_note(cur.lastrowid, conn=conn)

    def add_task_note(self, task_id: int, title: str = "", body: str = "", source: str = "") -> dict[str, Any]:
        task = self.get_task(task_id)
        return self.create_note(account_id=task.get("account_id"), task_id=task_id, title=title, body=body, source=source)

    def get_note(self, note_id: int, conn: sqlite3.Connection | None = None) -> dict[str, Any]:
        row = self._fetch_one("SELECT * FROM notes WHERE id = ?", (note_id,), conn)
        if row is None:
            raise KeyError(f"note not found: {note_id}")
        return row

    def list_notes(self, account_id: int | None = None, task_id: int | None = None, limit: int = 100, include_archived: bool = False) -> list[dict[str, Any]]:
        where, params = [], []
        if not include_archived:
            where.append("COALESCE(archived_at, '') = ''")
        if account_id is not None:
            where.append("account_id = ?"); params.append(account_id)
        if task_id is not None:
            where.append("task_id = ?"); params.append(task_id)
        sql = "SELECT * FROM notes" + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        return self.query_all(sql, tuple(params))

    def search_notes(self, query: str, limit: int = 25, include_archived: bool = False) -> list[dict[str, Any]]:
        like = f"%{query}%"
        archive_clause = "" if include_archived else "AND COALESCE(archived_at, '') = ''"
        return self.query_all("SELECT * FROM notes WHERE (title LIKE ? OR body LIKE ? OR source LIKE ?) " + archive_clause + " ORDER BY updated_at DESC LIMIT ?", (like, like, like, limit))

    def create_document(self, account_id: int | None = None, task_id: int | None = None, type: str = "general",
                        title: str = "", body: str = "") -> dict[str, Any]:
        self._validate_choice("type", type, DOCUMENT_TYPES)
        ts = now_iso()
        with self.connect() as conn:
            cur = conn.execute(
                "INSERT INTO documents (account_id, task_id, type, title, body, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (account_id, task_id, type, title, body, ts, ts),
            )
            return self.get_document(cur.lastrowid, conn=conn)

    def get_document(self, document_id: int, conn: sqlite3.Connection | None = None) -> dict[str, Any]:
        row = self._fetch_one("SELECT * FROM documents WHERE id = ?", (document_id,), conn)
        if row is None:
            raise KeyError(f"document not found: {document_id}")
        return row

    def list_documents(self, account_id: int | None = None, task_id: int | None = None, type: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        where, params = [], []
        if account_id is not None:
            where.append("account_id = ?"); params.append(account_id)
        if task_id is not None:
            where.append("task_id = ?"); params.append(task_id)
        if type:
            where.append("type = ?"); params.append(type)
        sql = "SELECT * FROM documents" + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        return self.query_all(sql, tuple(params))

    def update_document(self, document_id: int, **fields: Any) -> dict[str, Any]:
        allowed = {"account_id", "task_id", "type", "title", "body"}
        updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
        if "type" in updates: self._validate_choice("type", updates["type"], DOCUMENT_TYPES)
        if not updates:
            return self.get_document(document_id)
        updates["updated_at"] = now_iso()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        params = tuple(updates.values()) + (document_id,)
        with self.connect() as conn:
            conn.execute(f"UPDATE documents SET {set_clause} WHERE id = ?", params)
            return self.get_document(document_id, conn=conn)

    def export_document_markdown(self, document_id: int) -> Path:
        doc = self.get_document(document_id)
        safe_title = re.sub(r"[^A-Za-z0-9._-]+", "-", doc.get("title") or f"document-{document_id}").strip("-").lower()
        filename = f"{document_id}-{safe_title or 'document'}.md"
        path = self.exports_dir / filename
        path.write_text(doc.get("body") or "", encoding="utf-8")
        return path

    def get_account_context(self, account_id: int) -> dict[str, Any]:
        return {
            "account": self.get_account(account_id),
            "contacts": self.list_contacts(account_id=account_id),
            "tasks": self.list_tasks(account_id=account_id),
            "notes": self.list_notes(account_id=account_id),
            "documents": self.list_documents(account_id=account_id),
        }

    def get_task_context(self, task_id: int) -> dict[str, Any]:
        task = self.get_task(task_id)
        return {
            "task": task,
            "account": self.get_account(task["account_id"]) if task.get("account_id") else None,
            "notes": self.list_notes(task_id=task_id),
            "documents": self.list_documents(task_id=task_id),
        }

    def summarize_open_work(self) -> dict[str, Any]:
        open_statuses = ("inbox", "active", "waiting", "blocked")
        tasks = self.query_all(
            f"SELECT * FROM tasks WHERE status IN ({','.join('?' for _ in open_statuses)}) ORDER BY priority DESC, updated_at DESC",
            open_statuses,
        )
        return {"open_task_count": len(tasks), "tasks": tasks}

    def daily_work_snapshot(self) -> dict[str, Any]:
        urgent = self.query_all("SELECT * FROM tasks WHERE status NOT IN ('done','archived') AND priority = 'urgent' ORDER BY updated_at DESC")
        blocked = self.query_all("SELECT * FROM tasks WHERE status = 'blocked' ORDER BY updated_at DESC")
        waiting = self.query_all("SELECT * FROM tasks WHERE status = 'waiting' ORDER BY updated_at DESC")
        next_actions = self.query_all(
            """SELECT t.*, a.name AS account_name FROM tasks t LEFT JOIN accounts a ON a.id = t.account_id
            WHERE t.status NOT IN ('done','archived') AND COALESCE(t.next_action, '') != '' ORDER BY a.name, t.updated_at DESC"""
        )
        docs = self.query_all("SELECT * FROM documents ORDER BY updated_at DESC LIMIT 10")
        open_work = self.summarize_open_work()
        return {
            "open_task_count": open_work["open_task_count"],
            "urgent_tasks": urgent,
            "blocked_tasks": blocked,
            "waiting_tasks": waiting,
            "next_actions_by_account": next_actions,
            "recent_documents": docs,
        }


    def import_reporting_csv(self, file_path: str | Path, report_type: str, account_id: int | None = None,
                             label: str = "") -> dict[str, Any]:
        self._validate_choice("report_type", report_type, REPORTING_IMPORT_TYPES)
        source = Path(file_path).expanduser()
        if not source.exists() or not source.is_file():
            raise FileNotFoundError(f"CSV file not found: {source}")
        ts = now_iso()
        with source.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            columns = list(reader.fieldnames or [])
            if not columns:
                raise ValueError("CSV has no header row")
            rows = [dict(row) for row in reader]
        with self.connect() as conn:
            cur = conn.execute(
                """INSERT INTO reporting_imports
                (account_id, report_type, label, source_path, row_count, columns_json, imported_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (account_id, report_type, label, str(source), len(rows), json.dumps(columns), ts),
            )
            import_id = cur.lastrowid
            conn.executemany(
                "INSERT INTO reporting_rows (import_id, row_number, data_json) VALUES (?, ?, ?)",
                [(import_id, i + 1, json.dumps(row, ensure_ascii=False)) for i, row in enumerate(rows)],
            )
            return self.get_reporting_import(import_id, sample_size=5, conn=conn)

    def list_reporting_imports(self, report_type: str | None = None, account_id: int | None = None,
                               limit: int = 50) -> list[dict[str, Any]]:
        where, params = [], []
        if report_type:
            where.append("report_type = ?"); params.append(report_type)
        if account_id is not None:
            where.append("account_id = ?"); params.append(account_id)
        sql = "SELECT * FROM reporting_imports" + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY imported_at DESC LIMIT ?"
        params.append(limit)
        rows = self.query_all(sql, tuple(params))
        for row in rows:
            row["columns"] = json.loads(row.pop("columns_json") or "[]")
        return rows

    def get_reporting_import(self, import_id: int, sample_size: int = 10,
                             conn: sqlite3.Connection | None = None) -> dict[str, Any]:
        imp = self._fetch_one("SELECT * FROM reporting_imports WHERE id = ?", (import_id,), conn)
        if imp is None:
            raise KeyError(f"reporting import not found: {import_id}")
        imp["columns"] = json.loads(imp.pop("columns_json") or "[]")
        rows = self._fetch_all(
            "SELECT row_number, data_json FROM reporting_rows WHERE import_id = ? ORDER BY row_number LIMIT ?",
            (import_id, sample_size), conn,
        )
        imp["sample_rows"] = [{"row_number": r["row_number"], "data": json.loads(r["data_json"])} for r in rows]
        return imp

    def _reporting_rows(self, import_id: int) -> tuple[dict[str, Any], list[dict[str, str]]]:
        imp = self.get_reporting_import(import_id, sample_size=0)
        rows = self.query_all("SELECT data_json FROM reporting_rows WHERE import_id = ? ORDER BY row_number", (import_id,))
        return imp, [json.loads(r["data_json"]) for r in rows]

    def summarize_course_usage(self, import_id: int, user_column: str = "", course_column: str = "",
                               status_column: str = "", active_statuses: str = "completed,in progress,passed,started",
                               last_activity_column: str = "") -> dict[str, Any]:
        imp, rows = self._reporting_rows(import_id)
        columns = imp["columns"]
        user_col = _choose_column(columns, user_column, ["user id", "userid", "user_id", "email", "user email", "learner", "learner email"])
        course_col = _choose_column(columns, course_column, ["course id", "course_id", "course", "course title", "title", "path title"])
        status_col = _choose_column(columns, status_column, ["status", "completion status", "progress", "state"])
        activity_col = _choose_column(columns, last_activity_column, ["last activity", "last_activity", "last viewed", "completed at", "completion date", "updated at"])
        active_values = {v.strip().lower() for v in active_statuses.split(",") if v.strip()}
        users, courses, active_users = set(), set(), set()
        status_counts: dict[str, int] = {}
        course_counts: dict[str, int] = {}
        for row in rows:
            user = (row.get(user_col) or "").strip() if user_col else ""
            course = (row.get(course_col) or "").strip() if course_col else ""
            status = (row.get(status_col) or "").strip() if status_col else ""
            if user: users.add(user)
            if course:
                courses.add(course)
                course_counts[course] = course_counts.get(course, 0) + 1
            if status:
                status_counts[status] = status_counts.get(status, 0) + 1
            if user and ((status and status.lower() in active_values) or (activity_col and (row.get(activity_col) or "").strip())):
                active_users.add(user)
        return {
            "import_id": import_id,
            "row_count": len(rows),
            "detected_columns": {"user": user_col, "course": course_col, "status": status_col, "last_activity": activity_col},
            "unique_user_count": len(users),
            "unique_course_count": len(courses),
            "active_user_count": len(active_users),
            "active_users": sorted(active_users),
            "status_counts": dict(sorted(status_counts.items())),
            "top_courses_by_rows": sorted(course_counts.items(), key=lambda x: (-x[1], x[0]))[:25],
        }

    def summarize_user_activity(self, user_import_id: int, course_usage_import_id: int | None = None,
                                user_id_column: str = "", email_column: str = "", name_column: str = "",
                                active_column: str = "", last_login_column: str = "") -> dict[str, Any]:
        imp, rows = self._reporting_rows(user_import_id)
        columns = imp["columns"]
        user_col = _choose_column(columns, user_id_column, ["user id", "userid", "user_id", "id", "email", "user email"])
        email_col = _choose_column(columns, email_column, ["email", "user email", "email address", "mail"])
        name_col = _choose_column(columns, name_column, ["name", "full name", "user name", "firstname", "first name"])
        active_col = _choose_column(columns, active_column, ["active", "is active", "status", "state", "enabled"])
        login_col = _choose_column(columns, last_login_column, ["last login", "last_login", "last activity", "last active"])
        usage_users: set[str] = set()
        if course_usage_import_id is not None:
            usage_summary = self.summarize_course_usage(course_usage_import_id)
            usage_users = set(usage_summary["active_users"])
        inactive_values = {"false", "no", "0", "inactive", "disabled", "deactivated", "archived"}
        active, inactive = [], []
        for row in rows:
            identifiers = {v.strip() for v in [row.get(user_col, ""), row.get(email_col, "")] if v and v.strip()}
            explicit = (row.get(active_col) or "").strip().lower() if active_col else ""
            used_courses = bool(usage_users and identifiers.intersection(usage_users))
            is_active = used_courses or (bool(explicit) and explicit not in inactive_values) or (bool(login_col) and bool((row.get(login_col) or "").strip()))
            record = {"user_id": row.get(user_col, ""), "email": row.get(email_col, ""), "name": row.get(name_col, ""), "active_signal": explicit or ("course_usage" if used_courses else "")}
            (active if is_active else inactive).append(record)
        return {"import_id": user_import_id, "row_count": len(rows), "detected_columns": {"user_id": user_col, "email": email_col, "name": name_col, "active": active_col, "last_login": login_col}, "active_user_count": len(active), "inactive_user_count": len(inactive), "active_users": active[:200], "inactive_users": inactive[:200]}

    def summarize_asset_metadata(self, import_id: int, asset_id_column: str = "", title_column: str = "",
                                 type_column: str = "", owner_column: str = "", status_column: str = "") -> dict[str, Any]:
        imp, rows = self._reporting_rows(import_id)
        columns = imp["columns"]
        asset_col = _choose_column(columns, asset_id_column, ["asset id", "asset_id", "id", "content id"])
        title_col = _choose_column(columns, title_column, ["title", "name", "asset title", "content title"])
        type_col = _choose_column(columns, type_column, ["type", "asset type", "content type", "file type"])
        owner_col = _choose_column(columns, owner_column, ["owner", "created by", "author", "publisher"])
        status_col = _choose_column(columns, status_column, ["status", "state", "published", "visibility"])
        type_counts: dict[str, int] = {}
        status_counts: dict[str, int] = {}
        missing = []
        for idx, row in enumerate(rows, start=1):
            typ = (row.get(type_col) or "").strip() if type_col else ""
            status = (row.get(status_col) or "").strip() if status_col else ""
            if typ: type_counts[typ] = type_counts.get(typ, 0) + 1
            if status: status_counts[status] = status_counts.get(status, 0) + 1
            missing_fields = [name for name, col in {"asset_id": asset_col, "title": title_col, "type": type_col, "owner": owner_col}.items() if col and not (row.get(col) or "").strip()]
            if missing_fields:
                missing.append({"row_number": idx, "asset_id": row.get(asset_col, ""), "title": row.get(title_col, ""), "missing_fields": missing_fields})
        return {"import_id": import_id, "row_count": len(rows), "detected_columns": {"asset_id": asset_col, "title": title_col, "type": type_col, "owner": owner_col, "status": status_col}, "type_counts": dict(sorted(type_counts.items())), "status_counts": dict(sorted(status_counts.items())), "missing_metadata_count": len(missing), "missing_metadata_rows": missing[:200]}

    def export_showpad_update_csv(self, source_import_id: int, output_name: str = "showpad-update.csv",
                                  columns: str = "", filters_json: str = "{}", updates_json: str = "{}") -> dict[str, Any]:
        imp, rows = self._reporting_rows(source_import_id)
        filters = json.loads(filters_json or "{}")
        updates = json.loads(updates_json or "{}")
        selected = [c.strip() for c in columns.split(",") if c.strip()] or list(imp["columns"])
        for col in updates:
            if col not in selected:
                selected.append(col)
        filtered = []
        for row in rows:
            if all(str(row.get(k, "")) == str(v) for k, v in filters.items()):
                out = {col: row.get(col, "") for col in selected}
                out.update(updates)
                filtered.append(out)
        safe_name = re.sub(r"[^A-Za-z0-9._-]+", "-", output_name).strip("-") or "showpad-update.csv"
        if not safe_name.lower().endswith(".csv"):
            safe_name += ".csv"
        path = self.exports_dir / safe_name
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=selected)
            writer.writeheader()
            writer.writerows(filtered)
        return {"path": str(path), "row_count": len(filtered), "columns": selected, "filters": filters, "updates": updates}

    def _fetch_one(self, sql: str, params: tuple[Any, ...], conn: sqlite3.Connection | None) -> dict[str, Any] | None:
        if conn is not None:
            return row_to_dict(conn.execute(sql, params).fetchone())
        return self.query_one(sql, params)

    def _validate_choice(self, field: str, value: str, choices: set[str]) -> None:
        if value not in choices:
            raise ValueError(f"invalid {field}: {value}. Expected one of: {', '.join(sorted(choices))}")

    def _validate_hex_color(self, value: str) -> None:
        if value and not re.fullmatch(r"#[0-9A-Fa-f]{6}", value):
            raise ValueError("account_color must be an empty string or a #RRGGBB hex color")

    def _ensure_account_color_column(self, conn: sqlite3.Connection) -> None:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(accounts)").fetchall()}
        if "account_color" not in columns:
            conn.execute("ALTER TABLE accounts ADD COLUMN account_color TEXT NOT NULL DEFAULT ''")

    def _ensure_archive_columns(self, conn: sqlite3.Connection) -> None:
        for table in ["accounts", "contacts", "notes"]:
            columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
            if "archived_at" not in columns:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN archived_at TEXT NOT NULL DEFAULT ''")

    def _ensure_contact_relationship_columns(self, conn: sqlite3.Connection) -> None:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(contacts)").fetchall()}
        if "support_level" not in columns:
            conn.execute("ALTER TABLE contacts ADD COLUMN support_level TEXT NOT NULL DEFAULT 'neutral'")
            conn.execute(
                """UPDATE contacts
                SET support_level = CASE
                    WHEN is_primary = 1 OR LOWER(COALESCE(role, '') || ' ' || COALESCE(title, '') || ' ' || COALESCE(notes, '')) LIKE '%champion%'
                         OR LOWER(COALESCE(role, '') || ' ' || COALESCE(title, '') || ' ' || COALESCE(notes, '')) LIKE '%sponsor%'
                    THEN 'champion'
                    WHEN LOWER(COALESCE(role, '') || ' ' || COALESCE(title, '') || ' ' || COALESCE(notes, '')) LIKE '%detractor%'
                         OR LOWER(COALESCE(role, '') || ' ' || COALESCE(title, '') || ' ' || COALESCE(notes, '')) LIKE '%blocker%'
                    THEN 'detractor'
                    ELSE 'neutral'
                END"""
            )
        if "is_showpad_owner" not in columns:
            conn.execute("ALTER TABLE contacts ADD COLUMN is_showpad_owner INTEGER NOT NULL DEFAULT 0")


    def _fetch_all(self, sql: str, params: tuple[Any, ...], conn: sqlite3.Connection | None) -> list[dict[str, Any]]:
        if conn is not None:
            return [dict(row) for row in conn.execute(sql, params).fetchall()]
        return self.query_all(sql, params)


def _choose_column(columns: list[str], preferred: str, aliases: list[str]) -> str:
    if preferred:
        if preferred in columns:
            return preferred
        lowered = {c.lower(): c for c in columns}
        if preferred.lower() in lowered:
            return lowered[preferred.lower()]
        return preferred
    normalized = {_normalize_column(c): c for c in columns}
    for alias in aliases:
        key = _normalize_column(alias)
        if key in normalized:
            return normalized[key]
    for col in columns:
        ncol = _normalize_column(col)
        if any(_normalize_column(alias) in ncol for alias in aliases):
            return col
    return ""


def _normalize_column(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


SCHEMA = """
CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    industry TEXT NOT NULL DEFAULT '',
    region TEXT NOT NULL DEFAULT '',
    stakeholders TEXT NOT NULL DEFAULT '',
    technical_context TEXT NOT NULL DEFAULT '',
    business_context TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    account_color TEXT NOT NULL DEFAULT '',
    archived_at TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    email TEXT NOT NULL DEFAULT '',
    role TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    is_primary INTEGER NOT NULL DEFAULT 0,
    support_level TEXT NOT NULL DEFAULT 'neutral',
    is_showpad_owner INTEGER NOT NULL DEFAULT 0,
    archived_at TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    account_id INTEGER REFERENCES accounts(id) ON DELETE SET NULL,
    type TEXT NOT NULL DEFAULT 'general',
    status TEXT NOT NULL DEFAULT 'inbox',
    priority TEXT NOT NULL DEFAULT 'normal',
    summary TEXT NOT NULL DEFAULT '',
    details TEXT NOT NULL DEFAULT '',
    next_action TEXT NOT NULL DEFAULT '',
    due_date TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER REFERENCES accounts(id) ON DELETE SET NULL,
    task_id INTEGER REFERENCES tasks(id) ON DELETE SET NULL,
    title TEXT NOT NULL DEFAULT '',
    body TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT '',
    archived_at TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER REFERENCES accounts(id) ON DELETE SET NULL,
    task_id INTEGER REFERENCES tasks(id) ON DELETE SET NULL,
    type TEXT NOT NULL DEFAULT 'general',
    title TEXT NOT NULL DEFAULT '',
    body TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);


CREATE TABLE IF NOT EXISTS reporting_imports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER REFERENCES accounts(id) ON DELETE SET NULL,
    report_type TEXT NOT NULL,
    label TEXT NOT NULL DEFAULT '',
    source_path TEXT NOT NULL,
    row_count INTEGER NOT NULL,
    columns_json TEXT NOT NULL,
    imported_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reporting_rows (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    import_id INTEGER NOT NULL REFERENCES reporting_imports(id) ON DELETE CASCADE,
    row_number INTEGER NOT NULL,
    data_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_accounts_name ON accounts(name);
CREATE INDEX IF NOT EXISTS idx_contacts_account_id ON contacts(account_id);
CREATE INDEX IF NOT EXISTS idx_contacts_email ON contacts(email);
CREATE INDEX IF NOT EXISTS idx_tasks_account_id ON tasks(account_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_notes_account_task ON notes(account_id, task_id);
CREATE INDEX IF NOT EXISTS idx_documents_account_task ON documents(account_id, task_id);
CREATE INDEX IF NOT EXISTS idx_reporting_imports_type ON reporting_imports(report_type);
CREATE INDEX IF NOT EXISTS idx_reporting_rows_import ON reporting_rows(import_id);
"""
