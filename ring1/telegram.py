"""Telegram Bot API notifications — fire-and-forget, never raises.

Pure stdlib (urllib.request + json).
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request

log = logging.getLogger("protea.telegram")

_API_BASE = "https://api.telegram.org/bot{token}/sendMessage"


class TelegramNotifier:
    """Send messages via Telegram Bot API.  All methods are fire-and-forget."""

    def __init__(self, bot_token: str, chat_id: str) -> None:
        self.bot_token = bot_token
        self.chat_id = chat_id
        self._url = _API_BASE.format(token=bot_token)

    def send(self, message: str) -> bool:
        """Send a text message.  Returns True on success, False on any error."""
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "Markdown",
        }
        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                self._url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                return body.get("ok", False)
        except Exception:
            log.debug("Telegram send failed", exc_info=True)
            return False

    def notify_generation_complete(
        self,
        generation: int,
        score: float,
        survived: bool,
        commit_hash: str,
    ) -> bool:
        """Notify about a completed generation."""
        status = "SURVIVED" if survived else "DIED"
        msg = (
            f"*Protea Gen {generation}*\n"
            f"Status: {status}\n"
            f"Score: {score:.2f}\n"
            f"Commit: `{commit_hash[:12]}`"
        )
        return self.send(msg)

    def notify_error(self, generation: int, error: str) -> bool:
        """Notify about an error during evolution."""
        msg = (
            f"*Protea Gen {generation} ERROR*\n"
            f"```\n{error[:500]}\n```"
        )
        return self.send(msg)


def create_notifier(config) -> TelegramNotifier | None:
    """Create a TelegramNotifier from Ring1Config, or None if disabled."""
    if not config.telegram_enabled:
        return None
    if not config.telegram_bot_token or not config.telegram_chat_id:
        log.warning("Telegram enabled but token/chat_id missing — disabled")
        return None
    return TelegramNotifier(config.telegram_bot_token, config.telegram_chat_id)
