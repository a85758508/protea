"""Claude API HTTP client — pure stdlib (urllib.request + json).

Sends messages to the Anthropic Messages API with retry + exponential backoff.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request

log = logging.getLogger("protea.llm_client")

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"

_RETRYABLE_CODES = {429, 500, 502, 503, 529}
_MAX_RETRIES = 3
_BASE_DELAY = 2.0  # seconds


class LLMError(Exception):
    """Raised when the Claude API call fails after all retries."""


class ClaudeClient:
    """Minimal Claude Messages API client (no third-party deps)."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-5-20250929",
        max_tokens: int = 4096,
    ) -> None:
        if not api_key:
            raise LLMError("CLAUDE_API_KEY is not set")
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens

    def send_message(self, system_prompt: str, user_message: str) -> str:
        """Send a message to Claude and return the assistant's text response.

        Retries on transient errors (429, 5xx) with exponential backoff.
        """
        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_message}],
        }
        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": API_VERSION,
        }

        last_error: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                req = urllib.request.Request(
                    API_URL, data=data, headers=headers, method="POST"
                )
                with urllib.request.urlopen(req, timeout=120) as resp:
                    body = json.loads(resp.read().decode("utf-8"))
                # Extract text from the first content block.
                for block in body.get("content", []):
                    if block.get("type") == "text":
                        return block["text"]
                raise LLMError("No text content in API response")
            except urllib.error.HTTPError as exc:
                last_error = exc
                code = exc.code
                if code in _RETRYABLE_CODES and attempt < _MAX_RETRIES - 1:
                    delay = _BASE_DELAY * (2 ** attempt)
                    log.warning(
                        "Claude API %d — retry %d/%d in %.1fs",
                        code, attempt + 1, _MAX_RETRIES, delay,
                    )
                    time.sleep(delay)
                    continue
                raise LLMError(
                    f"Claude API HTTP {code}: {exc.read().decode('utf-8', errors='replace')}"
                ) from exc
            except urllib.error.URLError as exc:
                last_error = exc
                if attempt < _MAX_RETRIES - 1:
                    delay = _BASE_DELAY * (2 ** attempt)
                    log.warning(
                        "Claude API network error — retry %d/%d in %.1fs",
                        attempt + 1, _MAX_RETRIES, delay,
                    )
                    time.sleep(delay)
                    continue
                raise LLMError(f"Claude API network error: {exc}") from exc

        raise LLMError(f"Claude API failed after {_MAX_RETRIES} retries") from last_error
