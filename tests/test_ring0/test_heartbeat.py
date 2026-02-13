"""Tests for ring0.heartbeat — HeartbeatMonitor."""

from __future__ import annotations

import os
import time

from ring0.heartbeat import HeartbeatMonitor


class TestWriteHeartbeat:
    """write_heartbeat should produce a file with the expected format."""

    def test_creates_file_with_correct_format(self, tmp_path):
        hb_file = tmp_path / ".heartbeat"
        HeartbeatMonitor.write_heartbeat(hb_file, pid=1234)

        text = hb_file.read_text()
        lines = text.strip().splitlines()
        assert len(lines) == 2
        assert lines[0] == "1234"
        # The second line must be a valid float timestamp.
        ts = float(lines[1])
        assert ts > 0


class TestReadHeartbeat:
    """read_heartbeat should parse pid and timestamp from a heartbeat file."""

    def test_parses_pid_and_timestamp(self, tmp_path):
        hb_file = tmp_path / ".heartbeat"
        now = time.time()
        hb_file.write_text(f"42\n{now}\n")

        monitor = HeartbeatMonitor(hb_file)
        pid, ts = monitor.read_heartbeat()
        assert pid == 42
        assert ts == now

    def test_returns_none_for_missing_file(self, tmp_path):
        monitor = HeartbeatMonitor(tmp_path / ".heartbeat")
        pid, ts = monitor.read_heartbeat()
        assert pid is None
        assert ts is None

    def test_returns_none_for_malformed_file(self, tmp_path):
        hb_file = tmp_path / ".heartbeat"
        hb_file.write_text("garbage\n")

        monitor = HeartbeatMonitor(hb_file)
        pid, ts = monitor.read_heartbeat()
        assert pid is None
        assert ts is None


class TestIsAlive:
    """is_alive combines freshness and PID existence checks."""

    def test_true_for_current_process(self, tmp_path):
        hb_file = tmp_path / ".heartbeat"
        HeartbeatMonitor.write_heartbeat(hb_file, pid=os.getpid())

        monitor = HeartbeatMonitor(hb_file)
        assert monitor.is_alive() is True

    def test_false_when_file_missing(self, tmp_path):
        monitor = HeartbeatMonitor(tmp_path / ".heartbeat")
        assert monitor.is_alive() is False

    def test_false_when_heartbeat_is_stale(self, tmp_path):
        hb_file = tmp_path / ".heartbeat"
        stale_ts = time.time() - 30.0  # 30 seconds ago
        hb_file.write_text(f"{os.getpid()}\n{stale_ts}\n")

        monitor = HeartbeatMonitor(hb_file, timeout_sec=6.0)
        assert monitor.is_alive() is False

    def test_false_when_pid_does_not_exist(self, tmp_path):
        hb_file = tmp_path / ".heartbeat"
        fake_pid = 4_000_000  # almost certainly not running
        hb_file.write_text(f"{fake_pid}\n{time.time()}\n")

        monitor = HeartbeatMonitor(hb_file)
        assert monitor.is_alive() is False


class TestWaitForHeartbeat:
    """wait_for_heartbeat should poll until a valid heartbeat appears."""

    def test_returns_true_when_heartbeat_exists(self, tmp_path):
        hb_file = tmp_path / ".heartbeat"
        HeartbeatMonitor.write_heartbeat(hb_file, pid=os.getpid())

        monitor = HeartbeatMonitor(hb_file)
        assert monitor.wait_for_heartbeat(startup_timeout=2.0) is True

    def test_returns_false_on_timeout(self, tmp_path):
        monitor = HeartbeatMonitor(tmp_path / ".heartbeat")
        assert monitor.wait_for_heartbeat(startup_timeout=1.0) is False
