"""SQLite helpers for persisting sprints and tasks."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from data import sprints as seed_sprints

DB_PATH = Path(__file__).with_name("app.db")


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_db() -> None:
    """Create tables and seed initial data if empty."""
    with get_connection() as conn:
        _create_tables(conn)
        cur = conn.execute("SELECT COUNT(*) AS c FROM sprints")
        if cur.fetchone()["c"] == 0:
            _seed(conn)


def _create_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        PRAGMA foreign_keys = ON;
        CREATE TABLE IF NOT EXISTS sprints (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            start DATE NOT NULL,
            end DATE NOT NULL,
            overview TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY,
            sprint_id INTEGER NOT NULL REFERENCES sprints(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            done BOOLEAN NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS goals (
            id INTEGER PRIMARY KEY,
            sprint_id INTEGER NOT NULL REFERENCES sprints(id) ON DELETE CASCADE,
            text TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS acceptance (
            id INTEGER PRIMARY KEY,
            sprint_id INTEGER NOT NULL REFERENCES sprints(id) ON DELETE CASCADE,
            text TEXT NOT NULL
        );
        """
    )


def _seed(conn: sqlite3.Connection) -> None:
    """Load initial data from data.py into the database."""
    for sprint in seed_sprints:
        conn.execute(
            """
            INSERT INTO sprints (id, name, start, end, overview)
            VALUES (?, ?, ?, ?, ?)
            """,
            (sprint.id, sprint.name, sprint.start, sprint.end, sprint.overview),
        )
        for task in sprint.tasks:
            conn.execute(
                """
                INSERT INTO tasks (id, sprint_id, title, done)
                VALUES (?, ?, ?, ?)
                """,
                (task.id, sprint.id, task.title, int(task.done)),
            )
        for goal in sprint.goals:
            conn.execute(
                "INSERT INTO goals (sprint_id, text) VALUES (?, ?)",
                (sprint.id, goal),
            )
        for criterion in sprint.acceptance:
            conn.execute(
                "INSERT INTO acceptance (sprint_id, text) VALUES (?, ?)",
                (sprint.id, criterion),
            )


def fetch_sprints() -> List[Dict[str, Any]]:
    with get_connection() as conn:
        sprint_rows = conn.execute(
            "SELECT id, name, start, end, overview FROM sprints ORDER BY start"
        ).fetchall()
        return [_attach_children(conn, row) for row in sprint_rows]


def fetch_sprint(sprint_id: int) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, name, start, end, overview FROM sprints WHERE id = ?",
            (sprint_id,),
        ).fetchone()
        if not row:
            return None
        return _attach_children(conn, row)


def _attach_children(conn: sqlite3.Connection, row: sqlite3.Row) -> Dict[str, Any]:
    sprint_id = row["id"]
    tasks = conn.execute(
        "SELECT id, title, done FROM tasks WHERE sprint_id = ? ORDER BY id",
        (sprint_id,),
    ).fetchall()
    goals = conn.execute(
        "SELECT text FROM goals WHERE sprint_id = ? ORDER BY id",
        (sprint_id,),
    ).fetchall()
    acceptance = conn.execute(
        "SELECT text FROM acceptance WHERE sprint_id = ? ORDER BY id",
        (sprint_id,),
    ).fetchall()
    return {
        "id": row["id"],
        "name": row["name"],
        "start": row["start"],
        "end": row["end"],
        "overview": row["overview"],
        "tasks": [{"id": t["id"], "title": t["title"], "done": bool(t["done"])} for t in tasks],
        "goals": [g["text"] for g in goals],
        "acceptance": [a["text"] for a in acceptance],
    }


def toggle_task(sprint_id: int, task_id: int) -> bool:
    """Flip the done flag for a task. Returns True if a row was updated."""
    with get_connection() as conn:
        cur = conn.execute(
            """
            UPDATE tasks
            SET done = NOT done
            WHERE id = ? AND sprint_id = ?
            """,
            (task_id, sprint_id),
        )
        return cur.rowcount > 0
