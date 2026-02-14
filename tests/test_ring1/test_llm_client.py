"""Tests for ring1.llm_client."""

import json
import http.server
import threading

import pytest

from ring1.llm_client import ClaudeClient, LLMError


class TestClaudeClientInit:
    def test_missing_api_key_raises(self):
        with pytest.raises(LLMError, match="CLAUDE_API_KEY"):
            ClaudeClient(api_key="")

    def test_valid_init(self):
        client = ClaudeClient(api_key="sk-test", model="test-model", max_tokens=100)
        assert client.api_key == "sk-test"
        assert client.model == "test-model"
        assert client.max_tokens == 100

    def test_default_values(self):
        client = ClaudeClient(api_key="sk-test")
        assert client.model == "claude-sonnet-4-5-20250929"
        assert client.max_tokens == 4096


class _MockHandler(http.server.BaseHTTPRequestHandler):
    """Simple HTTP handler that returns canned Claude API responses."""

    # Class-level state for test control.
    response_body: dict = {}
    status_code: int = 200
    call_count: int = 0

    def do_POST(self):
        _MockHandler.call_count += 1
        content_len = int(self.headers.get("Content-Length", 0))
        self.rfile.read(content_len)  # consume body

        self.send_response(_MockHandler.status_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(_MockHandler.response_body).encode())

    def log_message(self, format, *args):
        pass  # suppress output


@pytest.fixture
def mock_api(monkeypatch):
    """Start a local HTTP server and patch API_URL to point to it."""
    server = http.server.HTTPServer(("127.0.0.1", 0), _MockHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    import ring1.llm_client as mod
    monkeypatch.setattr(mod, "API_URL", f"http://127.0.0.1:{port}/v1/messages")
    # Reset handler state.
    _MockHandler.call_count = 0
    _MockHandler.status_code = 200
    _MockHandler.response_body = {
        "content": [{"type": "text", "text": "Hello from Claude"}]
    }

    yield _MockHandler

    server.shutdown()


class TestSendMessage:
    def test_success(self, mock_api):
        client = ClaudeClient(api_key="sk-test")
        result = client.send_message("system", "hello")
        assert result == "Hello from Claude"
        assert mock_api.call_count == 1

    def test_custom_response(self, mock_api):
        mock_api.response_body = {
            "content": [{"type": "text", "text": "custom reply"}]
        }
        client = ClaudeClient(api_key="sk-test")
        result = client.send_message("system", "hello")
        assert result == "custom reply"

    def test_no_text_content_raises(self, mock_api):
        mock_api.response_body = {"content": [{"type": "image", "data": "..."}]}
        client = ClaudeClient(api_key="sk-test")
        with pytest.raises(LLMError, match="No text content"):
            client.send_message("system", "hello")

    def test_http_400_no_retry(self, mock_api):
        mock_api.status_code = 400
        mock_api.response_body = {"error": "bad request"}
        client = ClaudeClient(api_key="sk-test")
        with pytest.raises(LLMError, match="HTTP 400"):
            client.send_message("system", "hello")
        # 400 should NOT be retried.
        assert mock_api.call_count == 1

    def test_http_429_retries(self, mock_api, monkeypatch):
        import ring1.llm_client as mod
        monkeypatch.setattr(mod, "_BASE_DELAY", 0.01)

        mock_api.status_code = 429
        client = ClaudeClient(api_key="sk-test")
        with pytest.raises(LLMError):
            client.send_message("system", "hello")
        # Should have retried 3 times.
        assert mock_api.call_count == 3

    def test_http_500_retries(self, mock_api, monkeypatch):
        import ring1.llm_client as mod
        monkeypatch.setattr(mod, "_BASE_DELAY", 0.01)

        mock_api.status_code = 500
        client = ClaudeClient(api_key="sk-test")
        with pytest.raises(LLMError):
            client.send_message("system", "hello")
        assert mock_api.call_count == 3
