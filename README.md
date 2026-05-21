# langfuse-freeze

Wraps the Langfuse client to snapshot prompts to disk at startup. If Langfuse is unreachable at runtime, the local backup is used as fallback.

## How it works

On `import langfuse_freeze`, `FrozenLangfuse.bootstrap()` runs automatically:
- Backup file already exists → skip (log and continue)
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

client = FrozenLangfuse()
prompt = client.get_prompt("my-prompt", type="text", label="production")
```

Drop-in replacement for `Langfuse`. Same API.

## Bootstrap at container build time

Run before the app starts (e.g. in a Dockerfile or k8s init container):

```bash
langfuse-freeze-bootstrap
```

Same logic as import-time bootstrap — skips if backup already present.

## Configuration

| Env var | Default                             | Description |
|---|-------------------------------------|---|
| `LANGFUSE_PUBLIC_KEY` | —                                   | Required |
| `LANGFUSE_SECRET_KEY` | —                                   | Required |
| `LANGFUSE_HOST` | —                                   | Required |
| `LANGFUSE_PROMPTS_BACKUP_PATH` | `./langfuse-backup/prompts.json.gz` | Backup file location |
| `LANGFUSE_BOOTSTRAP_MAX_RETRIES` | `3`                                 | Fetch attempts before crash |
| `LANGFUSE_BOOTSTRAP_RETRY_DELAY` | `2`                                 | Base seconds for exponential backoff |
| `LANGFUSE_DISABLE_IMPLICIT_BOOTSTRAP` | —                                   | Set to `1` to skip import-time bootstrap |

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
