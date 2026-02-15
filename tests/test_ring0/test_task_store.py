"""Tests for ring0.task_store."""

from __future__ import annotations

import time

import pytest

from ring0.task_store import TaskStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def store(tmp_path):
    return TaskStore(tmp_path / "tasks.db")


# ---------------------------------------------------------------------------
# TestInit
# ---------------------------------------------------------------------------

class TestInit:
    def test_creates_table(self, tmp_path):
        store = TaskStore(tmp_path / "tasks.db")
        assert store.count() == 0

    def test_idempotent_init(self, tmp_path):
        db = tmp_path / "tasks.db"
        TaskStore(db)
        TaskStore(db)  # second init should not raise

    def test_db_path_stored(self, tmp_path):
        db = tmp_path / "tasks.db"
        store = TaskStore(db)
        assert store.db_path == db


# ---------------------------------------------------------------------------
# TestAdd
# ---------------------------------------------------------------------------

class TestAdd:
    def test_add_returns_rowid(self, store):
        rowid = store.add("t-1", "hello", "chat-1")
        assert rowid >= 1

    def test_add_increments_count(self, store):
        store.add("t-1", "a", "c1")
        store.add("t-2", "b", "c2")
        assert store.count() == 2

    def test_add_with_explicit_created_at(self, store):
        store.add("t-1", "text", "c1", created_at=1000.0)
        rows = store.get_recent(1)
        assert rows[0]["created_at"] == 1000.0

    def test_add_defaults_created_at(self, store):
        before = time.time()
        store.add("t-1", "text", "c1")
        after = time.time()
        rows = store.get_recent(1)
        assert before <= rows[0]["created_at"] <= after

    def test_add_duplicate_task_id_raises(self, store):
        store.add("t-1", "a", "c1")
        with pytest.raises(Exception):  # sqlite3.IntegrityError
            store.add("t-1", "b", "c2")

    def test_add_default_status_is_pending(self, store):
        store.add("t-1", "text", "c1")
        rows = store.get_recent(1)
        assert rows[0]["status"] == "pending"

    def test_add_default_result_is_empty(self, store):
        store.add("t-1", "text", "c1")
        rows = store.get_recent(1)
        assert rows[0]["result"] == ""

    def test_add_default_completed_at_is_none(self, store):
        store.add("t-1", "text", "c1")
        rows = store.get_recent(1)
        assert rows[0]["completed_at"] is None


# ---------------------------------------------------------------------------
# TestGetPending
# ---------------------------------------------------------------------------

class TestGetPending:
    def test_empty(self, store):
        assert store.get_pending() == []

    def test_returns_pending_only(self, store):
        store.add("t-1", "a", "c1")
        store.add("t-2", "b", "c1")
        store.set_status("t-2", "executing")
        pending = store.get_pending()
        assert len(pending) == 1
        assert pending[0]["task_id"] == "t-1"

    def test_ordered_by_created_at_asc(self, store):
        store.add("t-1", "first", "c1", created_at=200.0)
        store.add("t-2", "second", "c1", created_at=100.0)
        pending = store.get_pending()
        assert pending[0]["task_id"] == "t-2"
        assert pending[1]["task_id"] == "t-1"


# ---------------------------------------------------------------------------
# TestGetExecuting
# ---------------------------------------------------------------------------

class TestGetExecuting:
    def test_empty(self, store):
        assert store.get_executing() == []

    def test_returns_executing_only(self, store):
        store.add("t-1", "a", "c1")
        store.add("t-2", "b", "c1")
        store.set_status("t-1", "executing")
        executing = store.get_executing()
        assert len(executing) == 1
        assert executing[0]["task_id"] == "t-1"


# ---------------------------------------------------------------------------
# TestSetStatus
# ---------------------------------------------------------------------------

