"""Git manager — snapshot and rollback Ring 2 code (pure stdlib)."""

import os
import pathlib
import subprocess


_GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "Protea",
    "GIT_AUTHOR_EMAIL": "protea@localhost",
    "GIT_COMMITTER_NAME": "Protea",
    "GIT_COMMITTER_EMAIL": "protea@localhost",
}


class GitManager:
    """Thin wrapper around git CLI for snapshotting and rollback."""

    def __init__(self, repo_path: pathlib.Path) -> None:
        self.repo_path = repo_path

    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=self.repo_path,
            check=True,
            capture_output=True,
            text=True,
            env=_GIT_ENV,
        )

    def _is_repo(self) -> bool:
        return (self.repo_path / ".git").is_dir()

    def init_repo(self) -> None:
        """Initialise a git repo if one does not already exist."""
        if not self._is_repo():
            self.repo_path.mkdir(parents=True, exist_ok=True)
            self._run("init")
            self._run("checkout", "-b", "main")

    def get_current_hash(self) -> str:
        """Return the HEAD commit hash (short form)."""
        result = self._run("rev-parse", "HEAD")
        return result.stdout.strip()

    def snapshot(self, message: str) -> str:
        """Stage everything and commit.  Return the new commit hash.

        If there is nothing to commit, return the current HEAD hash.
        """
        self._run("add", "-A")
        # Check if there is anything staged.
        status = self._run("status", "--porcelain")
        if not status.stdout.strip():
            return self.get_current_hash()
        self._run("commit", "-m", message)
        return self.get_current_hash()

    def rollback(self, commit_hash: str) -> None:
        """Restore the working tree to *commit_hash* without moving HEAD.

        Resets the index then checks out, so files added after the target
        commit are removed as well.
        """
        self._run("reset", commit_hash, "--", ".")
        self._run("checkout", "--", ".")
        self._run("clean", "-fd")

    def get_history(self, n: int = 10) -> list[tuple[str, str]]:
        """Return the last *n* commits as ``(hash, message)`` tuples."""
        result = self._run(
            "log",
            f"-{n}",
            "--pretty=format:%H%x00%s",
        )
        entries: list[tuple[str, str]] = []
        for line in result.stdout.strip().splitlines():
            if "\x00" in line:
                h, msg = line.split("\x00", 1)
                entries.append((h, msg))
        return entries
