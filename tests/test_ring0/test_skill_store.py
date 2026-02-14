"""Tests for ring0.skill_store — SkillStore."""

from __future__ import annotations

import sqlite3

import pytest

from ring0.skill_store import SkillStore


class TestAdd:
    """add() should insert rows and return their rowid."""

    def test_insert_returns_rowid(self, tmp_path):
        store = SkillStore(tmp_path / "skills.db")
        rid = store.add("greet", "Greeting skill", "Hello {{name}}")
        assert rid == 1

    def test_successive_inserts_increment_rowid(self, tmp_path):
        store = SkillStore(tmp_path / "skills.db")
        r1 = store.add("skill_a", "Desc A", "Template A")
        r2 = store.add("skill_b", "Desc B", "Template B")
        assert r2 == r1 + 1

    def test_parameters_stored_as_json(self, tmp_path):
        store = SkillStore(tmp_path / "skills.db")
        store.add("s1", "desc", "tmpl", parameters={"key": "value", "n": 42})
        skill = store.get_by_name("s1")
        assert skill["parameters"] == {"key": "value", "n": 42}

    def test_parameters_default_empty_dict(self, tmp_path):
        store = SkillStore(tmp_path / "skills.db")
        store.add("s1", "desc", "tmpl")
        skill = store.get_by_name("s1")
        assert skill["parameters"] == {}

    def test_tags_stored_as_json(self, tmp_path):
        store = SkillStore(tmp_path / "skills.db")
        store.add("s1", "desc", "tmpl", tags=["tag1", "tag2"])
        skill = store.get_by_name("s1")
        assert skill["tags"] == ["tag1", "tag2"]

    def test_tags_default_empty_list(self, tmp_path):
        store = SkillStore(tmp_path / "skills.db")
        store.add("s1", "desc", "tmpl")
        skill = store.get_by_name("s1")
        assert skill["tags"] == []

    def test_source_default_user(self, tmp_path):
        store = SkillStore(tmp_path / "skills.db")
        store.add("s1", "desc", "tmpl")
        skill = store.get_by_name("s1")
        assert skill["source"] == "user"

    def test_source_custom(self, tmp_path):
        store = SkillStore(tmp_path / "skills.db")
        store.add("s1", "desc", "tmpl", source="evolution")
        skill = store.get_by_name("s1")
        assert skill["source"] == "evolution"

    def test_unique_name_constraint(self, tmp_path):
        store = SkillStore(tmp_path / "skills.db")
        store.add("unique_skill", "desc", "tmpl")
        with pytest.raises(sqlite3.IntegrityError):
            store.add("unique_skill", "other desc", "other tmpl")


class TestGetByName:
    """get_by_name() should return a skill dict or None."""

    def test_found(self, tmp_path):
        store = SkillStore(tmp_path / "skills.db")
        store.add("greet", "Greeting", "Hello {{name}}")
        skill = store.get_by_name("greet")
        assert skill is not None
        assert skill["name"] == "greet"
        assert skill["description"] == "Greeting"
        assert skill["prompt_template"] == "Hello {{name}}"

    def test_not_found(self, tmp_path):
        store = SkillStore(tmp_path / "skills.db")
        assert store.get_by_name("nonexistent") is None

    def test_returns_all_fields(self, tmp_path):
        store = SkillStore(tmp_path / "skills.db")
        store.add("s1", "desc", "tmpl", parameters={"k": "v"}, tags=["t1"])
        skill = store.get_by_name("s1")
        assert "id" in skill
        assert "created_at" in skill
        assert skill["usage_count"] == 0
        assert skill["active"] is True


