"""Langfuse Freeze."""

from __future__ import annotations

import os

from langfuse_freeze.main import LangfuseBacked

if not os.environ.get("LANGFUSE_DISABLE_BOOTSTRAP"):
    try:
        LangfuseBacked.bootstrap()
    except Exception as e:
        raise RuntimeError(
            f"Langfuse bootstrap failed at import time. Set LANGFUSE_DISABLE_BOOTSTRAP=1 to skip. Original error: {e}"
        ) from e
