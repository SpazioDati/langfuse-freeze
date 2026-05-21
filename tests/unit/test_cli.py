from __future__ import annotations

from unittest.mock import patch

import pytest

from langfuse_freeze.cli import main


def test_cli_bootstrap_success(tmp_path):
    backup_path = str(tmp_path / "prompts.json.gz")

    with (
        patch("langfuse_freeze.client.Langfuse.__init__", return_value=None),
        patch(
            "langfuse_freeze.client.FrozenLangfuse._fetch_all_prompts",
            return_value={"p": {"type": "text", "labels": {"production": "x"}}},
        ),
        patch("sys.argv", ["langfuse-freeze-bootstrap", "--backup-path", backup_path]),
    ):
        main()


def test_cli_bootstrap_exits_on_failure(tmp_path):
    backup_path = str(tmp_path / "prompts.json.gz")

    with (
        patch("langfuse_freeze.client.Langfuse.__init__", return_value=None),
        patch("langfuse_freeze.client.FrozenLangfuse._fetch_all_prompts", side_effect=ConnectionError("down")),
        patch("sys.argv", ["langfuse-freeze-bootstrap", "--backup-path", backup_path]),
        pytest.raises(SystemExit, match="1"),
    ):
        main()
