"""Telegram Bot — bidirectional interaction via getUpdates long polling.

Pure stdlib (urllib.request + json + threading).  Runs as a daemon thread
alongside the Sentinel main loop.  Errors never propagate to the caller.
"""

from __future__ import annotations

import json
import logging
import pathlib
import threading
import time
import urllib.error
import urllib.request

log = logging.getLogger("protea.telegram_bot")

_API_BASE = "https://api.telegram.org/bot{token}/{method}"


# ---------------------------------------------------------------------------
# Shared state between Sentinel thread and Bot thread
# ---------------------------------------------------------------------------

class SentinelState:
    """Thread-safe container for Sentinel runtime state.

    Sentinel writes fields under the lock each loop iteration.
    Bot reads fields under the lock on command.
    """

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.pause_event = threading.Event()
        self.kill_event = threading.Event()
        # Mutable fields — protected by self.lock
        self.generation: int = 0
        self.start_time: float = time.time()
        self.alive: bool = False
        self.mutation_rate: float = 0.0
        self.max_runtime_sec: float = 0.0
        self.last_score: float = 0.0
        self.last_survived: bool = False

    def snapshot(self) -> dict:
        """Return a consistent copy of all fields."""
        with self.lock:
            return {
                "generation": self.generation,
                "start_time": self.start_time,
                "alive": self.alive,
                "mutation_rate": self.mutation_rate,
                "max_runtime_sec": self.max_runtime_sec,
                "last_score": self.last_score,
                "last_survived": self.last_survived,
                "paused": self.pause_event.is_set(),
            }


# ---------------------------------------------------------------------------
# Telegram Bot
# ---------------------------------------------------------------------------

