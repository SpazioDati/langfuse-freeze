# langfuse-freeze

Wraps the Langfuse client to snapshot prompts to disk at startup. If Langfuse is unreachable at runtime,
the local backup is used as fallback.

## How it works

`FrozenLangfuse(prompts_backup_path=<path>).bootstrap()` creates a Langfuse client (init parameters are equivalent to
the client in official SDK) and runs the backup process:
- Backup file already exists → skip if `overwrite` argument is false (log and continue)
- Backup file missing → fetch all prompts from Langfuse, write to disk
- Fetch fails → retry with exponential backoff, raise `RuntimeError` after max retries

At runtime, `FrozenLangfuse.get_prompt()` injects the backup as `fallback` so Langfuse SDK handles outages gracefully.

## Installation

```bash
uv add langfuse-freeze
```

## Usage

```python
from langfuse_freeze import FrozenLangfuse

client = FrozenLangfuse(prompts_backup_path='./langfuse_backup/prompts.json.gz')
client.bootstrap()
prompt = client.get_prompt("my-prompt", type="text", label="production")
```

Drop-in replacement for `Langfuse`. Same API.

## Bootstrap at container build time

Run before the app starts (e.g. in a Dockerfile or k8s init container):

```bash
langfuse-freeze-bootstrap ./langfuse_backup/prompts.json.gz
```

Same logic as import-time bootstrap — skips if backup already present.

## Backup format

```json
{
  "my-prompt": {
    "type": "text",
    "labels": {
      "production": "You are a helpful assistant.",
      "dev": "You are a dev assistant."
    }
  }
}
```

To refresh the backup, delete the file and restart (or re-run `langfuse-freeze-bootstrap`).

## Running tests

Unit tests (no network):

```bash
uv run pytest tests/ -m "not integration"
```

Integration tests requires Langfuse running on `http://localhost:3000`, we reccomend to [use docker-compose](https://langfuse.com/self-hosting/deployment/docker-compose).
In order to setup the instance with docker compose, some environment variables are required, with the following values:

```
LANGFUSE_INIT_ORG_ID=my-org
LANGFUSE_INIT_PROJECT_ID=my-project
LANGFUSE_INIT_PROJECT_PUBLIC_KEY=lf_pk_1234567890
LANGFUSE_INIT_PROJECT_SECRET_KEY=lf_sk_1234567890
LANGFUSE_INIT_USER_EMAIL=user@example.com
LANGFUSE_INIT_USER_PASSWORD=password123
```

They can be set in a `.env` file so the instance can be started with

```bash
docker compose --env-file .env up
```

Once Langfuse is running, integration tests can be run (they will write prompts on `my-project`)

```bash
uv run pytest tests/ -m integration
```
