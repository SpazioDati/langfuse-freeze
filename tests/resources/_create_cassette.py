from __future__ import annotations

import json
import sys

from langfuse import Langfuse


def dump_cassette(output_path: str, public_key: str, secret_key: str, host: str):
    langfuse = Langfuse(public_key=public_key, secret_key=secret_key, host=host)
    cassette = {"pages": [], "prompts": {}}
    page = 1

    while True:
        response = langfuse.api.prompts.list(page=page)
        if not response.data:
            break

        page_data = []
        for prompt_meta in response.data:
            meta_dict = {
                "name": prompt_meta.name,
                "type": prompt_meta.type.value,
                "versions": prompt_meta.versions,
                "labels": prompt_meta.labels,
                "tags": prompt_meta.tags,
                "last_updated_at": prompt_meta.last_updated_at.isoformat(),
                "last_config": prompt_meta.last_config,
            }
            page_data.append(meta_dict)

            if prompt_meta.name not in cassette["prompts"]:
                cassette["prompts"][prompt_meta.name] = {}

            for label in prompt_meta.labels:
                prompt_client = langfuse.get_prompt(
                    name=prompt_meta.name,
                    label=label,
                    type=prompt_meta.type.value,
                )
                cassette["prompts"][prompt_meta.name][label] = {
                    "type": prompt_meta.type.value,
                    "prompt": prompt_client.prompt,
                    "version": prompt_client.version,
                    "config": prompt_client.config,
                    "labels": prompt_client.labels,
                    "tags": prompt_client.tags,
                }

        cassette["pages"].append(page_data)
        page += 1

    with open(output_path, "w") as f:
        json.dump(cassette, f, indent=2, ensure_ascii=False)

    print(f"Dumped {len(cassette['pages'])} pages, {len(cassette['prompts'])} prompts to {output_path}")


if __name__ == "__main__":
    import os

    dump_cassette(
        output_path=sys.argv[1] if len(sys.argv) > 1 else "prompts_cassette.json",
        public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
        secret_key=os.environ["LANGFUSE_SECRET_KEY"],
        host=os.environ["LANGFUSE_HOST"],
    )
