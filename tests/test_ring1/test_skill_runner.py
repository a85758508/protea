"""Tests for ring1.skill_runner."""

from __future__ import annotations

import sys
import time

from ring1.skill_runner import SkillRunner


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SIMPLE_SCRIPT = "import time\nprint('hello from skill')\ntime.sleep(60)\n"

_PORT_SCRIPT = """\
import time
print("Starting server on port 8080")
print("Also available at localhost:9090")
time.sleep(60)
"""

_FAST_EXIT_SCRIPT = "print('done')\n"


# ---------------------------------------------------------------------------
# TestRun
# ---------------------------------------------------------------------------


class TestRun:
    def test_run_simple_script(self):
        sr = SkillRunner()
        try:
            pid, msg = sr.run("test_skill", _SIMPLE_SCRIPT)
            assert pid > 0
            assert "test_skill" in msg
            assert str(pid) in msg
            assert sr.is_running()
        finally:
            sr.stop()

    def test_run_stops_previous(self):
        sr = SkillRunner()
        try:
            pid1, _ = sr.run("skill_a", _SIMPLE_SCRIPT)
            pid2, _ = sr.run("skill_b", _SIMPLE_SCRIPT)
            assert pid1 != pid2
            # Only the second should be running.
            assert sr.is_running()
            info = sr.get_info()
            assert info["skill_name"] == "skill_b"
        finally:
            sr.stop()

    def test_run_writes_temp_file(self, tmp_path):
        sr = SkillRunner()
        try:
            sr.run("tmp_test", _SIMPLE_SCRIPT)
            # The script path should exist and contain the source.
            assert sr._script_path
            with open(sr._script_path) as f:
                assert "hello from skill" in f.read()
        finally:
            sr.stop()


# ---------------------------------------------------------------------------
# TestStop
# ---------------------------------------------------------------------------


class TestStop:
    def test_stop_running(self):
        sr = SkillRunner()
        sr.run("s", _SIMPLE_SCRIPT)
        assert sr.stop() is True
        assert not sr.is_running()

    def test_stop_not_running(self):
        sr = SkillRunner()
        assert sr.stop() is False


# ---------------------------------------------------------------------------
# TestIsRunning
# ---------------------------------------------------------------------------


class TestIsRunning:
    def test_running_when_active(self):
        sr = SkillRunner()
        try:
            sr.run("r", _SIMPLE_SCRIPT)
            assert sr.is_running() is True
        finally:
            sr.stop()

    def test_not_running_after_stop(self):
        sr = SkillRunner()
        sr.run("r", _SIMPLE_SCRIPT)
        sr.stop()
        assert sr.is_running() is False

    def test_not_running_after_natural_exit(self):
        sr = SkillRunner()
        sr.run("r", _FAST_EXIT_SCRIPT)
        # Wait for the script to finish.
        time.sleep(2)
        assert sr.is_running() is False


# ---------------------------------------------------------------------------
# TestGetOutput
# ---------------------------------------------------------------------------


class TestGetOutput:
    def test_read_output(self):
        sr = SkillRunner()
        try:
            sr.run("out", _SIMPLE_SCRIPT)
            # run() already sleeps 1s, output should be available.
            output = sr.get_output()
            assert "hello from skill" in output
        finally:
            sr.stop()

    def test_no_output_when_not_running(self):
        sr = SkillRunner()
        assert sr.get_output() == ""

    def test_output_truncation(self):
        many_lines = "\n".join(f"print('line {i}')" for i in range(100))
        sr = SkillRunner()
        try:
            sr.run("trunc", many_lines)
            time.sleep(1)
            output = sr.get_output(max_lines=5)
            assert len(output.splitlines()) <= 5
        finally:
            sr.stop()


# ---------------------------------------------------------------------------
# TestGetInfo
# ---------------------------------------------------------------------------


class TestGetInfo:
    def test_info_running(self):
        sr = SkillRunner()
        try:
            sr.run("info_test", _SIMPLE_SCRIPT)
            info = sr.get_info()
            assert info is not None
            assert info["skill_name"] == "info_test"
            assert info["pid"] > 0
            assert info["running"] is True
            assert info["uptime"] >= 0
        finally:
            sr.stop()

    def test_info_none_when_not_started(self):
        sr = SkillRunner()
        assert sr.get_info() is None


# ---------------------------------------------------------------------------
# TestPortDetection
# ---------------------------------------------------------------------------


class TestPortDetection:
    def test_detect_port_from_output(self):
        sr = SkillRunner()
        try:
            sr.run("port_test", _PORT_SCRIPT)
            info = sr.get_info()
            # Should detect port 8080 (first match).
            assert info["port"] == 8080
        finally:
            sr.stop()

    def test_no_port_when_none_printed(self):
        sr = SkillRunner()
        try:
            sr.run("no_port", _SIMPLE_SCRIPT)
            info = sr.get_info()
            assert info["port"] is None
        finally:
            sr.stop()

    def test_detect_localhost_port(self):
        script = "import time\nprint('Running at localhost:3000')\ntime.sleep(60)\n"
        sr = SkillRunner()
        try:
            sr.run("lh", script)
            info = sr.get_info()
            assert info["port"] == 3000
        finally:
            sr.stop()


# ---------------------------------------------------------------------------
# TestPatchSource
# ---------------------------------------------------------------------------


class TestPatchSource:
    def test_replaces_httpserver_constructor(self):
        src = "from http.server import HTTPServer\nserver = HTTPServer(('', 8080), Handler)\n"
        patched = SkillRunner._patch_source(src)
        assert "ThreadingHTTPServer(('', 8080), Handler)" in patched
        assert "server = HTTPServer(" not in patched

    def test_adds_threading_import(self):
        src = "from http.server import HTTPServer\n"
        patched = SkillRunner._patch_source(src)
        assert "from http.server import HTTPServer, ThreadingHTTPServer" in patched

    def test_skips_if_already_has_threading(self):
        src = "from http.server import HTTPServer, ThreadingHTTPServer\nserver = ThreadingHTTPServer(('', 8080), Handler)\n"
        patched = SkillRunner._patch_source(src)
        # Should be unchanged.
        assert patched == src

    def test_no_httpserver_unchanged(self):
        src = "print('hello world')\n"
        patched = SkillRunner._patch_source(src)
        assert patched == src