class TestGetActive:
    """get_active() should return active skills ordered by usage_count."""

    def test_returns_active_only(self, tmp_path):
        store = SkillStore(tmp_path / "skills.db")
        store.add("active1", "desc", "tmpl")
        store.add("active2", "desc", "tmpl")
        store.add("inactive", "desc", "tmpl")
        store.deactivate("inactive")

        skills = store.get_active()
        names = [s["name"] for s in skills]
        assert "active1" in names
        assert "active2" in names
        assert "inactive" not in names

    def test_ordered_by_usage_count(self, tmp_path):
        store = SkillStore(tmp_path / "skills.db")
        store.add("low", "desc", "tmpl")
        store.add("high", "desc", "tmpl")
        store.update_usage("high")
        store.update_usage("high")
        store.update_usage("low")

        skills = store.get_active()
        assert skills[0]["name"] == "high"
        assert skills[1]["name"] == "low"

    def test_respects_limit(self, tmp_path):
        store = SkillStore(tmp_path / "skills.db")
        for i in range(10):
            store.add(f"skill_{i}", "desc", "tmpl")
        skills = store.get_active(limit=3)
        assert len(skills) == 3

    def test_empty_returns_empty_list(self, tmp_path):
        store = SkillStore(tmp_path / "skills.db")
        assert store.get_active() == []


class TestUpdateUsage:
    """update_usage() should increment the usage count."""

    def test_increments(self, tmp_path):
        store = SkillStore(tmp_path / "skills.db")
        store.add("s1", "desc", "tmpl")
        assert store.get_by_name("s1")["usage_count"] == 0
        store.update_usage("s1")
        assert store.get_by_name("s1")["usage_count"] == 1
        store.update_usage("s1")
        assert store.get_by_name("s1")["usage_count"] == 2

    def test_nonexistent_no_error(self, tmp_path):
        store = SkillStore(tmp_path / "skills.db")
        store.update_usage("nonexistent")  # should not raise


class TestDeactivate:
    """deactivate() should set active to False."""

    def test_deactivates(self, tmp_path):
        store = SkillStore(tmp_path / "skills.db")
        store.add("s1", "desc", "tmpl")
        assert store.get_by_name("s1")["active"] is True
        store.deactivate("s1")
        assert store.get_by_name("s1")["active"] is False

    def test_nonexistent_no_error(self, tmp_path):
        store = SkillStore(tmp_path / "skills.db")
        store.deactivate("nonexistent")  # should not raise


class TestCount:
    """count() should return total number of skills."""

    def test_empty(self, tmp_path):
        store = SkillStore(tmp_path / "skills.db")
        assert store.count() == 0

    def test_after_inserts(self, tmp_path):
        store = SkillStore(tmp_path / "skills.db")
        store.add("a", "desc", "tmpl")
        store.add("b", "desc", "tmpl")
        assert store.count() == 2

    def test_includes_inactive(self, tmp_path):
        store = SkillStore(tmp_path / "skills.db")
        store.add("a", "desc", "tmpl")
        store.deactivate("a")
        assert store.count() == 1


class TestClear:
    """clear() should delete all skills."""

    def test_clears_all(self, tmp_path):
        store = SkillStore(tmp_path / "skills.db")
        store.add("a", "desc", "tmpl")
        store.add("b", "desc", "tmpl")
        assert store.count() == 2
        store.clear()
        assert store.count() == 0
        assert store.get_active() == []

    def test_clear_empty(self, tmp_path):
        store = SkillStore(tmp_path / "skills.db")
        store.clear()  # should not raise
        assert store.count() == 0

    def test_add_after_clear(self, tmp_path):
        store = SkillStore(tmp_path / "skills.db")
        store.add("before", "desc", "tmpl")
        store.clear()
        store.add("after", "desc", "tmpl")
        assert store.count() == 1
        assert store.get_by_name("after") is not None


class TestSharedDatabase:
    """SkillStore should coexist with other tables in same db."""

    def test_coexists_with_memory_and_fitness(self, tmp_path):
        from ring0.fitness import FitnessTracker
        from ring0.memory import MemoryStore

        db_path = tmp_path / "protea.db"
        fitness = FitnessTracker(db_path)
        memory = MemoryStore(db_path)
        skills = SkillStore(db_path)

        fitness.record(1, "abc", 0.9, 60.0, True)
        memory.add(1, "observation", "survived")
        skills.add("greet", "Greeting", "Hello")

        assert len(fitness.get_history()) == 1
        assert memory.count() == 1
        assert skills.count() == 1
