"""Tests for ring1.config."""

import os
import pathlib

import pytest

from ring1.config import Ring1Config, _load_dotenv, load_ring1_config


class TestLoadDotenv:
    def test_loads_key_value(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("FOO_TEST_KEY=bar123\n")
        # Ensure it doesn't already exist.
        os.environ.pop("FOO_TEST_KEY", None)
        _load_dotenv(tmp_path)
        assert os.environ["FOO_TEST_KEY"] == "bar123"
        os.environ.pop("FOO_TEST_KEY", None)

    def test_ignores_comments_and_blanks(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("# comment\n\nKEY_TEST_X=val\n")
        os.environ.pop("KEY_TEST_X", None)
        _load_dotenv(tmp_path)
        assert os.environ["KEY_TEST_X"] == "val"
        os.environ.pop("KEY_TEST_X", None)

    def test_strips_quotes(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text('QUOTED_TEST="hello world"\n')
        os.environ.pop("QUOTED_TEST", None)
        _load_dotenv(tmp_path)
        assert os.environ["QUOTED_TEST"] == "hello world"
        os.environ.pop("QUOTED_TEST", None)

    def test_strips_single_quotes(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("SQ_TEST='hello'\n")
        os.environ.pop("SQ_TEST", None)
        _load_dotenv(tmp_path)
        assert os.environ["SQ_TEST"] == "hello"
        os.environ.pop("SQ_TEST", None)

    def test_does_not_overwrite_existing(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("EXIST_TEST_KEY=new\n")
        os.environ["EXIST_TEST_KEY"] = "old"
        _load_dotenv(tmp_path)
        assert os.environ["EXIST_TEST_KEY"] == "old"
        os.environ.pop("EXIST_TEST_KEY", None)

    def test_missing_env_file(self, tmp_path):
        # Should not raise.
        _load_dotenv(tmp_path)

    def test_skips_empty_value(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("EMPTY_VAL_TEST=\n")
        os.environ.pop("EMPTY_VAL_TEST", None)
        _load_dotenv(tmp_path)
        # Empty values are skipped.
        assert "EMPTY_VAL_TEST" not in os.environ


class TestLoadRing1Config:
    def _make_project(self, tmp_path, toml_extra="", env_lines=""):
        """Create a minimal project directory with config.toml and .env."""
        cfg_dir = tmp_path / "config"
        cfg_dir.mkdir()
        toml_content = (
            "[ring0]\n"
            "heartbeat_interval_sec = 2\n"
            "heartbeat_timeout_sec = 6\n"
            "max_cpu_percent = 80.0\n"
            "max_memory_percent = 80.0\n"
            "max_disk_percent = 90.0\n"
            '[ring0.git]\nring2_path = "ring2"\n'
            '[ring0.fitness]\ndb_path = "data/protea.db"\n'
            "[ring0.evolution]\nseed = 42\n"
        )
        toml_content += toml_extra
        (cfg_dir / "config.toml").write_text(toml_content)
        if env_lines:
            (tmp_path / ".env").write_text(env_lines)
        return tmp_path

    def test_defaults(self, tmp_path):
        root = self._make_project(tmp_path)
        # Clear env vars.
        for key in ("CLAUDE_API_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
            os.environ.pop(key, None)
        cfg = load_ring1_config(root)
        assert isinstance(cfg, Ring1Config)
        assert cfg.claude_model == "claude-sonnet-4-5-20250929"
        assert cfg.claude_max_tokens == 4096
        assert cfg.telegram_enabled is False
        assert cfg.max_prompt_history == 10

    def test_reads_toml_values(self, tmp_path):
        extra = (
            "\n[ring1]\n"
            'claude_model = "claude-haiku-3"\n'
            "claude_max_tokens = 2048\n"
            "max_prompt_history = 5\n"
            "\n[ring1.telegram]\n"
            "enabled = true\n"
        )
        root = self._make_project(tmp_path, toml_extra=extra)
        os.environ.pop("CLAUDE_API_KEY", None)
        os.environ.pop("TELEGRAM_BOT_TOKEN", None)
        os.environ.pop("TELEGRAM_CHAT_ID", None)
        cfg = load_ring1_config(root)
        assert cfg.claude_model == "claude-haiku-3"
        assert cfg.claude_max_tokens == 2048
        assert cfg.max_prompt_history == 5
        assert cfg.telegram_enabled is True

    def test_reads_env_secrets(self, tmp_path):
        env = (
            "CLAUDE_API_KEY=sk-test-123\n"
            "TELEGRAM_BOT_TOKEN=bot-tok\n"
            "TELEGRAM_CHAT_ID=12345\n"
        )
        root = self._make_project(tmp_path, env_lines=env)
        # Clear first so .env takes effect.
        for key in ("CLAUDE_API_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
            os.environ.pop(key, None)
        cfg = load_ring1_config(root)
        assert cfg.claude_api_key == "sk-test-123"
        assert cfg.telegram_bot_token == "bot-tok"
        assert cfg.telegram_chat_id == "12345"
        # Cleanup.
        for key in ("CLAUDE_API_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
            os.environ.pop(key, None)

    def test_is_namedtuple(self, tmp_path):
        root = self._make_project(tmp_path)
        for key in ("CLAUDE_API_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
            os.environ.pop(key, None)
        cfg = load_ring1_config(root)
        # NamedTuple should be immutable.
        with pytest.raises(AttributeError):
            cfg.claude_model = "other"  # type: ignore[misc]

    def test_p1_defaults(self, tmp_path):
        """P1 fields should default when no [ring1.autonomy] section."""
        root = self._make_project(tmp_path)
        for key in ("CLAUDE_API_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
            os.environ.pop(key, None)
        cfg = load_ring1_config(root)
        assert cfg.p1_enabled is True
        assert cfg.p1_idle_threshold_sec == 600
        assert cfg.p1_check_interval_sec == 60

    def test_p1_reads_toml_values(self, tmp_path):
        """P1 fields should be read from [ring1.autonomy]."""
        extra = (
            "\n[ring1.autonomy]\n"
            "enabled = false\n"
            "idle_threshold_sec = 300\n"
            "check_interval_sec = 30\n"
        )
        root = self._make_project(tmp_path, toml_extra=extra)
        for key in ("CLAUDE_API_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
            os.environ.pop(key, None)
        cfg = load_ring1_config(root)
        assert cfg.p1_enabled is False
        assert cfg.p1_idle_threshold_sec == 300
        assert cfg.p1_check_interval_sec == 30
