# BearGrub AI Deployment Runbook

This runbook covers the Phase 2 container path. It does not require committing secrets.

## Runtime Requirements

- Python 3.13 container runtime.
- `OPENAI_API_KEY` set in the runtime environment.
- Optional `POSTHOG_API_KEY` for sanitized telemetry.
- Outbound HTTPS access to Berkeley Dining and OpenAI.
- Writable local filesystem for `chroma_db/` and `menu_data/`.

## Local Container Smoke Test

Build from the BearGrub AI app directory:

```bash
cd apps/beargrub-ai
docker build -t beargrub-ai:local .
```

Run with your local env file:

```bash
docker run --rm -p 8000:8000 --env-file .env beargrub-ai:local
```

Then open `http://127.0.0.1:8000`.

## Pre-Deploy Gates

Run these before publishing an image:

```bash
cd apps/beargrub-ai
.venv/bin/python -m compileall -q app.py classifier.py config.py mcp_tools.py menu_answers.py prompts.py rag.py refresh.py scraper.py storage.py tests
.venv/bin/python -m pytest tests/ -v
.venv/bin/python tests/offline_prompt_eval.py
```

The live eval remains separate because it requires network access and `OPENAI_API_KEY`:

```bash
cd apps/beargrub-ai
.venv/bin/python tests/eval_pipeline.py
```

## Health Check

The Docker image defines a health check against the Chainlit HTTP root. A healthy container means the web server is responsive. It does not prove Berkeley Dining or OpenAI are reachable; use the refresh command for that:

```bash
python refresh.py --date "$(date +%F)" --hall ALL --json
```

## App Runner Shape

Use an image-based service:

- Port: `8000`, or set `PORT` if the platform injects a port.
- Environment variables: `OPENAI_API_KEY`, optional `POSTHOG_API_KEY`, optional `BEARGRUB_AUTO_INIT=1`.
- Health path: `/`.
- Instance storage: ephemeral is acceptable for Phase 2 because refresh can rebuild `chroma_db/` and `menu_data/`; persistent object storage is still a later production hardening step.

## Failure Policy

- Startup refresh failure should not expose secrets and should degrade to an empty menu store if no prior store exists.
- Runtime refresh failure should keep the existing in-memory store.
- Snapshot write failure should be logged in the refresh summary but should not discard a successfully embedded store.
- Do not deploy with `DEBUG = True` for a public production service; it prints query diagnostics to stdout.
