from __future__ import annotations

from langfuse_freeze.main import FrozenLangfuse


def test_v3_message_becomes_chatmessage():
    backup = {
        "my-prompt": {
            "type": "chat",
            "labels": {
                "production": [{"role": "system", "content": "Hello", "type": "message"}],
            },
        }
    }
    result = FrozenLangfuse._normalize_backup(backup)
    msg = result["my-prompt"]["labels"]["production"][0]
    assert msg["type"] == "chatmessage"


def test_v3_placeholder_becomes_placeholder():
    backup = {
        "my-prompt": {
            "type": "chat",
            "labels": {
                "production": [{"name": "history"}],
            },
        }
    }
    result = FrozenLangfuse._normalize_backup(backup)
    msg = result["my-prompt"]["labels"]["production"][0]
    assert msg["type"] == "placeholder"


def test_v4_chatmessage_unchanged():
    backup = {
        "my-prompt": {
            "type": "chat",
            "labels": {
                "production": [{"role": "user", "content": "Hi", "type": "chatmessage"}],
            },
        }
    }
    result = FrozenLangfuse._normalize_backup(backup)
    msg = result["my-prompt"]["labels"]["production"][0]
    assert msg["type"] == "chatmessage"


def test_text_prompt_not_touched():
    backup = {
        "my-prompt": {
            "type": "text",
            "labels": {"production": "some text"},
        }
    }
    result = FrozenLangfuse._normalize_backup(backup)
    assert result["my-prompt"]["labels"]["production"] == "some text"


def test_mixed_prompts_normalizes_only_chat():
    backup = {
        "chat-prompt": {
            "type": "chat",
            "labels": {
                "production": [{"role": "system", "content": "Hi", "type": "message"}],
            },
        },
        "text-prompt": {
            "type": "text",
            "labels": {"production": "raw text"},
        },
    }
    result = FrozenLangfuse._normalize_backup(backup)
    assert result["chat-prompt"]["labels"]["production"][0]["type"] == "chatmessage"
    assert result["text-prompt"]["labels"]["production"] == "raw text"
