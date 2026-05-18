from __future__ import annotations

import json
import logging
import os
from unittest.mock import patch

import pytest

from langfuse_freeze.main import FrozenLangfuse


@pytest.fixture(autouse=True)
def isolated_backup_path(tmp_path, monkeypatch):
    backup_path = str(tmp_path / "prompts.json")
    monkeypatch.setattr(FrozenLangfuse, "PROMPTS_BACKUP_PATH", backup_path)
    return backup_path


@pytest.fixture
def langfuse_env(monkeypatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")
    monkeypatch.setenv("LANGFUSE_HOST", "http://localhost:3030")


def test_bootstrap_skips_if_backup_exists(isolated_backup_path, caplog):
    with open(isolated_backup_path, "w") as f:
        json.dump({}, f)

    with (
        caplog.at_level(logging.INFO, logger="langfuse_freeze.main"),
        patch.object(FrozenLangfuse, "_fetch_all_prompts") as mock_fetch,
    ):
        FrozenLangfuse.bootstrap()
        mock_fetch.assert_not_called()

    assert "skipping" in caplog.text


def test_bootstrap_fetches_if_backup_missing(isolated_backup_path, langfuse_env):
    fake_prompts = {"my-prompt": {"type": "text", "labels": {"production": "hello"}}}

    with patch.object(FrozenLangfuse, "_fetch_all_prompts", return_value=fake_prompts) as mock_fetch:
        FrozenLangfuse.bootstrap()
        mock_fetch.assert_called_once_with("pk-test", "sk-test", "http://localhost:3030")

    assert os.path.exists(isolated_backup_path)
    with open(isolated_backup_path) as f:
        assert json.load(f) == fake_prompts


def test_bootstrap_retries_on_failure(isolated_backup_path, langfuse_env, monkeypatch):
    import langfuse_freeze.main as main_module

    monkeypatch.setattr(main_module, "_MAX_RETRIES", 3)
    monkeypatch.setattr(main_module, "_RETRY_DELAY", 0)

    fake_prompts = {"p": {"type": "text", "labels": {"production": "x"}}}
    call_count = 0

    def flaky_fetch(*args):
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise ConnectionError("timeout")
        return fake_prompts

    with patch.object(FrozenLangfuse, "_fetch_all_prompts", side_effect=flaky_fetch):
        FrozenLangfuse.bootstrap()

    assert call_count == 2
    assert os.path.exists(isolated_backup_path)


def test_bootstrap_raises_after_max_retries(isolated_backup_path, langfuse_env, monkeypatch):
    import langfuse_freeze.main as main_module

    monkeypatch.setattr(main_module, "_MAX_RETRIES", 3)
    monkeypatch.setattr(main_module, "_RETRY_DELAY", 0)

    with (
        patch.object(FrozenLangfuse, "_fetch_all_prompts", side_effect=ConnectionError("down")),
        pytest.raises(RuntimeError, match="3 attempts"),
    ):
        FrozenLangfuse.bootstrap()


def test_bootstrap_missing_public_key_raises(isolated_backup_path, monkeypatch):
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")
    monkeypatch.setenv("LANGFUSE_HOST", "http://localhost:3030")

    with pytest.raises(AssertionError, match="LANGFUSE_PUBLIC_KEY"):
        FrozenLangfuse.bootstrap()
