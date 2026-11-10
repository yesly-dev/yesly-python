# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

The official Python SDK, `yesly` on PyPI. Typed (`mypy --strict`), managed with uv, built with hatch. Usage is in `README.md`.

## Commands

```bash
uv run --group dev pytest
uv run --group dev pytest tests/<file>.py -k "<name>"   # one test
uv run --group dev mypy
node ../yesly-openapi/sdk/generate.mjs python .         # regenerate src/yesly/_generated/
YESLY_API_KEY=ysk_test_… uv run python scripts/smoke.py  # smoke test against the real API
```

Smoke tests run against staging with a `ysk_test_` key and `YESLY_BASE_URL=https://api.dev.yesly.dev/v1`; they create and clean up one object per resource.

## How it is built

The API-shaped part is generated from `yesly-openapi/openapi.yaml` by `yesly-openapi/sdk/generate.mjs` (`node ../yesly-openapi/sdk/generate.mjs python .`): `src/yesly/_generated/`. Never edit it by hand: change the spec in `yesly-openapi`, lint it, and regenerate with both repos checked out side by side. Everything else is hand-written: `_client.py`, `_base.py`, `_errors.py`, `_pagination.py`, `webhooks.py`, `types.py`, `_version.py`. The hand-written client sends `Authorization: Bearer <key>` and `Yesly-Version`, retries with backoff honouring `Retry-After`, adds an automatic `Idempotency-Key` to writes, pages with `starting_after`, and verifies webhook signatures. The procedure for an API change across all SDKs is `yesly-openapi/docs/sdks.md`; package names must match `yesly-web/src/lib/sdks.ts`.

## Releasing

Bump `src/yesly/_version.py`, then push a tag `v<version>`.
