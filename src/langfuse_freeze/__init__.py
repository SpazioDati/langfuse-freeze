"""Langfuse Freeze."""

from __future__ import annotations

import os

from langfuse_freeze.main import LangfuseBacked

if not os.environ.get("LANGFUSE_DISABLE_BOOTSTRAP"):
    LangfuseBacked.bootstrap()
