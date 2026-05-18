from __future__ import annotations

import logging
import os
import sys

logging.basicConfig(level=logging.INFO)

os.environ["LANGFUSE_DISABLE_IMPLICIT_BOOTSTRAP"] = "1"

from langfuse_freeze.main import FrozenLangfuse  # noqa: E402


def main() -> None:
    try:
        FrozenLangfuse.bootstrap()
    except (RuntimeError, AssertionError):
        logging.exception("Bootstrap failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
