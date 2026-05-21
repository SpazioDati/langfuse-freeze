from __future__ import annotations

import gzip
import json
import os

import pytest
from langfuse import Langfuse

from langfuse_freeze import FrozenLangfuse

LANGFUSE_HOST = "http://localhost:3000"
LANGFUSE_PUBLIC_KEY = "lf_pk_1234567890"
LANGFUSE_SECRET_KEY = "lf_sk_1234567890"


@pytest.fixture(scope="session", autouse=True)
def langfuse_setup(cassette):
    langfuse = Langfuse(public_key=LANGFUSE_PUBLIC_KEY, secret_key=LANGFUSE_SECRET_KEY, host=LANGFUSE_HOST)
    for name, label_data in cassette["prompts"].items():
        first_label = next(iter(label_data.values()))
        for label, data in label_data.items():
            if isinstance(data["prompt"], list):
                for message in data["prompt"]:
                    message["type"] = "chatmessage"
            langfuse.create_prompt(name=name, type=first_label["type"], prompt=data["prompt"], labels=[label])
    return


@pytest.fixture
def fresh_backup(tmp_path):
    return str(tmp_path / "prompts.json.gz")


def _make_integration_client(backup_path):
    return FrozenLangfuse(
        prompts_backup_path=backup_path,
        public_key=os.environ.get("LANGFUSE_PUBLIC_KEY", LANGFUSE_PUBLIC_KEY),
        secret_key=os.environ.get("LANGFUSE_SECRET_KEY", LANGFUSE_SECRET_KEY),
        host=LANGFUSE_HOST,
    )


@pytest.mark.integration
def test_bootstrap_fetches_and_writes_real_prompts(fresh_backup):
    client = _make_integration_client(fresh_backup)
    client.bootstrap()
    assert os.path.exists(fresh_backup)
    with gzip.open(fresh_backup, "rt") as f:
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
    client = _make_integration_client(fresh_backup)
    client.bootstrap()
    mtime_first = os.path.getmtime(fresh_backup)
    client.bootstrap()
    mtime_second = os.path.getmtime(fresh_backup)
    assert mtime_first == mtime_second


@pytest.mark.integration
def test_langfuse_backed_get_text_prompt(fresh_backup):
    client = _make_integration_client(fresh_backup)
    client.bootstrap()

    with gzip.open(fresh_backup, "rt") as f:
        data = json.load(f)

    text_prompts = {k: v for k, v in data.items() if v["type"] == "text"}
    if not text_prompts:
        pytest.skip("No text prompts found in Langfuse")

    prompt_name = next(iter(text_prompts))
    from langfuse.model import TextPromptClient

    result = client.get_prompt(prompt_name, type="text")
    assert isinstance(result, TextPromptClient)


@pytest.mark.integration
def test_langfuse_backed_get_chat_prompt(fresh_backup):
    client = _make_integration_client(fresh_backup)
    client.bootstrap()

    with gzip.open(fresh_backup, "rt") as f:
        data = json.load(f)

    chat_prompts = {k: v for k, v in data.items() if v["type"] == "chat"}
    if not chat_prompts:
        pytest.skip("No chat prompts found in Langfuse")

    prompt_name = next(iter(chat_prompts))
    from langfuse.model import ChatPromptClient

    result = client.get_prompt(prompt_name, type="chat")
    assert isinstance(result, ChatPromptClient)


@pytest.mark.integration
def test_fallback_used_when_langfuse_unreachable(fresh_backup):
    client = _make_integration_client(fresh_backup)
    client.bootstrap()

    with gzip.open(fresh_backup, "rt") as f:
        data = json.load(f)

    if not data:
        pytest.skip("No prompts in backup")

    prompt_name = next(iter(data))
    prompt_type = data[prompt_name]["type"]

    # Create a client pointing to an unreachable host but with the same backup
    unreachable_client = FrozenLangfuse(
        prompts_backup_path=fresh_backup,
        public_key="pk-lf-invalid",
        secret_key="sk-lf-invalid",
        host="http://localhost:19999",
    )
    result = unreachable_client.get_prompt(prompt_name, type=prompt_type)
    assert result is not None
