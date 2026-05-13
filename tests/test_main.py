from __future__ import annotations

import json
from unittest.mock import patch

import pytest


@pytest.fixture
def backup_file(tmp_path):
    path = tmp_path / "prompts.json"
    prompts = {
        "text-prompt": {
            "type": "text",
            "labels": {
                "production": "You are a helpful assistant.",
                "dev": "You are a dev assistant.",
            },
        },
        "chat-prompt": {
            "type": "chat",
            "labels": {
                "production": [{"role": "system", "content": "You are a bot."}],
                "dev": [{"role": "system", "content": "You are a dev bot."}],
            },
        },
    }
    path.write_text(json.dumps(prompts))
    return str(path)


def _make_client(backup_path):
    from langfuse_freeze.main import LangfuseBacked

    client = LangfuseBacked.__new__(LangfuseBacked)
    client.PROMPTS_BACKUP_PATH = backup_path
    with patch("langfuse_freeze.main.Langfuse.__init__", return_value=None):
        LangfuseBacked.__init__(client)
    return client


def test_init_loads_backup(backup_file):
    client = _make_client(backup_file)
    assert "text-prompt" in client._prompts_backup
    assert "chat-prompt" in client._prompts_backup


def test_init_handles_missing_backup(tmp_path):
    client = _make_client(str(tmp_path / "nonexistent.json"))
    assert client._prompts_backup == {}


def test_get_prompt_injects_text_fallback_production(backup_file):
    client = _make_client(backup_file)

    with patch("langfuse_freeze.main.Langfuse.get_prompt") as mock_super:
        client.get_prompt("text-prompt", type="text")
        _, kwargs = mock_super.call_args
        assert kwargs["fallback"] == "You are a helpful assistant."


def test_get_prompt_injects_text_fallback_specific_label(backup_file):
    client = _make_client(backup_file)

    with patch("langfuse_freeze.main.Langfuse.get_prompt") as mock_super:
        client.get_prompt("text-prompt", type="text", label="dev")
        _, kwargs = mock_super.call_args
        assert kwargs["fallback"] == "You are a dev assistant."


def test_get_prompt_injects_chat_fallback_production(backup_file):
    client = _make_client(backup_file)

    with patch("langfuse_freeze.main.Langfuse.get_prompt") as mock_super:
        client.get_prompt("chat-prompt", type="chat")
        _, kwargs = mock_super.call_args
        assert kwargs["fallback"] == [{"role": "system", "content": "You are a bot."}]


def test_get_prompt_injects_chat_fallback_specific_label(backup_file):
    client = _make_client(backup_file)

    with patch("langfuse_freeze.main.Langfuse.get_prompt") as mock_super:
        client.get_prompt("chat-prompt", type="chat", label="dev")
        _, kwargs = mock_super.call_args
        assert kwargs["fallback"] == [{"role": "system", "content": "You are a dev bot."}]


def test_get_prompt_falls_back_to_production_for_unknown_label(backup_file):
    client = _make_client(backup_file)

    with patch("langfuse_freeze.main.Langfuse.get_prompt") as mock_super:
        client.get_prompt("text-prompt", type="text", label="nonexistent")
        _, kwargs = mock_super.call_args
        assert kwargs["fallback"] == "You are a helpful assistant."


def test_get_prompt_does_not_override_explicit_fallback(backup_file):
    client = _make_client(backup_file)

    with patch("langfuse_freeze.main.Langfuse.get_prompt") as mock_super:
        client.get_prompt("text-prompt", type="text", fallback="custom fallback")
        _, kwargs = mock_super.call_args
        assert kwargs["fallback"] == "custom fallback"


def test_get_prompt_no_fallback_for_unknown_prompt(backup_file):
    client = _make_client(backup_file)

    with patch("langfuse_freeze.main.Langfuse.get_prompt") as mock_super:
        client.get_prompt("unknown-prompt", type="text")
        _, kwargs = mock_super.call_args
        assert "fallback" not in kwargs or kwargs.get("fallback") is None
