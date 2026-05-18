"""Langfuse Freeze."""

from __future__ import annotations

import os

from langfuse_freeze.client import FrozenLangfuse

__all__ = ["FrozenLangfuse"]

if not os.environ.get("LANGFUSE_DISABLE_IMPLICIT_BOOTSTRAP"):
    try:
        FrozenLangfuse.bootstrap()
    except Exception as e:
        raise RuntimeError(
            f"Langfuse bootstrap failed at import time. Set LANGFUSE_DISABLE_IMPLICIT_BOOTSTRAP=1 to skip. Original error: {e}"
        ) from e
