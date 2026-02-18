"""SQLite store base class — shared boilerplate for all Ring 0 stores.

Extracts the repeated _connect / count / clear / _row_to_dict / _migrate
pattern used by MemoryStore, FitnessTracker, SkillStore, TaskStore, and
GenePool.  Pure stdlib — no external dependencies.
"""

from __future__ import annotations

import pathlib
import sqlite3


class SQLiteStore:
    """Base class for SQLite-backed stores."""

    _TABLE_NAME: str = ""       # subclass must set
    _CREATE_TABLE: str = ""     # subclass must set

    def __init__(self, db_path: pathlib.Path) -> None:
        self.db_path = db_path
        with self._connect() as con:
            con.execute(self._CREATE_TABLE)
            self._migrate(con)

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(str(self.db_path))
        con.row_factory = sqlite3.Row
        return con

    def _migrate(self, con: sqlite3.Connection) -> None:
        """Override in subclasses that need schema migrations."""

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict:
        return dict(row)

    def count(self) -> int:
        """Return total number of rows in the table."""
        with self._connect() as con:
            row = con.execute(
                f"SELECT COUNT(*) AS cnt FROM {self._TABLE_NAME}",
            ).fetchone()
            return row["cnt"]

    def clear(self) -> None:
        """Delete all rows from the table."""
        with self._connect() as con:
            con.execute(f"DELETE FROM {self._TABLE_NAME}")
