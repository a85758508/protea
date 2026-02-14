"""Tests for ring1.telegram."""

import http.server
import json
import threading
from unittest.mock import MagicMock

from ring1.telegram import TelegramNotifier, create_notifier


class _TelegramHandler(http.server.BaseHTTPRequestHandler):
    """Mock Telegram Bot API server."""

    received_messages: list[dict] = []
    status_code: int = 200

    def do_POST(self):
        content_len = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(content_len))
        _TelegramHandler.received_messages.append(body)

        self.send_response(_TelegramHandler.status_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        resp = {"ok": _TelegramHandler.status_code == 200}
        self.wfile.write(json.dumps(resp).encode())

    def log_message(self, format, *args):
        pass


def _make_server():
    server = http.server.HTTPServer(("127.0.0.1", 0), _TelegramHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    _TelegramHandler.received_messages = []
    _TelegramHandler.status_code = 200
    return server, port


class TestTelegramNotifier:
    def test_send_success(self, monkeypatch):
        server, port = _make_server()
        try:
            import ring1.telegram as mod
            monkeypatch.setattr(
                mod, "_API_BASE",
                f"http://127.0.0.1:{port}/bot{{token}}/sendMessage"
            )
            notifier = TelegramNotifier("test-token", "12345")
            result = notifier.send("Hello test")
            assert result is True
            assert len(_TelegramHandler.received_messages) == 1
            msg = _TelegramHandler.received_messages[0]
            assert msg["chat_id"] == "12345"
            assert msg["text"] == "Hello test"
        finally:
            server.shutdown()

    def test_send_failure_returns_false(self, monkeypatch):
        server, port = _make_server()
        _TelegramHandler.status_code = 500
        try:
            import ring1.telegram as mod
            monkeypatch.setattr(
                mod, "_API_BASE",
                f"http://127.0.0.1:{port}/bot{{token}}/sendMessage"
            )
            notifier = TelegramNotifier("test-token", "12345")
            result = notifier.send("Hello")
            assert result is False
        finally:
            server.shutdown()

    def test_send_never_raises(self, monkeypatch):
        import ring1.telegram as mod
        # Point to unreachable server.
        monkeypatch.setattr(
            mod, "_API_BASE",
            "http://127.0.0.1:1/bot{token}/sendMessage"
        )
        notifier = TelegramNotifier("tok", "id")
        # Should not raise, just return False.
        result = notifier.send("test")
        assert result is False

    def test_notify_generation_complete(self, monkeypatch):
        server, port = _make_server()
        try:
            import ring1.telegram as mod
            monkeypatch.setattr(
                mod, "_API_BASE",
                f"http://127.0.0.1:{port}/bot{{token}}/sendMessage"
            )
            notifier = TelegramNotifier("tok", "chat")
            result = notifier.notify_generation_complete(
                generation=5, score=0.85, survived=True, commit_hash="abc123def456"
            )
            assert result is True
            msg = _TelegramHandler.received_messages[0]
            assert "Gen 5" in msg["text"]
            assert "SURVIVED" in msg["text"]
            assert "0.85" in msg["text"]
        finally:
            server.shutdown()

    def test_notify_error(self, monkeypatch):
        server, port = _make_server()
        try:
            import ring1.telegram as mod
            monkeypatch.setattr(
                mod, "_API_BASE",
                f"http://127.0.0.1:{port}/bot{{token}}/sendMessage"
            )
            notifier = TelegramNotifier("tok", "chat")
            result = notifier.notify_error(3, "Something broke")
            assert result is True
            msg = _TelegramHandler.received_messages[0]
            assert "Gen 3" in msg["text"]
            assert "Something broke" in msg["text"]
        finally:
            server.shutdown()


class TestCreateNotifier:
    def test_disabled_returns_none(self):
        cfg = MagicMock()
        cfg.telegram_enabled = False
        assert create_notifier(cfg) is None

    def test_enabled_with_credentials(self):
        cfg = MagicMock()
        cfg.telegram_enabled = True
        cfg.telegram_bot_token = "tok"
        cfg.telegram_chat_id = "123"
        notifier = create_notifier(cfg)
        assert isinstance(notifier, TelegramNotifier)

    def test_enabled_missing_token(self):
        cfg = MagicMock()
        cfg.telegram_enabled = True
        cfg.telegram_bot_token = ""
        cfg.telegram_chat_id = "123"
        assert create_notifier(cfg) is None

    def test_enabled_missing_chat_id(self):
        cfg = MagicMock()
        cfg.telegram_enabled = True
        cfg.telegram_bot_token = "tok"
        cfg.telegram_chat_id = ""
        assert create_notifier(cfg) is None