class TestSetStatus:
    def test_set_executing(self, store):
        store.add("t-1", "text", "c1")
        store.set_status("t-1", "executing")
        assert len(store.get_executing()) == 1
        assert len(store.get_pending()) == 0

    def test_set_completed_with_result(self, store):
        store.add("t-1", "text", "c1")
        store.set_status("t-1", "completed", "done!")
        rows = store.get_recent(1)
        assert rows[0]["status"] == "completed"
        assert rows[0]["result"] == "done!"
        assert rows[0]["completed_at"] is not None

    def test_set_failed(self, store):
        store.add("t-1", "text", "c1")
        store.set_status("t-1", "failed", "error msg")
        rows = store.get_recent(1)
        assert rows[0]["status"] == "failed"
        assert rows[0]["result"] == "error msg"
        assert rows[0]["completed_at"] is not None

    def test_set_pending_no_completed_at(self, store):
        store.add("t-1", "text", "c1")
        store.set_status("t-1", "executing")
        store.set_status("t-1", "pending")
        rows = store.get_recent(1)
        assert rows[0]["status"] == "pending"


# ---------------------------------------------------------------------------
# TestGetRecent
# ---------------------------------------------------------------------------

class TestGetRecent:
    def test_empty(self, store):
        assert store.get_recent() == []

    def test_returns_most_recent_first(self, store):
        store.add("t-1", "first", "c1", created_at=100.0)
        store.add("t-2", "second", "c1", created_at=200.0)
        recent = store.get_recent(5)
        assert recent[0]["task_id"] == "t-2"
        assert recent[1]["task_id"] == "t-1"

    def test_respects_limit(self, store):
        for i in range(10):
            store.add(f"t-{i}", f"task {i}", "c1", created_at=float(i))
        recent = store.get_recent(3)
        assert len(recent) == 3

    def test_includes_all_statuses(self, store):
        store.add("t-1", "a", "c1", created_at=100.0)
        store.add("t-2", "b", "c1", created_at=200.0)
        store.set_status("t-1", "completed", "done")
        recent = store.get_recent(5)
        assert len(recent) == 2


# ---------------------------------------------------------------------------
# TestCountPending
# ---------------------------------------------------------------------------

class TestCountPending:
    def test_zero_when_empty(self, store):
        assert store.count_pending() == 0

    def test_counts_only_pending(self, store):
        store.add("t-1", "a", "c1")
        store.add("t-2", "b", "c1")
        store.set_status("t-1", "executing")
        assert store.count_pending() == 1

    def test_after_completion(self, store):
        store.add("t-1", "a", "c1")
        store.set_status("t-1", "completed", "done")
        assert store.count_pending() == 0


# ---------------------------------------------------------------------------
# TestCount
# ---------------------------------------------------------------------------

class TestCount:
    def test_zero_when_empty(self, store):
        assert store.count() == 0

    def test_counts_all(self, store):
        store.add("t-1", "a", "c1")
        store.add("t-2", "b", "c1")
        store.set_status("t-1", "completed", "done")
        assert store.count() == 2


# ---------------------------------------------------------------------------
# TestClear
# ---------------------------------------------------------------------------

class TestClear:
    def test_clear_empties_store(self, store):
        store.add("t-1", "a", "c1")
        store.add("t-2", "b", "c1")
        store.clear()
        assert store.count() == 0
        assert store.get_pending() == []

    def test_clear_on_empty_store(self, store):
        store.clear()  # should not raise
        assert store.count() == 0


# ---------------------------------------------------------------------------
# TestFieldValues
# ---------------------------------------------------------------------------

class TestFieldValues:
    def test_all_fields_round_trip(self, store):
        store.add("t-abc", "my task", "chat-99", created_at=12345.0)
        rows = store.get_recent(1)
        r = rows[0]
        assert r["task_id"] == "t-abc"
        assert r["text"] == "my task"
        assert r["chat_id"] == "chat-99"
        assert r["created_at"] == 12345.0
        assert r["status"] == "pending"
        assert r["result"] == ""
        assert r["completed_at"] is None
