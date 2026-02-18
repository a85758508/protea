"""Tests for ring0.sqlite_store — SQLiteStore base class."""

import pathlib
import sqlite3

import pytest

from ring0.sqlite_store import SQLiteStore


_TEST_TABLE = """\
CREATE TABLE IF NOT EXISTS test_items (
    id   INTEGER PRIMARY KEY,
    name TEXT NOT NULL
)
"""


class ConcreteStore(SQLiteStore):
    """Minimal subclass for testing the base class."""

    _TABLE_NAME = "test_items"
    _CREATE_TABLE = _TEST_TABLE
    _migrated = False

    def _migrate(self, con: sqlite3.Connection) -> None:
        ConcreteStore._migrated = True


class TestSQLiteStore:
    @pytest.fixture(autouse=True)
    def store(self, tmp_path):
        ConcreteStore._migrated = False
        self.store = ConcreteStore(tmp_path / "test.db")

    def test_table_created(self):
        with self.store._connect() as con:
            row = con.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='test_items'"
            ).fetchone()
            assert row is not None

    def test_migrate_called(self):
        assert ConcreteStore._migrated is True

    def test_count_empty(self):
        assert self.store.count() == 0

    def test_count_after_insert(self):
        with self.store._connect() as con:
            con.execute("INSERT INTO test_items (name) VALUES ('a')")
            con.execute("INSERT INTO test_items (name) VALUES ('b')")
        assert self.store.count() == 2

    def test_clear(self):
        with self.store._connect() as con:
            con.execute("INSERT INTO test_items (name) VALUES ('a')")
        assert self.store.count() == 1
        self.store.clear()
        assert self.store.count() == 0

    def test_row_to_dict(self):
        with self.store._connect() as con:
            con.execute("INSERT INTO test_items (name) VALUES ('hello')")
            row = con.execute("SELECT * FROM test_items").fetchone()
        d = self.store._row_to_dict(row)
        assert isinstance(d, dict)
        assert d["name"] == "hello"

    def test_connect_returns_row_factory(self):
        con = self.store._connect()
        assert con.row_factory is sqlite3.Row
        con.close()
