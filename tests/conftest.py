from __future__ import annotations

import gzip
import os
from unittest.mock import patch

os.environ.setdefault("LANGFUSE_DISABLE_IMPLICIT_BOOTSTRAP", "1")

import json
from pathlib import Path

import pytest

CASSETTE_PATH = Path(__file__).parent / "resources" / "prompts_cassette.json.gz"


def _make_client(backup_path):
    from langfuse_freeze import FrozenLangfuse

    client = FrozenLangfuse.__new__(FrozenLangfuse)
    client.PROMPTS_BACKUP_PATH = backup_path
    with patch("langfuse_freeze.client.Langfuse.__init__", return_value=None):
        FrozenLangfuse.__init__(client)
    return client


@pytest.fixture
def cassette():
    with gzip.open(CASSETTE_PATH, "rt") as f:
        return json.load(f)


@pytest.fixture
def backup_file(cassette, tmp_path):
    backup = {}
    for name, label_data in cassette["prompts"].items():
        first_label = next(iter(label_data.values()))
        labels = {label: data["prompt"] for label, data in label_data.items()}
        backup[name] = {"type": first_label["type"], "labels": labels}
    path = tmp_path / "prompts.json.gz"
    with gzip.open(path, "wt") as f:
        json.dump(backup, f)
    return str(path)
