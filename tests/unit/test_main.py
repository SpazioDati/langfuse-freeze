from __future__ import annotations

from unittest.mock import patch

import pytest

from tests.conftest import _make_client


def test_init_handles_missing_backup(tmp_path):
    with pytest.raises(RuntimeError):
        _make_client(str(tmp_path / "nonexistent.json"))


def test_get_prompt_injects_text_fallback_production(backup_file):
    client = _make_client(backup_file)

    with patch("langfuse_freeze.main.Langfuse.get_prompt") as mock_super:
        client.get_prompt("ask-fitch", type="chat")
        _, kwargs = mock_super.call_args
        assert isinstance(kwargs["fallback"], list)
        assert kwargs["fallback"][0]["type"] == "chatmessage"
        assert kwargs["fallback"][0]["role"] == "system"
        assert kwargs["fallback"][0]["content"].startswith("## General Instruction\nToday is {{date}}.")


def test_get_prompt_injects_text_fallback_specific_label(backup_file):
    client = _make_client(backup_file)

    with patch("langfuse_freeze.main.Langfuse.get_prompt") as mock_super:
        client.get_prompt("sentovel-entities-select", type="text", label="dev")
        _, kwargs = mock_super.call_args
        assert kwargs["fallback"].startswith(
            "Sei un esperto di economia italiana e di ecosistemi dati aziendali. Oggi è {{today}}."
        )


def test_get_prompt_injects_chat_fallback_production(backup_file):
    client = _make_client(backup_file)

    with patch("langfuse_freeze.main.Langfuse.get_prompt") as mock_super:
        client.get_prompt("ask-fitch", type="chat", label="non-existing")
        _, kwargs = mock_super.call_args
        assert kwargs["fallback"][0]["type"] == "chatmessage"
        assert kwargs["fallback"][0]["role"] == "system"
        assert kwargs["fallback"][0]["content"].startswith("## General Instruction\nToday is {{date}}.")


def test_get_prompt_injects_chat_fallback_specific_label(backup_file):
    client = _make_client(backup_file)

    with patch("langfuse_freeze.main.Langfuse.get_prompt") as mock_super:
        client.get_prompt("sentovel-rag-select-text", type="text", label="dev")
        _, kwargs = mock_super.call_args

        assert kwargs["fallback"].startswith("Sei un esperto di economia italiana e oggi è {{today}}.")
        assert "## Passo 3 — Cerca corrispondenze per OGNI concetto" not in kwargs["fallback"]


def test_get_prompt_falls_back_to_production_for_unknown_label(backup_file):
    client = _make_client(backup_file)

    with patch("langfuse_freeze.main.Langfuse.get_prompt") as mock_super:
        client.get_prompt("sentovel-rag-select-text", type="text", label="nonexistent")
        _, kwargs = mock_super.call_args
        assert kwargs["fallback"].startswith(
            "Sei un esperto di economia italiana e di ecosistemi dati aziendali. Oggi è {{today}}."
        )


def test_get_prompt_does_not_override_explicit_fallback(backup_file):
    client = _make_client(backup_file)

    with patch("langfuse_freeze.main.Langfuse.get_prompt") as mock_super:
        client.get_prompt("sentovel-rag-select-text", type="text", fallback="custom fallback")
        _, kwargs = mock_super.call_args
        assert kwargs["fallback"] == "custom fallback"


def test_get_prompt_no_fallback_for_unknown_prompt(backup_file):
    client = _make_client(backup_file)

    with patch("langfuse_freeze.main.Langfuse.get_prompt") as mock_super:
        client.get_prompt("unknown-prompt", type="text")
        _, kwargs = mock_super.call_args
        assert "fallback" not in kwargs or kwargs.get("fallback") is None
