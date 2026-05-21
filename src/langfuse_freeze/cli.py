from __future__ import annotations

import logging
import sys

from langfuse_freeze import FrozenLangfuse


def main() -> None:
    try:
        FrozenLangfuse(prompts_backup_path=sys.argv[1]).bootstrap()
    except (RuntimeError, AssertionError):
        logging.exception("Bootstrap failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
