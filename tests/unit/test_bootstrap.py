from __future__ import annotations

import gzip
import json
import logging
import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from langfuse_freeze import FrozenLangfuse


@pytest.fixture
def backup_path(tmp_path):
    return str(tmp_path / "prompts.json.gz")


@pytest.fixture
def client(backup_path):
    """Create a FrozenLangfuse instance with mocked Langfuse parent init."""
    with patch("langfuse_freeze.client.Langfuse.__init__", return_value=None):
        return FrozenLangfuse(prompts_backup_path=backup_path)


def test_bootstrap_skips_if_backup_exists(backup_path, caplog):
    with gzip.open(backup_path, "wt") as f:
        json.dump({}, f)

    with patch("langfuse_freeze.client.Langfuse.__init__", return_value=None):
        client = FrozenLangfuse(prompts_backup_path=backup_path)

    with (
        caplog.at_level(logging.INFO, logger="langfuse_freeze.client"),
        patch.object(client, "_fetch_all_prompts") as mock_fetch,
    ):
        client.bootstrap()
        mock_fetch.assert_not_called()

    assert "skipping" in caplog.text


def test_bootstrap_fetches_if_backup_missing(client, backup_path):
    fake_prompts = {"my-prompt": {"type": "text", "labels": {"production": "hello"}}}

    with patch.object(client, "_fetch_all_prompts", return_value=fake_prompts) as mock_fetch:
        client.bootstrap()
        mock_fetch.assert_called_once()

    assert os.path.exists(backup_path)
    with gzip.open(backup_path, "rt") as f:
        assert json.load(f) == fake_prompts


def test_bootstrap_retries_on_failure(client, backup_path):
    fake_prompts = {"p": {"type": "text", "labels": {"production": "x"}}}
    call_count = 0

    def flaky_fetch():
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise ConnectionError("timeout")
        return fake_prompts

    with patch.object(client, "_fetch_all_prompts", side_effect=flaky_fetch):
        client.bootstrap(max_retries=3, retry_delay=0)

    assert call_count == 2
    assert os.path.exists(backup_path)


def test_bootstrap_raises_after_max_retries(client):
    with (
        patch.object(client, "_fetch_all_prompts", side_effect=ConnectionError("down")),
        pytest.raises(RuntimeError, match="3 attempts"),
    ):
        client.bootstrap(max_retries=3, retry_delay=0)


def test_bootstrap_overwrites_when_requested(backup_path):
    with gzip.open(backup_path, "wt") as f:
        json.dump({"old": {"type": "text", "labels": {"production": "old"}}}, f)

    with patch("langfuse_freeze.client.Langfuse.__init__", return_value=None):
        client = FrozenLangfuse(prompts_backup_path=backup_path)

    new_prompts = {"new": {"type": "text", "labels": {"production": "new"}}}

    with patch.object(client, "_fetch_all_prompts", return_value=new_prompts):
        client.bootstrap(overwrite=True)

    with gzip.open(backup_path, "rt") as f:
        assert json.load(f) == new_prompts


def test_fetch_all_prompts_paginates_and_collects(client):
    """Test _fetch_all_prompts fetches prompts across pages and labels."""
    text_type = SimpleNamespace(value="text")
    chat_type = SimpleNamespace(value="chat")
    prompt_meta_1 = SimpleNamespace(name="prompt-a", type=text_type, labels=["production", "dev"])
    prompt_meta_2 = SimpleNamespace(name="prompt-b", type=chat_type, labels=["production"])

    fake_prompt_a_prod = MagicMock()
    fake_prompt_a_prod.prompt = "Hello production"
    fake_prompt_a_dev = MagicMock()
    fake_prompt_a_dev.prompt = "Hello dev"
    fake_prompt_b_prod = MagicMock()
    fake_prompt_b_prod.prompt = [{"role": "system", "content": "Hi"}]

    def mock_load_page(page):
        if page == 1:
            return [prompt_meta_1, prompt_meta_2]
        return []

    def mock_get_prompt(name, label, type):  # noqa: A002
        lookup = {
            ("prompt-a", "production"): fake_prompt_a_prod,
            ("prompt-a", "dev"): fake_prompt_a_dev,
            ("prompt-b", "production"): fake_prompt_b_prod,
        }
        return lookup[(name, label)]

    with (
        patch.object(client, "_load_prompt_metadata_response_page", side_effect=mock_load_page),
        patch.object(client, "get_prompt", side_effect=mock_get_prompt),
    ):
        result = client._fetch_all_prompts()

    assert result["prompt-a"]["type"] == text_type
    assert result["prompt-a"]["labels"]["production"] == "Hello production"
    assert result["prompt-a"]["labels"]["dev"] == "Hello dev"
    assert result["prompt-b"]["type"] == chat_type
    assert result["prompt-b"]["labels"]["production"] == [{"role": "system", "content": "Hi"}]
