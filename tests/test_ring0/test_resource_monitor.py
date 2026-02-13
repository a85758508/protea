"""Tests for ring0.resource_monitor."""

from ring0.resource_monitor import (
    check_resources,
    get_cpu_percent,
    get_disk_percent,
    get_memory_percent,
)


def test_get_disk_percent_returns_valid_range():
    pct = get_disk_percent("/")
    assert isinstance(pct, float)
    assert 0.0 <= pct <= 100.0


def test_get_memory_percent_returns_valid_range():
    pct = get_memory_percent()
    assert isinstance(pct, float)
    assert 0.0 <= pct <= 100.0


def test_get_cpu_percent_returns_non_negative():
    pct = get_cpu_percent()
    assert isinstance(pct, float)
    assert pct >= 0.0


def test_check_resources_all_ok_with_high_limits():
    ok, msg = check_resources(max_cpu=9999, max_mem=9999, max_disk=9999)
    assert ok is True
    assert "within limits" in msg.lower()


def test_check_resources_fails_with_zero_disk_limit():
    ok, msg = check_resources(max_cpu=9999, max_mem=9999, max_disk=0)
    assert ok is False
    assert "Disk" in msg
