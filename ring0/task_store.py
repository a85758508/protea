"""Task store backed by SQLite.

Persists user tasks across restarts so queued work survives os.execv().
Pure stdlib — no external dependencies.
"""

from __future__ import annotations

import pathlib
import sqlite3
import time

_CREATE_TABLE = """\
CREATE TABLE IF NOT EXISTS tasks (
    id           INTEGER PRIMARY KEY,
    task_id      TEXT    NOT NULL UNIQUE,
    text         TEXT    NOT NULL,
    chat_id      TEXT    NOT NULL,
    created_at   REAL    NOT NULL,
    status       TEXT    NOT NULL DEFAULT 'pending',
    result       TEXT    DEFAULT '',
    completed_at REAL    DEFAULT NULL
)
"""


class TaskStore:
    """Store and retrieve tasks in a local SQLite database."""

    def __init__(self, db_path: pathlib.Path) -> None:
        self.db_path = db_path
        with self._connect() as con:
            con.execute(_CREATE_TABLE)

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(str(self.db_path))
        con.row_factory = sqlite3.Row
        return con

    def add(
        self,
        task_id: str,
        text: str,
        chat_id: str,
        created_at: float | None = None,
    ) -> int:
        """Insert a task and return its rowid."""
        if created_at is None:
            created_at = time.time()
        with self._connect() as con:
            cur = con.execute(
                "INSERT INTO tasks (task_id, text, chat_id, created_at) "
                "VALUES (?, ?, ?, ?)",
                (task_id, text, chat_id, created_at),
            )
            return cur.lastrowid  # type: ignore[return-value]

    def get_pending(self) -> list[dict]:
        """Return all tasks with status 'pending', oldest first."""
        with self._connect() as con:
            rows = con.execute(
                "SELECT * FROM tasks WHERE status = 'pending' "
                "ORDER BY created_at ASC",
            ).fetchall()
            return [dict(r) for r in rows]

    def get_executing(self) -> list[dict]:
        """Return all tasks with status 'executing'."""
        with self._connect() as con:
            rows = con.execute(
                "SELECT * FROM tasks WHERE status = 'executing' "
                "ORDER BY created_at ASC",
            ).fetchall()
            return [dict(r) for r in rows]

    def set_status(
        self,
        task_id: str,
        status: str,
        result: str = "",
    ) -> None:
        """Update the status (and optionally result) of a task."""
        with self._connect() as con:
            if status in ("completed", "failed"):
                con.execute(
                    "UPDATE tasks SET status = ?, result = ?, completed_at = ? "
                    "WHERE task_id = ?",
                    (status, result, time.time(), task_id),
                )
            else:
                con.execute(
                    "UPDATE tasks SET status = ? WHERE task_id = ?",
                    (status, task_id),
                )

    def get_recent(self, limit: int = 5) -> list[dict]:
        """Return the most recent tasks ordered by created_at descending."""
        with self._connect() as con:
            rows = con.execute(
                "SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    def count_pending(self) -> int:
        """Return number of pending tasks."""
        with self._connect() as con:
            row = con.execute(
                "SELECT COUNT(*) AS cnt FROM tasks WHERE status = 'pending'",
            ).fetchone()
            return row["cnt"]

    def count(self) -> int:
        """Return total number of tasks."""
        with self._connect() as con:
            row = con.execute("SELECT COUNT(*) AS cnt FROM tasks").fetchone()
            return row["cnt"]

    def clear(self) -> None:
        """Delete all tasks."""
        with self._connect() as con:
            con.execute("DELETE FROM tasks")
