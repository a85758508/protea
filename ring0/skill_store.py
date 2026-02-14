"""Skill store backed by SQLite.

Stores prompt templates and structured descriptions for reusable skills.
Pure stdlib — no external dependencies.
"""

from __future__ import annotations

import json
import pathlib
import sqlite3

_CREATE_TABLE = """\
CREATE TABLE IF NOT EXISTS skills (
    id              INTEGER PRIMARY KEY,
    name            TEXT     NOT NULL UNIQUE,
    description     TEXT     NOT NULL,
    prompt_template TEXT     NOT NULL,
    parameters      TEXT     DEFAULT '{}',
    tags            TEXT     DEFAULT '[]',
    source          TEXT     NOT NULL DEFAULT 'user',
    usage_count     INTEGER  DEFAULT 0,
    active          BOOLEAN  DEFAULT 1,
    created_at      TEXT     DEFAULT CURRENT_TIMESTAMP
)
"""


class SkillStore:
    """Store and retrieve skills in a local SQLite database."""

    def __init__(self, db_path: pathlib.Path) -> None:
        self.db_path = db_path
        with self._connect() as con:
            con.execute(_CREATE_TABLE)

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(str(self.db_path))
        con.row_factory = sqlite3.Row
        return con

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict:
        d = dict(row)
        for key in ("parameters", "tags"):
            if key in d and isinstance(d[key], str):
                try:
                    d[key] = json.loads(d[key])
                except (json.JSONDecodeError, TypeError):
                    d[key] = {} if key == "parameters" else []
        d["active"] = bool(d.get("active", 1))
        return d

    def add(
        self,
        name: str,
        description: str,
        prompt_template: str,
        parameters: dict | None = None,
        tags: list[str] | None = None,
        source: str = "user",
    ) -> int:
        """Insert a skill and return its rowid."""
        params_json = json.dumps(parameters or {})
        tags_json = json.dumps(tags or [])
        with self._connect() as con:
            cur = con.execute(
                "INSERT INTO skills "
                "(name, description, prompt_template, parameters, tags, source) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (name, description, prompt_template, params_json, tags_json, source),
            )
            return cur.lastrowid  # type: ignore[return-value]

    def get_by_name(self, name: str) -> dict | None:
        """Return a skill by name, or None if not found."""
        with self._connect() as con:
            row = con.execute(
                "SELECT * FROM skills WHERE name = ?", (name,)
            ).fetchone()
            if row is None:
                return None
            return self._row_to_dict(row)

    def get_active(self, limit: int = 50) -> list[dict]:
        """Return active skills ordered by usage count descending."""
        with self._connect() as con:
            rows = con.execute(
                "SELECT * FROM skills WHERE active = 1 "
                "ORDER BY usage_count DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [self._row_to_dict(r) for r in rows]

    def update_usage(self, name: str) -> None:
        """Increment the usage count for a skill."""
        with self._connect() as con:
            con.execute(
                "UPDATE skills SET usage_count = usage_count + 1 WHERE name = ?",
                (name,),
            )

    def deactivate(self, name: str) -> None:
        """Deactivate a skill by name."""
        with self._connect() as con:
            con.execute(
                "UPDATE skills SET active = 0 WHERE name = ?", (name,),
            )

    def count(self) -> int:
        """Return total number of skills."""
        with self._connect() as con:
            row = con.execute("SELECT COUNT(*) AS cnt FROM skills").fetchone()
            return row["cnt"]

    def clear(self) -> None:
        """Delete all skills."""
        with self._connect() as con:
            con.execute("DELETE FROM skills")
