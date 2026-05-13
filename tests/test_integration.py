from __future__ import annotations

import json
import os

import pytest

from langfuse_freeze.main import LangfuseBacked

LANGFUSE_HOST = "http://localhost:10016"


@pytest.fixture(autouse=True)
def langfuse_env(monkeypatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", os.environ.get("LANGFUSE_PUBLIC_KEY", "pk-lf-1234"))
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", os.environ.get("LANGFUSE_SECRET_KEY", "sk-lf-1234"))
    monkeypatch.setenv("LANGFUSE_HOST", LANGFUSE_HOST)


@pytest.fixture
def fresh_backup(tmp_path, monkeypatch):
    backup_path = str(tmp_path / "prompts.json")
    monkeypatch.setenv("LANGFUSE_PROMPTS_BACKUP_PATH", backup_path)
    monkeypatch.setattr(LangfuseBacked, "PROMPTS_BACKUP_PATH", backup_path)
    return backup_path


@pytest.mark.integration
def test_bootstrap_fetches_and_writes_real_prompts(fresh_backup):
    LangfuseBacked.bootstrap()
    assert os.path.exists(fresh_backup)
    with open(fresh_backup) as f:
        data = json.load(f)

    assert len(data) > 0
    for _name, entry in data.items():
        assert entry["type"] in ("text", "chat")
        assert "labels" in entry
        assert "production" in entry["labels"]
        if entry["type"] == "chat":
            assert "content" in entry["labels"]["production"][0]
            assert "role" in entry["labels"]["production"][0]
        else:
            assert entry["labels"]["production"]
            assert isinstance(entry["labels"]["production"], str)


@pytest.mark.integration
def test_bootstrap_skips_existing_backup(fresh_backup):
    LangfuseBacked.bootstrap()
    mtime_first = os.path.getmtime(fresh_backup)
    LangfuseBacked.bootstrap()
    mtime_second = os.path.getmtime(fresh_backup)
    assert mtime_first == mtime_second


@pytest.mark.integration
def test_langfuse_backed_get_text_prompt(fresh_backup, monkeypatch):
    LangfuseBacked.bootstrap()

    with open(fresh_backup) as f:
        data = json.load(f)

    text_prompts = {k: v for k, v in data.items() if v["type"] == "text"}
    if not text_prompts:
        pytest.skip("No text prompts found in Langfuse")

    prompt_name = next(iter(text_prompts))
    client = LangfuseBacked(
        public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
        secret_key=os.environ["LANGFUSE_SECRET_KEY"],
        host=LANGFUSE_HOST,
    )
    from langfuse.model import TextPromptClient

    result = client.get_prompt(prompt_name, type="text")
    assert isinstance(result, TextPromptClient)


@pytest.mark.integration
def test_langfuse_backed_get_chat_prompt(fresh_backup, monkeypatch):
    LangfuseBacked.bootstrap()

    with open(fresh_backup) as f:
        data = json.load(f)

    chat_prompts = {k: v for k, v in data.items() if v["type"] == "chat"}
    if not chat_prompts:
        pytest.skip("No chat prompts found in Langfuse")

    prompt_name = next(iter(chat_prompts))
    client = LangfuseBacked(
        public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
        secret_key=os.environ["LANGFUSE_SECRET_KEY"],
        host=LANGFUSE_HOST,
    )
    from langfuse.model import ChatPromptClient

    result = client.get_prompt(prompt_name, type="chat")
    assert isinstance(result, ChatPromptClient)


@pytest.mark.integration
def test_fallback_used_when_langfuse_unreachable(fresh_backup):
    LangfuseBacked.bootstrap()

    with open(fresh_backup) as f:
        data = json.load(f)

    if not data:
        pytest.skip("No prompts in backup")

    prompt_name = next(iter(data))
    prompt_type = data[prompt_name]["type"]

    client = LangfuseBacked(
        public_key="pk-lf-invalid",
        secret_key="sk-lf-invalid",
        host="http://localhost:19999",
    )
    result = client.get_prompt(prompt_name, type=prompt_type)
    assert result is not None
