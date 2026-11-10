# Strido assistant

The documentation assistant behind the site's AI bar: a chat API with conversation history and
attachments (`/api/assistant/*`, Server-Sent Events), an MCP endpoint for agents (`/mcp`) and the
agent files (`/api/agent/*`). It answers from the synced `docs-site/content` tree (English and
German pages, BOM data), indexed with SQLite FTS5, and calls the model through Cortex Keyring.
Node 26, no dependencies (`node:http`, `node:sqlite`, `node:crypto`, `fetch`).

## Environment

| Variable | Default | Purpose |
|---|---|---|
| `KNOWLEDGE_DIR` | required | The synced `docs-site/content` tree (after `npm run sync`); its `public/` holds the BOM data and agent files |
| `ASSISTANT_DATA_DIR` | `./data` | Where `assistant.db` (conversations, messages, attachments) lives |
| `ASSISTANT_QUOTA_BYTES` | `209715200` (200 MiB) | Per-user total of stored attachment bytes; a message that would exceed it gets 413 `quota_exceeded` |
| `SITE_URL` | `https://strido.cortex.a2olabs.com` | Base of the absolute links MCP tools return |
| `PORT` / `HOST` | `8090` / `0.0.0.0` | Listen address |
| `ASSISTANT_MODEL` | `claude-sonnet-5` | Exact model id |
| `ASSISTANT_AUTH_MODE` | `cortex` | `cortex` or `dev` (fixed user `dev@localhost`, no checks; needs `ASSISTANT_DEV=1`) |
| `CORTEX_APP_HEADER_SECRET` | required in `cortex` mode | Gateway secret; `X-Cortex-Email`/`X-Cortex-User` are trusted only with a matching `X-Cortex-Auth-Secret` |
| `CORTEX_APP_DIRECTORY_URL` | unset | Control's app-directory base, e.g. `https://dashboard.example/api/v1/app-directory`; `cxu_` app tokens are checked at `…/tokens/verify` (a bare Control origin gets `/api/v1/app-directory` appended). Injected by Control when the manifest declares app-directory access |
| `CORTEX_APP_KEY_FILE` | unset | The app key file Control mounts (`/run/cortex/app-directory/key`); re-read after a 401 (key rotation). Both or neither with the URL; unset, app tokens get 401 |
| `CORTEX_MODEL_BASE_URL` (or `ANTHROPIC_BASE_URL`) | unset | Keyring's Anthropic Messages API base |
| `CORTEX_MODEL_SUBSCRIBER` / `CORTEX_MODEL_SUBSCRIBER_KEY` | unset | The subscriber's email and Keyring key; the key serves only that user |
| `CORTEX_MODEL_KEY` | unset | Shared key for everyone else. Without a subscriber, `CORTEX_MODEL_KEY` → `ANTHROPIC_API_KEY` → `ANTHROPIC_AUTH_TOKEN` serves everyone |

The machine lane (`Authorization: Bearer cxu_…`, from `cortex apps connect strido`) reaches `/mcp`
and `/api/agent/*` only. Token checks, current or refused, are cached for at most a minute.

## API notes

- `POST /api/assistant/conversations/:id/messages` (`:id` may be `new`) streams the answer as SSE
  (`conversation`, `user`, `status`, `delta`, `done` or `error`).
- `POST /api/assistant/conversations/:id/regenerate` `{locale, page?}` deletes the answers after the
  last user message and answers it again: the same stream without `user`; 404 without a user message.
- Per user: one answer at a time (409 `busy`), 20 messages or regenerations per 10 minutes (429), 200
  conversations (409), attachment quota (413 `quota_exceeded`). Images up to 3.75 MiB (the model's
  5 MB limit applies to base64), text files up to 200 KiB, 6 per message.
- Body limits: the messages route takes the six largest base64 images plus the prompt and 64 KiB;
  every other JSON route (including `/mcp`) 64 KiB.
- The database uses incremental auto-vacuum; deleting a conversation returns its pages to the disk.

## Run locally

```sh
cd assistant
set -a; . ~/.config/cortex/keyring.prod.env; set +a   # ANTHROPIC_BASE_URL + ANTHROPIC_AUTH_TOKEN
ASSISTANT_AUTH_MODE=dev ASSISTANT_DEV=1 KNOWLEDGE_DIR=../docs-site/content ASSISTANT_DATA_DIR=/tmp/yx-assistant \
  node src/server.mjs
curl localhost:8090/api/health
```

Tests (hermetic, fake model transport): `npm test`.
