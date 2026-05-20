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

_PROMPTS_BACKUP_PATH = os.environ.get("LANGFUSE_PROMPTS_BACKUP_PATH", "./langfuse-backup/prompts.json.gz")
_MAX_RETRIES = int(os.environ.get("LANGFUSE_BOOTSTRAP_MAX_RETRIES", "3"))
_RETRY_DELAY = float(os.environ.get("LANGFUSE_BOOTSTRAP_RETRY_DELAY", "2"))


class _PromptEntry(TypedDict):
    type: str
    labels: dict[
        str, str | list[ChatMessageWithPlaceholdersDict_Message | ChatMessageWithPlaceholdersDict_Placeholder]
    ]


class FrozenLangfuse(Langfuse):
    PROMPTS_BACKUP_PATH = _PROMPTS_BACKUP_PATH

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._prompts_backup: dict = {}
        try:
            with gzip.open(self.PROMPTS_BACKUP_PATH, "rt") as f:
                prompts_backup = json.load(f)
            self._prompts_backup = self._normalize_backup(prompts_backup)
            logger.info("Loaded %d prompts from backup", len(self._prompts_backup))

        except FileNotFoundError as e:
            msg = (
                f"No prompts backup found at {self.PROMPTS_BACKUP_PATH}. "
                + "Run FrozenLangfuse.bootstrap() first or ensure the backup file exists "
                + "by removing 'LANGFUSE_DISABLE_IMPLICIT_BOOTSTRAP' from env vars."
            )

            raise RuntimeError(msg) from e

        except json.JSONDecodeError as e:
            raise RuntimeError(f"Prompts backup at {self.PROMPTS_BACKUP_PATH} contains invalid JSON: {e}") from e

        except Exception as e:
            raise RuntimeError(f"Failed to load prompts backup from {self.PROMPTS_BACKUP_PATH}: {e}") from e

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

    @classmethod
    def bootstrap(cls, overwrite: bool = False) -> None:
        if os.path.exists(cls.PROMPTS_BACKUP_PATH) and not overwrite:
            logger.info("Backup already present at %s, skipping", cls.PROMPTS_BACKUP_PATH)
            return

        public_key = os.environ.get("LANGFUSE_PUBLIC_KEY")
        secret_key = os.environ.get("LANGFUSE_SECRET_KEY")
        host = os.environ.get("LANGFUSE_HOST")

        assert public_key, "MISSING `LANGFUSE_PUBLIC_KEY` in env"
        assert secret_key, "MISSING `LANGFUSE_SECRET_KEY` in env"
        assert host, "MISSING `LANGFUSE_HOST` in env"

        for attempt in range(_MAX_RETRIES):
            try:
                prompts = cls._fetch_all_prompts(public_key, secret_key, host)
            except Exception as exc:
                logger.warning("Fetch attempt %d/%d failed: %s", attempt + 1, _MAX_RETRIES, exc)
                if attempt < _MAX_RETRIES - 1:
                    time.sleep(_RETRY_DELAY * (2**attempt))
            else:
                cls._write_backup(prompts)
                logger.info("Saved %d prompts to %s", len(prompts), cls.PROMPTS_BACKUP_PATH)
                return

        raise RuntimeError(f"Failed to fetch prompts from Langfuse after {_MAX_RETRIES} attempts")

    @classmethod
    def _fetch_all_prompts(cls, public_key: str, secret_key: str, host: str) -> dict:
        langfuse = Langfuse(public_key=public_key, secret_key=secret_key, host=host)
        prompts_backup: dict[str, _PromptEntry] = {}
        page = 1
        futures = []
        with ThreadPoolExecutor() as executor:
            while True:
                prompts_metadata = cls._load_prompt_metadata_response_page(langfuse, page)
                if not prompts_metadata:
                    break
                for prompt_meta in prompts_metadata:
                    for label in prompt_meta.labels:
                        futures.append(executor.submit(cls._fetch_prompt, langfuse, prompt_meta, label))
                page += 1
            for future in as_completed(futures):
                prompt_meta, label, prompt = future.result()
                prompt_data = prompts_backup.setdefault(
                    prompt_meta.name,
                    {"type": prompt_meta.type, "labels": {}},
                )
                prompt_data["labels"][label] = prompt.prompt

        return prompts_backup

    @staticmethod
    def _load_prompt_metadata_response_page(langfuse: Langfuse, page: int) -> list[PromptMeta]:
        return langfuse.api.prompts.list(page=page).data

    @staticmethod
    def _fetch_prompt(
        langfuse: Langfuse, prompt_meta: PromptMeta, label: str
    ) -> tuple[PromptMeta, str, PromptClient | TextPromptClient | ChatPromptClient]:
        return prompt_meta, label, langfuse.get_prompt(name=prompt_meta.name, label=label, type=prompt_meta.type.name)

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
    def _write_backup(cls, prompts: dict) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(cls.PROMPTS_BACKUP_PATH)), exist_ok=True)
        with gzip.open(cls.PROMPTS_BACKUP_PATH, "wt") as f:
            json.dump(prompts, f, indent=2)
