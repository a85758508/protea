"""Tests for ring0.fitness — FitnessTracker."""

from __future__ import annotations

from ring0.fitness import FitnessTracker


class TestRecord:
    """record() should insert rows and return their rowid."""

    def test_insert_returns_rowid(self, tmp_path):
        tracker = FitnessTracker(tmp_path / "fitness.db")
        rid = tracker.record(
            generation=1,
            commit_hash="abc123",
            score=0.85,
            runtime_sec=1.2,
            survived=True,
        )
        assert rid == 1

    def test_successive_inserts_increment_rowid(self, tmp_path):
        tracker = FitnessTracker(tmp_path / "fitness.db")
        r1 = tracker.record(1, "aaa", 0.5, 1.0, True)
        r2 = tracker.record(1, "bbb", 0.6, 1.1, False)
        assert r2 == r1 + 1


class TestGetBest:
    """get_best() should return entries sorted by score descending."""

    def test_returns_sorted_by_score(self, tmp_path):
        tracker = FitnessTracker(tmp_path / "fitness.db")
        tracker.record(1, "low", 0.1, 1.0, True)
        tracker.record(1, "high", 0.9, 1.0, True)
        tracker.record(1, "mid", 0.5, 1.0, True)

        best = tracker.get_best(n=3)
        scores = [entry["score"] for entry in best]
        assert scores == [0.9, 0.5, 0.1]

    def test_limits_to_n(self, tmp_path):
        tracker = FitnessTracker(tmp_path / "fitness.db")
        for i in range(10):
            tracker.record(1, f"hash{i}", float(i), 1.0, True)

        best = tracker.get_best(n=3)
        assert len(best) == 3
        assert best[0]["score"] == 9.0

    def test_empty_database_returns_empty_list(self, tmp_path):
        tracker = FitnessTracker(tmp_path / "fitness.db")
        assert tracker.get_best() == []


class TestGetGenerationStats:
    """get_generation_stats() should compute correct aggregates."""

    def test_computes_correct_stats(self, tmp_path):
        tracker = FitnessTracker(tmp_path / "fitness.db")
        tracker.record(1, "a", 0.2, 1.0, True)
        tracker.record(1, "b", 0.8, 1.0, True)
        tracker.record(1, "c", 0.5, 1.0, False)

        stats = tracker.get_generation_stats(generation=1)
        assert stats is not None
        assert stats["count"] == 3
        assert stats["max_score"] == 0.8
        assert stats["min_score"] == 0.2
        assert abs(stats["avg_score"] - 0.5) < 1e-9

    def test_returns_none_for_missing_generation(self, tmp_path):
        tracker = FitnessTracker(tmp_path / "fitness.db")
        assert tracker.get_generation_stats(generation=99) is None

    def test_ignores_other_generations(self, tmp_path):
        tracker = FitnessTracker(tmp_path / "fitness.db")
        tracker.record(1, "a", 1.0, 1.0, True)
        tracker.record(2, "b", 0.0, 1.0, True)

        stats = tracker.get_generation_stats(generation=1)
        assert stats is not None
        assert stats["count"] == 1
        assert stats["avg_score"] == 1.0


class TestGetHistory:
    """get_history() should return entries in reverse chronological order."""

    def test_returns_reverse_order(self, tmp_path):
        tracker = FitnessTracker(tmp_path / "fitness.db")
        tracker.record(1, "first", 0.1, 1.0, True)
        tracker.record(2, "second", 0.2, 1.0, True)
        tracker.record(3, "third", 0.3, 1.0, True)

        history = tracker.get_history(limit=10)
        hashes = [entry["commit_hash"] for entry in history]
        assert hashes == ["third", "second", "first"]

    def test_respects_limit(self, tmp_path):
        tracker = FitnessTracker(tmp_path / "fitness.db")
        for i in range(10):
            tracker.record(i, f"hash{i}", float(i), 1.0, True)

        history = tracker.get_history(limit=3)
        assert len(history) == 3
        # Most recent first.
        assert history[0]["commit_hash"] == "hash9"

    def test_empty_database_returns_empty_list(self, tmp_path):
        tracker = FitnessTracker(tmp_path / "fitness.db")
        assert tracker.get_history() == []
