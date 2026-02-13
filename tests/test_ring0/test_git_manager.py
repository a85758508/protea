"""Tests for ring0.git_manager."""

import pathlib

from ring0.git_manager import GitManager


def test_init_repo_creates_git_dir(tmp_path: pathlib.Path):
    gm = GitManager(tmp_path)
    gm.init_repo()
    assert (tmp_path / ".git").is_dir()


def test_init_repo_is_idempotent(tmp_path: pathlib.Path):
    gm = GitManager(tmp_path)
    gm.init_repo()
    gm.init_repo()  # should not raise
    assert (tmp_path / ".git").is_dir()


def test_snapshot_creates_commit(tmp_path: pathlib.Path):
    gm = GitManager(tmp_path)
    gm.init_repo()
    (tmp_path / "hello.txt").write_text("hello")
    commit_hash = gm.snapshot("initial commit")
    assert len(commit_hash) == 40  # full SHA-1


def test_snapshot_no_changes_returns_current_hash(tmp_path: pathlib.Path):
    gm = GitManager(tmp_path)
    gm.init_repo()
    (tmp_path / "hello.txt").write_text("hello")
    first = gm.snapshot("first")
    second = gm.snapshot("should be noop")
    assert first == second


def test_rollback_restores_file_content(tmp_path: pathlib.Path):
    gm = GitManager(tmp_path)
    gm.init_repo()

    # First version
    (tmp_path / "data.txt").write_text("version-1")
    hash1 = gm.snapshot("v1")

    # Second version
    (tmp_path / "data.txt").write_text("version-2")
    gm.snapshot("v2")

    assert (tmp_path / "data.txt").read_text() == "version-2"

    # Rollback to first
    gm.rollback(hash1)
    assert (tmp_path / "data.txt").read_text() == "version-1"


def test_rollback_removes_new_files(tmp_path: pathlib.Path):
    gm = GitManager(tmp_path)
    gm.init_repo()

    (tmp_path / "keep.txt").write_text("keep")
    hash1 = gm.snapshot("v1")

    (tmp_path / "extra.txt").write_text("extra")
    gm.snapshot("v2")

    gm.rollback(hash1)
    assert not (tmp_path / "extra.txt").exists()
    assert (tmp_path / "keep.txt").read_text() == "keep"


def test_get_history_returns_correct_entries(tmp_path: pathlib.Path):
    gm = GitManager(tmp_path)
    gm.init_repo()

    (tmp_path / "a.txt").write_text("a")
    gm.snapshot("alpha")

    (tmp_path / "b.txt").write_text("b")
    gm.snapshot("beta")

    history = gm.get_history(n=5)
    assert len(history) == 2
    # Most recent first
    assert history[0][1] == "beta"
    assert history[1][1] == "alpha"
    # Hashes are 40-char hex strings
    for h, _ in history:
        assert len(h) == 40
