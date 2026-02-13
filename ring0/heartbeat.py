"""Heartbeat monitor for Ring 2 process health.

Ring 2 writes a `.heartbeat` file containing its PID and a Unix timestamp.
Ring 0 (Sentinel) polls that file to decide whether Ring 2 is still alive.
Pure stdlib — no external dependencies.
"""

from __future__ import annotations

import os
import pathlib
import time


class HeartbeatMonitor:
    """Monitor a Ring 2 process via a heartbeat file protocol."""

    def __init__(
        self, heartbeat_path: pathlib.Path, timeout_sec: float = 6.0
    ) -> None:
        self.heartbeat_path = heartbeat_path
        self.timeout_sec = timeout_sec

    def read_heartbeat(self) -> tuple[int | None, float | None]:
        """Parse the heartbeat file and return *(pid, timestamp)*.

        Returns ``(None, None)`` when the file is missing or malformed.
        """
        try:
            text = self.heartbeat_path.read_text().strip()
            lines = text.splitlines()
            if len(lines) < 2:
                return None, None
            pid = int(lines[0])
            ts = float(lines[1])
            return pid, ts
        except (OSError, ValueError):
            return None, None

    def is_alive(self) -> bool:
        """Return *True* when the heartbeat is fresh and the PID is running."""
        pid, ts = self.read_heartbeat()
        if pid is None or ts is None:
            return False
        # Check freshness.
        if time.time() - ts > self.timeout_sec:
            return False
        # Check that the process actually exists.
        try:
            os.kill(pid, 0)
        except (OSError, ProcessLookupError):
            return False
        return True

    def wait_for_heartbeat(self, startup_timeout: float = 10.0) -> bool:
        """Block until a valid heartbeat appears or *startup_timeout* elapses.

        Polls every 0.5 s.  Returns *True* if a heartbeat was detected.
        """
        deadline = time.time() + startup_timeout
        while time.time() < deadline:
            if self.is_alive():
                return True
            time.sleep(0.5)
        return False

    @staticmethod
    def write_heartbeat(heartbeat_path: pathlib.Path, pid: int) -> None:
        """Write a heartbeat file containing *pid* and the current timestamp."""
        heartbeat_path.write_text(f"{pid}\n{time.time()}\n")
