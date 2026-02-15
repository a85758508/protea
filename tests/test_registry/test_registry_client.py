"""Tests for ring1.registry_client — RegistryClient with mocked HTTP."""

from __future__ import annotations

import io
import json
from unittest.mock import MagicMock, patch

import pytest

from ring1.registry_client import RegistryClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_response(data: dict | list, status: int = 200) -> MagicMock:
    """Create a mock urllib response that works as a context manager."""
    raw = json.dumps(data).encode("utf-8")
    resp = MagicMock()
    resp.read.return_value = raw
    resp.status = status
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPublish:
    @patch("urllib.request.urlopen")
    def test_publish_returns_dict(self, mock_urlopen):
        mock_urlopen.return_value = _mock_response(
            {"name": "greet", "version": 1, "node_id": "test-node"}
        )
        client = RegistryClient("http://registry:8761", node_id="test-node")
        result = client.publish("greet", "Greeting skill", "Hello {{name}}", tags=["greeting"])
        assert result is not None
        assert result["name"] == "greet"
        assert result["version"] == 1
        # Verify the request was built correctly.
        req = mock_urlopen.call_args[0][0]
        assert req.method == "POST"
        assert req.full_url == "http://registry:8761/api/skills"
        body = json.loads(req.data.decode("utf-8"))
        assert body["node_id"] == "test-node"
        assert body["name"] == "greet"
        assert body["tags"] == ["greeting"]

    @patch("urllib.request.urlopen")
    def test_publish_update_bumps_version(self, mock_urlopen):
        mock_urlopen.return_value = _mock_response({"name": "greet", "version": 2})
        client = RegistryClient("http://registry:8761", node_id="test-node")
        result = client.publish("greet", "v2", "t2")
        assert result["version"] == 2


class TestSearch:
    @patch("urllib.request.urlopen")
    def test_search_all(self, mock_urlopen):
        mock_urlopen.return_value = _mock_response([
            {"name": "alpha", "description": "Alpha skill"},
            {"name": "beta", "description": "Beta skill"},
        ])
        client = RegistryClient("http://registry:8761", node_id="test-node")
        results = client.search()
        assert len(results) == 2
        req = mock_urlopen.call_args[0][0]
        assert req.method == "GET"
        assert "limit=50" in req.full_url

    @patch("urllib.request.urlopen")
    def test_search_query(self, mock_urlopen):
        mock_urlopen.return_value = _mock_response([
            {"name": "web-tool", "description": "Web utility"},
        ])
        client = RegistryClient("http://registry:8761", node_id="test-node")
        results = client.search(query="web")
        assert len(results) == 1
        assert results[0]["name"] == "web-tool"
        req = mock_urlopen.call_args[0][0]
        assert "q=web" in req.full_url

    @patch("urllib.request.urlopen")
    def test_search_tag(self, mock_urlopen):
        mock_urlopen.return_value = _mock_response([
            {"name": "s1", "tags": ["api"]},
        ])
        client = RegistryClient("http://registry:8761", node_id="test-node")
        results = client.search(tag="api")
        assert len(results) == 1
        req = mock_urlopen.call_args[0][0]
        assert "tag=api" in req.full_url


class TestDownload:
    @patch("urllib.request.urlopen")
    def test_download_returns_skill(self, mock_urlopen):
        mock_urlopen.return_value = _mock_response(
            {"name": "greet", "downloads": 1}
        )
        client = RegistryClient("http://registry:8761", node_id="test-node")
        skill = client.download("test-node", "greet")
        assert skill is not None
        assert skill["name"] == "greet"
        assert skill["downloads"] == 1
        req = mock_urlopen.call_args[0][0]
        assert req.method == "GET"
        assert req.full_url == "http://registry:8761/api/skills/test-node/greet"

    @patch("urllib.request.urlopen")
    def test_download_not_found(self, mock_urlopen):
        import urllib.error
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="", code=404, msg="Not Found", hdrs={}, fp=io.BytesIO(b""),
        )
        client = RegistryClient("http://registry:8761", node_id="test-node", timeout=1)
        assert client.download("x", "missing") is None


class TestRate:
    @patch("urllib.request.urlopen")
    def test_rate_up(self, mock_urlopen):
        mock_urlopen.return_value = _mock_response({"ok": True})
        client = RegistryClient("http://registry:8761", node_id="test-node")
        assert client.rate("test-node", "s", up=True) is True
        req = mock_urlopen.call_args[0][0]
        assert req.method == "POST"
        assert "/test-node/s/rate" in req.full_url
        body = json.loads(req.data.decode("utf-8"))
        assert body["up"] is True

    @patch("urllib.request.urlopen")
    def test_rate_down(self, mock_urlopen):
        mock_urlopen.return_value = _mock_response({"ok": True})
        client = RegistryClient("http://registry:8761", node_id="test-node")
        assert client.rate("test-node", "s", up=False) is True
        body = json.loads(mock_urlopen.call_args[0][0].data.decode("utf-8"))
        assert body["up"] is False


class TestUnpublish:
    @patch("urllib.request.urlopen")
    def test_unpublish(self, mock_urlopen):
        mock_urlopen.return_value = _mock_response({"ok": True, "deleted": "test-node/s"})
        client = RegistryClient("http://registry:8761", node_id="test-node")
        assert client.unpublish("s") is True
        req = mock_urlopen.call_args[0][0]
        assert req.method == "DELETE"
        assert req.full_url == "http://registry:8761/api/skills/test-node/s"

    @patch("urllib.request.urlopen")
    def test_unpublish_nonexistent(self, mock_urlopen):
        import urllib.error
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="", code=404, msg="Not Found", hdrs={}, fp=io.BytesIO(b""),
        )
        client = RegistryClient("http://registry:8761", node_id="test-node", timeout=1)
        assert client.unpublish("missing") is False


class TestStats:
    @patch("urllib.request.urlopen")
    def test_get_stats(self, mock_urlopen):
        mock_urlopen.return_value = _mock_response(
            {"total_skills": 5, "total_nodes": 2, "total_downloads": 10}
        )
        client = RegistryClient("http://registry:8761", node_id="test-node")
        stats = client.get_stats()
        assert stats is not None
        assert stats["total_skills"] == 5
        assert stats["total_nodes"] == 2
        req = mock_urlopen.call_args[0][0]
        assert req.method == "GET"
        assert req.full_url == "http://registry:8761/api/stats"


class TestConnectionError:
    def test_graceful_degradation(self):
        """Client should return None/[] when registry is unreachable."""
        client = RegistryClient("http://127.0.0.1:1", node_id="test", timeout=1)
        assert client.publish("s", "d", "t") is None
        assert client.search() == []
        assert client.download("n", "s") is None
        assert client.rate("n", "s") is False
        assert client.unpublish("s") is False
        assert client.get_stats() is None
