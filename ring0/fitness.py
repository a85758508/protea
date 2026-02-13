"""Fitness tracker backed by SQLite.

Records and queries fitness scores for every generation in the
self-evolving lifecycle.  Pure stdlib — no external dependencies.
"""

from __future__ import annotations

import pathlib
import sqlite3

_CREATE_TABLE = """\
CREATE TABLE IF NOT EXISTS fitness_log (
    id          INTEGER PRIMARY KEY,
    generation  INTEGER  NOT NULL,
    commit_hash TEXT     NOT NULL,
    score       REAL     NOT NULL,
    runtime_sec REAL     NOT NULL,
    survived    BOOLEAN  NOT NULL,
    timestamp   TEXT     DEFAULT CURRENT_TIMESTAMP
)
"""


class FitnessTracker:
    """Evaluate and record fitness scores in a local SQLite database."""

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
        return dict(row)

    def record(
        self,
        generation: int,
        commit_hash: str,
        score: float,
        runtime_sec: float,
        survived: bool,
    ) -> int:
        """Insert a fitness entry and return its *rowid*."""
        with self._connect() as con:
            cur = con.execute(
                "INSERT INTO fitness_log "
                "(generation, commit_hash, score, runtime_sec, survived) "
                "VALUES (?, ?, ?, ?, ?)",
                (generation, commit_hash, score, runtime_sec, survived),
            )
            return cur.lastrowid  # type: ignore[return-value]

    def get_best(self, n: int = 5) -> list[dict]:
        """Return the top *n* entries ordered by score descending."""
        with self._connect() as con:
            rows = con.execute(
                "SELECT * FROM fitness_log ORDER BY score DESC LIMIT ?",
                (n,),
            ).fetchall()
            return [self._row_to_dict(r) for r in rows]

    def get_generation_stats(self, generation: int) -> dict | None:
        """Return aggregate stats for a single generation.

        Returns a dict with keys *avg_score*, *max_score*, *min_score*,
        and *count*, or ``None`` if the generation has no entries.
        """
        with self._connect() as con:
            row = con.execute(
                "SELECT AVG(score) AS avg_score, MAX(score) AS max_score, "
                "MIN(score) AS min_score, COUNT(*) AS count "
                "FROM fitness_log WHERE generation = ?",
                (generation,),
            ).fetchone()
            if row is None or row["count"] == 0:
                return None
            return self._row_to_dict(row)

    def get_history(self, limit: int = 50) -> list[dict]:
        """Return the most recent entries ordered by *id* descending."""
        with self._connect() as con:
            rows = con.execute(
                "SELECT * FROM fitness_log ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [self._row_to_dict(r) for r in rows]
