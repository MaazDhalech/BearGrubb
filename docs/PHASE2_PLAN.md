# BearGrub AI Phase 2 Plan

Phase 2 turns the local Phase 1 app into a deployable, repeatable, and observable service. The work should proceed in slices that each leave the repository shippable.

## Principles

- CI must protect every push before deployment work begins.
- Required CI checks must be deterministic, offline, and free of API cost.
- Live Berkeley/OpenAI checks should exist, but should run manually or on a schedule because upstream outages and API limits are not code regressions.
- The scraper, parser, classifier, and storage pipeline should be testable without Chainlit or a browser.
- The app should never replace a known-good menu with an empty scrape.
- User prompts, raw retrieved context, API keys, and `.env` values should not be logged or sent to telemetry.

## Slice 1 - CI And Offline Prompt Eval

Deliverables:

- GitHub Actions workflow for every push and pull request.
- Dependency installation for `apps/beargrub-ai`.
- Python import/syntax check.
- Unit test gate with `pytest`.
- Offline prompt eval gate using local menu fixtures and deterministic answer paths.
- Generated-file guard for `.env`, `__pycache__`, `.pyc`, and local vector DB files.

Edge cases:

- CI must not need `OPENAI_API_KEY`.
- CI must not fetch Berkeley Dining.
- CI must not mutate tracked files.
- CI should fail loudly if generated artifacts are committed.

## Slice 2 - Refresh Job Boundary

Deliverables:

- A single command that performs scrape -> classify -> embed.
- Structured refresh summary: date, halls fetched, item count, classification counts, failures.
- Nonzero exit on total refresh failure.
- Keep-existing-data behavior when a live refresh returns zero items.
- Snapshot persistence remains part of Slice 3, after the refresh boundary is stable.

Edge cases:

- Partial hall outage.
- Malformed XML.
- Empty Berkeley response.
- Classifier fallback failure.
- Corrupted local cache.

## Slice 3 - Persistent Storage

Deliverables:

- Raw XML snapshot storage.
- Normalized menu JSON storage.
- Classification cache backup/restore.
- Local storage implementation for dev.
- S3 implementation for production.

Edge cases:

- S3 unavailable.
- Latest snapshot stale.
- Snapshot exists for only some halls.
- Cache schema changes.
- Date/timezone mismatch.

## Slice 4 - Deployment

Deliverables:

- Dockerfile.
- Runtime env documentation.
- Health check.
- AWS App Runner or equivalent deployment path.
- Deployment runbook.

Edge cases:

- Missing API key.
- Startup with no menu data.
- Upstream outage during startup.
- ChromaDB/local persistence permissions.
- Port configuration.

## Slice 5 - Observability And Abuse Controls

Deliverables:

- Structured logs for refresh, retrieval, classification, model calls, and user-visible failures.
- Sanitized PostHog events only.
- Basic rate limiting if deployed publicly.
- Prompt-injection regression tests.

Edge cases:

- Prompt asks for system prompt/API keys.
- Menu item contains prompt-like text.
- Rapid requests from one client.
- Long conversation history.
- Model or network timeout.

## Slice 6 - Live Eval

Deliverables:

- Manual or scheduled GitHub Actions job for live Berkeley scrape plus OpenAI prompt eval.
- Clear separation from required PR checks.
- Eval artifact summary uploaded for review.

Edge cases:

- Berkeley endpoint outage.
- OpenAI rate limit.
- Prompt drift.
- Current menu changes that invalidate stale expected item names.
