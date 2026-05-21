from __future__ import annotations

import gzip
import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING, Literal, TypedDict, overload

from langfuse import Langfuse

if TYPE_CHECKING:
    from langfuse.api import PromptMeta
    from langfuse.model import (
        ChatMessageDict,
        ChatMessageWithPlaceholdersDict_Message,
        ChatMessageWithPlaceholdersDict_Placeholder,
        ChatPromptClient,
        PromptClient,
        TextPromptClient,
    )

logger = logging.getLogger(__name__)


class _PromptEntry(TypedDict):
    type: str
    labels: dict[
        str, str | list[ChatMessageWithPlaceholdersDict_Message | ChatMessageWithPlaceholdersDict_Placeholder]
    ]


class FrozenLangfuse(Langfuse):
    def __init__(self, *, prompts_backup_path: str, **kwargs):
        super().__init__(**kwargs)
        self._prompts_backup_path = prompts_backup_path
        self._prompts_backup: dict = {}
        try:
            with gzip.open(prompts_backup_path, "rt") as f:
                prompts_backup = json.load(f)
            self._prompts_backup = self._normalize_backup(prompts_backup)
            logger.info("Loaded %d prompts from backup", len(self._prompts_backup))

        except FileNotFoundError:
            logger.warning(
                "No prompts backup found at %s. Run .bootstrap() to create it.",
                prompts_backup_path,
            )

        except json.JSONDecodeError as e:
            raise RuntimeError(f"Prompts backup at {prompts_backup_path} contains invalid JSON: {e}") from e

        except Exception as e:
            raise RuntimeError(f"Failed to load prompts backup from {prompts_backup_path}: {e}") from e

    def _get_fallback(self, name: str, label: str | None):
        entry = self._prompts_backup.get(name)
        if entry is None:
            logger.warning("Asking for a prompt that is not present in the backup")
            return None

        labels: dict = entry.get("labels", {})
        # [gg] if we are missing the label fallback to 'production' always present.
        key = label if label in labels else "production"
        return labels.get(key)

    @overload
    def get_prompt(
        self,
        name: str,
        *,
        version: int | None = None,
        label: str | None = None,
        type: Literal["chat"],
        cache_ttl_seconds: int | None = None,
        fallback: list[ChatMessageDict] | None = None,
        max_retries: int | None = None,
        fetch_timeout_seconds: int | None = None,
    ) -> ChatPromptClient: ...

    @overload
    def get_prompt(
        self,
        name: str,
        *,
        version: int | None = None,
        label: str | None = None,
        type: Literal["text"] = "text",
        cache_ttl_seconds: int | None = None,
        fallback: str | None = None,
        max_retries: int | None = None,
        fetch_timeout_seconds: int | None = None,
    ) -> TextPromptClient: ...

    def get_prompt(self, name, **kwargs) -> PromptClient:
        if "fallback" not in kwargs or kwargs["fallback"] is None:
            local_fallback = self._get_fallback(name, kwargs.get("label"))
            kwargs["fallback"] = local_fallback

        return super().get_prompt(name, **kwargs)

    def bootstrap(self, overwrite: bool = False, max_retries: int = 3, retry_delay: int = 2) -> None:
        if os.path.exists(self._prompts_backup_path) and not overwrite:
            logger.info("Backup already present at %s, skipping", self._prompts_backup_path)
            return

        for attempt in range(max_retries):
            try:
                prompts = self._fetch_all_prompts()
            except Exception as exc:
                logger.warning("Fetch attempt %d/%d failed: %s", attempt + 1, max_retries, exc)
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (2**attempt))
            else:
                self._prompts_backup = prompts
                self._write_backup(prompts, self._prompts_backup_path)
                logger.info("Saved %d prompts to %s", len(prompts), self._prompts_backup_path)
                return

        raise RuntimeError(f"Failed to fetch prompts from Langfuse after {max_retries} attempts")

    def _fetch_all_prompts(self) -> dict:
        prompts_backup: dict[str, _PromptEntry] = {}
        page = 1
        futures = []
        with ThreadPoolExecutor() as executor:
            while True:
                prompts_metadata = self._load_prompt_metadata_response_page(page)
                if not prompts_metadata:
                    break
                for prompt_meta in prompts_metadata:
                    for label in prompt_meta.labels:
                        futures.append(executor.submit(self._fetch_prompt, prompt_meta, label))
                page += 1
            for future in as_completed(futures):
                prompt_meta, label, prompt = future.result()
                prompt_data = prompts_backup.setdefault(
                    prompt_meta.name,
                    {"type": prompt_meta.type, "labels": {}},
                )
                prompt_data["labels"][label] = prompt.prompt

        return prompts_backup

    def _load_prompt_metadata_response_page(self, page: int) -> list[PromptMeta]:
        return self.api.prompts.list(page=page).data

    def _fetch_prompt(
        self, prompt_meta: PromptMeta, label: str
    ) -> tuple[PromptMeta, str, PromptClient | TextPromptClient | ChatPromptClient]:
        return prompt_meta, label, self.get_prompt(name=prompt_meta.name, label=label, type=prompt_meta.type.value)

    @staticmethod
    def _normalize_chat_message(msg: dict) -> dict:
        """Normalize chat messages for langfuse v3/v4 compatibility.
        v3 used type='message'; v4 uses 'chatmessage' or 'placeholder'.
        """
        if "name" in msg and "role" not in msg and "content" not in msg:
            msg["type"] = "placeholder"

        elif "role" in msg and "content" in msg:
            msg["type"] = "chatmessage"

        return msg

    @classmethod
    def _normalize_backup(cls, backup: dict) -> dict:
        """Normalize legacy v3 backups to v4 schema."""
        for _name, entry in backup.items():
            if not isinstance(entry, dict) or entry.get("type") != "chat":
                continue
            labels = entry.get("labels", {})
            for label, prompt in labels.items():
                if isinstance(prompt, list):
                    labels[label] = [cls._normalize_chat_message(m) for m in prompt]
        return backup

    @classmethod
    def _write_backup(cls, prompts: dict, path: str) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with gzip.open(path, "wt") as f:
            json.dump(prompts, f, indent=2)
