"""Ring 1 configuration — load [ring1] from config.toml + .env secrets.

Pure stdlib.  Reads `.env` into os.environ for secrets (API keys, tokens).
"""

from __future__ import annotations

import os
import pathlib
from typing import NamedTuple


class Ring1Config(NamedTuple):
    claude_api_key: str
    claude_model: str
    claude_max_tokens: int
    telegram_bot_token: str
    telegram_chat_id: str
    telegram_enabled: bool
    max_prompt_history: int


def _load_dotenv(project_root: pathlib.Path) -> None:
    """Parse a simple .env file and inject into os.environ.

    Handles KEY=VALUE, ignores comments (#) and blank lines.
    Strips optional surrounding quotes from values.
    """
    env_path = project_root / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        # Strip matching quotes.
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        if key and value:
            os.environ.setdefault(key, value)


def load_ring1_config(project_root: pathlib.Path) -> Ring1Config:
    """Load Ring 1 config from config.toml + environment variables."""
    import tomllib

    _load_dotenv(project_root)

    cfg_path = project_root / "config" / "config.toml"
    with open(cfg_path, "rb") as f:
        toml = tomllib.load(f)

    r1 = toml.get("ring1", {})
    tg = r1.get("telegram", {})

    return Ring1Config(
        claude_api_key=os.environ.get("CLAUDE_API_KEY", ""),
        claude_model=r1.get("claude_model", "claude-sonnet-4-5-20250929"),
        claude_max_tokens=r1.get("claude_max_tokens", 4096),
        telegram_bot_token=os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        telegram_chat_id=os.environ.get("TELEGRAM_CHAT_ID", ""),
        telegram_enabled=tg.get("enabled", False),
        max_prompt_history=r1.get("max_prompt_history", 10),
    )
