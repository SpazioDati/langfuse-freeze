"""
Build the prompt backup from the Langfuse API, given a specific project by its keys.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

from langfuse_freeze import FrozenLangfuse

public_key = os.environ.get("LANGFUSE_PUBLIC_KEY")
secret_key = os.environ.get("LANGFUSE_SECRET_KEY")
host = os.environ.get("LANGFUSE_HOST")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup-path", required=True, help="Path to the prompts backup json file")
    parser.add_argument("--public-key", default=os.getenv("LANGFUSE_PUBLIC_KEY"))
    parser.add_argument("--secret-key", default=os.getenv("LANGFUSE_SECRET_KEY"))
    parser.add_argument("--host", default=os.getenv("LANGFUSE_HOST"))
    args = parser.parse_args()
    try:
        FrozenLangfuse(
            prompts_backup_path=args.backup_path,
            host=args.host,
            public_key=args.public_key,
            secret_key=args.secret_key,
        ).bootstrap()
    except (RuntimeError, AssertionError):
        logging.exception("Bootstrap failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
