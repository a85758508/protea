"""Integration tests for ring0.sentinel."""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys
import time
import tomllib

import pytest

from ring0.git_manager import GitManager
from ring0.heartbeat import HeartbeatMonitor
from ring0.sentinel import _start_ring2, _stop_ring2


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _project_root() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parent.parent.parent


def _write_ring2_script(ring2_path: pathlib.Path, script: str) -> None:
    """Write a custom Ring 2 main.py for testing."""
    (ring2_path / "main.py").write_text(script)


# Minimal Ring 2 that heartbeats correctly
_GOOD_RING2 = """\
import os, pathlib, time
hb = pathlib.Path(os.environ["PROTEA_HEARTBEAT"])
pid = os.getpid()
while True:
    hb.write_text(f"{pid}\\n{time.time()}\\n")
    time.sleep(1)
"""

# Ring 2 that crashes immediately
_BAD_RING2 = """\
import sys
sys.exit(1)
"""


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestRing2Lifecycle:
    """Start / stop Ring 2 and verify heartbeat protocol."""

    def test_start_and_heartbeat(self, tmp_path):
        ring2 = tmp_path / "ring2"
        ring2.mkdir()
        _write_ring2_script(ring2, _GOOD_RING2)
        hb_path = ring2 / ".heartbeat"

        proc = _start_ring2(ring2, hb_path)
        try:
            monitor = HeartbeatMonitor(hb_path, timeout_sec=6.0)
            assert monitor.wait_for_heartbeat(startup_timeout=5.0)
            assert monitor.is_alive()
        finally:
            _stop_ring2(proc)

        assert proc.poll() is not None  # process terminated

    def test_stop_dead_process_is_safe(self):
        _stop_ring2(None)  # should not raise

    def test_crashing_ring2_detected(self, tmp_path):
        ring2 = tmp_path / "ring2"
        ring2.mkdir()
        _write_ring2_script(ring2, _BAD_RING2)
        hb_path = ring2 / ".heartbeat"

        proc = _start_ring2(ring2, hb_path)
        proc.wait(timeout=5)
        monitor = HeartbeatMonitor(hb_path, timeout_sec=2.0)
        assert not monitor.is_alive()


class TestRollbackIntegration:
    """Verify Git snapshot + rollback works with Ring 2 code."""

    def test_rollback_restores_ring2(self, tmp_path):
        ring2 = tmp_path / "ring2"
        ring2.mkdir()

        gm = GitManager(ring2)
        gm.init_repo()

        # Version 1: good script
        _write_ring2_script(ring2, _GOOD_RING2)
        good_hash = gm.snapshot("good version")

        # Version 2: bad script
        _write_ring2_script(ring2, _BAD_RING2)
        gm.snapshot("bad version")

        # Rollback to good
        gm.rollback(good_hash)
        content = (ring2 / "main.py").read_text()
        assert "sys.exit(1)" not in content
        assert "time.sleep" in content


class TestConfigLoading:
    """Verify the default config.toml is parseable."""

    def test_config_loads(self):
        root = _project_root()
        cfg_path = root / "config" / "config.toml"
        with open(cfg_path, "rb") as f:
            cfg = tomllib.load(f)
        assert "ring0" in cfg
        assert cfg["ring0"]["heartbeat_interval_sec"] > 0
        assert cfg["ring0"]["heartbeat_timeout_sec"] > 0