class TelegramBot:
    """Telegram Bot that reads commands via getUpdates long polling."""

    def __init__(
        self,
        bot_token: str,
        chat_id: str,
        state: SentinelState,
        fitness,
        ring2_path: pathlib.Path,
    ) -> None:
        self.bot_token = bot_token
        self.chat_id = str(chat_id)
        self.state = state
        self.fitness = fitness
        self.ring2_path = ring2_path
        self._offset: int = 0
        self._running = threading.Event()
        self._running.set()

    # -- low-level API helpers --

    def _api_call(self, method: str, params: dict | None = None) -> dict | None:
        """Call a Telegram Bot API method.  Returns parsed JSON or None."""
        url = _API_BASE.format(token=self.bot_token, method=method)
        payload = json.dumps(params or {}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        timeout = 35 if method == "getUpdates" else 10
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                if body.get("ok"):
                    return body
                return None
        except Exception:
            log.debug("API call %s failed", method, exc_info=True)
            return None

    def _get_updates(self) -> list[dict]:
        """Fetch new updates via long polling."""
        params = {"offset": self._offset, "timeout": 30}
        result = self._api_call("getUpdates", params)
        if not result:
            return []
        updates = result.get("result", [])
        if updates:
            self._offset = updates[-1]["update_id"] + 1
        return updates

    def _send_reply(self, text: str) -> None:
        """Send a text reply (fire-and-forget)."""
        self._api_call("sendMessage", {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "Markdown",
        })

    def _is_authorized(self, update: dict) -> bool:
        """Check if the update comes from the authorized chat."""
        msg = update.get("message", {})
        chat = msg.get("chat", {})
        return str(chat.get("id", "")) == self.chat_id

    # -- command handlers --

    def _cmd_status(self) -> str:
        snap = self.state.snapshot()
        elapsed = time.time() - snap["start_time"]
        status = "PAUSED" if snap["paused"] else ("ALIVE" if snap["alive"] else "DEAD")
        return (
            f"*Protea Status*\n"
            f"Generation: {snap['generation']}\n"
            f"Status: {status}\n"
            f"Uptime: {elapsed:.0f}s\n"
            f"Mutation rate: {snap['mutation_rate']:.2f}\n"
            f"Max runtime: {snap['max_runtime_sec']:.0f}s"
        )

    def _cmd_history(self) -> str:
        rows = self.fitness.get_history(limit=10)
        if not rows:
            return "No history yet."
        lines = ["*Recent 10 generations:*"]
        for r in rows:
            surv = "OK" if r["survived"] else "FAIL"
            lines.append(
                f"Gen {r['generation']}  score={r['score']:.2f}  "
                f"{surv}  {r['runtime_sec']:.0f}s"
            )
        return "\n".join(lines)

    def _cmd_top(self) -> str:
        rows = self.fitness.get_best(n=5)
        if not rows:
            return "No fitness data yet."
        lines = ["*Top 5 generations:*"]
        for r in rows:
            surv = "OK" if r["survived"] else "FAIL"
            lines.append(
                f"Gen {r['generation']}  score={r['score']:.2f}  "
                f"{surv}  `{r['commit_hash'][:8]}`"
            )
        return "\n".join(lines)

    def _cmd_code(self) -> str:
        code_path = self.ring2_path / "main.py"
        try:
            source = code_path.read_text()
        except FileNotFoundError:
            return "ring2/main.py not found."
        if len(source) > 3000:
            source = source[:3000] + "\n... (truncated)"
        return f"```python\n{source}\n```"

    def _cmd_pause(self) -> str:
        if self.state.pause_event.is_set():
            return "Already paused."
        self.state.pause_event.set()
        return "Evolution paused."

    def _cmd_resume(self) -> str:
        if not self.state.pause_event.is_set():
            return "Not paused."
        self.state.pause_event.clear()
        return "Evolution resumed."

    def _cmd_kill(self) -> str:
        self.state.kill_event.set()
        return "Kill signal sent — Ring 2 will restart."

    def _cmd_help(self) -> str:
        return (
            "*Protea Bot Commands:*\n"
            "/status — current generation, uptime, state\n"
            "/history — recent 10 generations\n"
            "/top — top 5 by fitness\n"
            "/code — current Ring 2 source\n"
            "/pause — pause evolution loop\n"
            "/resume — resume evolution loop\n"
            "/kill — restart Ring 2 (no generation advance)"
        )

    # -- dispatch --

    _COMMANDS: dict[str, str] = {
        "/status": "_cmd_status",
        "/history": "_cmd_history",
        "/top": "_cmd_top",
        "/code": "_cmd_code",
        "/pause": "_cmd_pause",
        "/resume": "_cmd_resume",
        "/kill": "_cmd_kill",
        "/help": "_cmd_help",
        "/start": "_cmd_help",
    }

    def _handle_command(self, text: str) -> str:
        """Dispatch a command string and return the response text."""
        cmd = text.strip().split()[0].lower() if text.strip() else ""
        # Strip @botname suffix (e.g. "/status@MyBot")
        cmd = cmd.split("@")[0]
        method_name = self._COMMANDS.get(cmd)
        if method_name is None:
            return self._cmd_help()
        return getattr(self, method_name)()

    # -- main loop --

    def run(self) -> None:
        """Long-polling loop.  Intended to run in a daemon thread."""
        log.info("Telegram bot started (chat_id=%s)", self.chat_id)
        while self._running.is_set():
            try:
                updates = self._get_updates()
                for update in updates:
                    try:
                        if not self._is_authorized(update):
                            log.debug("Ignoring unauthorized update")
                            continue
                        text = update.get("message", {}).get("text", "")
                        if not text:
                            continue
                        reply = self._handle_command(text)
                        self._send_reply(reply)
                    except Exception:
                        log.debug("Error handling update", exc_info=True)
            except Exception:
                log.debug("Error in polling loop", exc_info=True)
                # Back off on repeated errors.
                if self._running.is_set():
                    time.sleep(5)
        log.info("Telegram bot stopped")

    def stop(self) -> None:
        """Signal the polling loop to stop."""
        self._running.clear()


# ---------------------------------------------------------------------------
# Factory + thread launcher
# ---------------------------------------------------------------------------

def create_bot(config, state: SentinelState, fitness, ring2_path: pathlib.Path) -> TelegramBot | None:
    """Create a TelegramBot from Ring1Config, or None if disabled/missing."""
    if not config.telegram_enabled:
        return None
    if not config.telegram_bot_token or not config.telegram_chat_id:
        log.warning("Telegram bot: enabled but token/chat_id missing — disabled")
        return None
    return TelegramBot(
        bot_token=config.telegram_bot_token,
        chat_id=config.telegram_chat_id,
        state=state,
        fitness=fitness,
        ring2_path=ring2_path,
    )


def start_bot_thread(bot: TelegramBot) -> threading.Thread:
    """Start the bot in a daemon thread and return the thread handle."""
    thread = threading.Thread(target=bot.run, name="telegram-bot", daemon=True)
    thread.start()
    return thread
