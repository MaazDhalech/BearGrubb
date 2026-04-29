# Phase 1 Part Reports

## Part 1 - Scraper

### What was built
- Added `config.py` with dining hall IDs, endpoint, local paths, model names, and environment loading.
- Added `scraper.py` with `fetch_all(date, hall='ALL')`, Berkeley dining menu URL construction, XML parsing, JSON-wrapped XML support, nutrient extraction, vegan/vegetarian dietary tag parsing, allergen parsing, and `calories_per_oz` precomputation.
- Added scraper tests covering field extraction, small serving sizes, all-hall fetch behavior, single-hall URL construction, and fetch-failure continuation.

### Deviations from the spec and why
- Added JSON-wrapped XML support in `parse_response_content()` because the specified endpoint is under `wp-json` even though the payload structure is XML. This keeps the parser compatible with either response envelope.
- Did not create `.env` with placeholder secrets. A real `.env` should be local-only; the code reads env vars and requirements will document expected names.

### Updated vulnerability log
- External dining menu fetches can fail or return malformed data. Mitigation: scraper logs errors and returns no items for that hall instead of crashing.
- The Berkeley endpoint is unauthenticated remote input. Mitigation: parser extracts only known XML fields into plain dictionaries and does not execute content.
- No secrets are written to disk by this part.

### Next part
- Build `classifier.py` with persisted cache, ingredient normalization, deterministic halal rules, shellfish handling, empty-ingredient handling, and GPT fallback plumbing.

## Part 2 - Classifier

### What was built
- Added `classifier.py` with `load_cache()`, `save_cache()`, `normalize()`, `get_cache_key()`, deterministic halal classification, shellfish detection, GPT fallback, result coercion, and `classify_all()`.
- Added an empty local `classification_cache.json` for persisted cache shape.
- Added classifier tests covering more than 10 specified cases: halal-labeled meat, unlabeled meat, alcohol, vanilla extract, shellfish, gelatin, halal gelatin, empty ingredients, natural flavors, single-ingredient produce, and ignoring halal labels outside ingredients.
- Added tests for normalized cache keys, cache persistence, GPT fallback plumbing, and `classify_all()` enrichment.

### Deviations from the spec and why
- Expanded deterministic classification beyond the spec's Step 3 so obviously safe vegetarian/produce items return `HALAL` without spending an OpenAI call. This is consistent with the edge case that salad bar single-ingredient items should be halal.
- Preserved semicolon-aware ingredient segment checks by splitting the original ingredient string first, then normalizing each segment. The spec says normalize before matching but also says to split normalized text on semicolons; stripping punctuation would remove semicolons, so this implementation keeps both requirements working.
- If OpenAI is unavailable for a GPT-review item, the classifier returns `UNCERTAIN` instead of crashing. This keeps the local app usable and matches the spec's uncertainty behavior.
- Kept `CLASSIFICATION_PROMPT` in `classifier.py` for this part; Part 5 will move prompt constants to `prompts.py`.

### Updated vulnerability log
- Ingredient strings are untrusted remote content. Mitigation: deterministic rules operate on normalized plain text and GPT calls send ingredients only as user content under a strict JSON-only system prompt.
- Cache poisoning risk exists if `classification_cache.json` is manually edited. Mitigation: cached and GPT results are coerced to known statuses and shellfish fields before use.
- OpenAI dependency/API absence can break classification. Mitigation: GPT-review cases degrade to `UNCERTAIN` when the client/package is unavailable.
- No API keys are hardcoded.

### Next part
- Build `rag.py` with structured filter extraction before retrieval, document/metadata construction, ChromaDB embedding when dependencies are installed, a local in-memory fallback for tests, and staleness detection.

## Part 3 - RAG Pipeline

### What was built
- Added `rag.py` with `extract_filters()`, `embed_menu()`, `retrieve()`, `is_stale()`, document construction, metadata construction, Chroma-compatible metadata cleaning, and a retrieval-compatible in-memory store for local tests.
- Implemented structured filter extraction before semantic retrieval for dining hall, halal, vegan, vegetarian, and meal period filters.
- Implemented the spec's human-readable menu item document format and structured metadata fields for filtering and nutrition lookups.
- Added RAG tests for combined filter extraction, breakfast-to-brunch mapping, document/metadata shape, filtered retrieval, all-dining-halls retrieval, and staleness detection.

### Deviations from the spec and why
- Added `InMemoryMenuStore` as a fallback when LangChain/ChromaDB packages are not installed. This keeps local unit tests deterministic and avoids requiring OpenAI embeddings for every test run while preserving the same `similarity_search()`/`get()` interface used by Chroma.
- Added `short_name` to metadata. The spec stores item name in the document text only, but adding it to metadata makes tests and downstream app responses easier to inspect without changing the filter contract.
- Omitted `None` nutrition values from Chroma metadata because Chroma only accepts primitive non-null metadata. The document text still carries the raw field values for model context.

### Updated vulnerability log
- Retrieval can return irrelevant results if semantic search runs without structured filters. Mitigation: `retrieve()` always calls `extract_filters()` before search and passes exact metadata filters to the store.
- Local test retrieval is lexical, not vector-based. Mitigation: production uses LangChain/Chroma when dependencies are available; the fallback is only an interface-compatible local path.
- Chroma metadata rejects null and complex values. Mitigation: metadata is cleaned to primitive non-null values before Chroma ingestion.
- Stale or empty stores can lead to outdated answers. Mitigation: `is_stale()` treats empty stores, old dates, and inspection failures as stale.

### Next part
- Build `mcp_tools.py` with the `get_menu` safety-net tool definition and a handler that fetches, classifies, and re-embeds menu data when the user explicitly asks to refresh.

## Part 4 - MCP Refresh Safety Net

### What was built
- Added `mcp_tools.py` with the `get_menu` MCP tool schema from the spec.
- Added `handle_tool_call()` for manual menu refreshes: validate tool arguments, fetch menu data, classify it, and re-embed the refreshed menu store.
- Added a no-data safety path that keeps the existing store if a manual refresh fetch returns no menu items.
- Added MCP tests for tool schema, successful refresh flow, fetch-empty fallback, unknown tool rejection, and argument validation.

### Deviations from the spec and why
- `handle_tool_call()` accepts an optional `cache` argument so the app can reuse the module-level classification cache instead of forcing a reload. Existing spec-style calls with `(name, args, db)` still work.
- If `fetch_all()` returns no items, the handler returns the existing `db` instead of embedding an empty store. This avoids wiping good local data after a transient Berkeley dining XML/API failure.
- Added explicit argument validation for dining hall and date format before fetching. The MCP schema describes the shape, but runtime validation makes direct calls safer.

### Updated vulnerability log
- Tool calls can arrive with malformed arguments. Mitigation: `handle_tool_call()` validates dining hall and ISO date before fetching.
- Manual refresh can be triggered when upstream dining data is temporarily unavailable. Mitigation: empty refresh results preserve the existing store.
- Refresh still depends on remote Berkeley menu data and OpenAI classification for ambiguous ingredients. Mitigation: scraper/classifier failure behaviors from earlier parts remain in effect.

### Next part
- Build `prompts.py` with `SYSTEM_PROMPT` and `CLASSIFICATION_PROMPT` constants, then update classifier imports to use the shared classification prompt.

## Part 5 - Prompt Constants

### What was built
- Added `prompts.py` with shared `SYSTEM_PROMPT` and `CLASSIFICATION_PROMPT` constants.
- Moved classifier GPT fallback to import `CLASSIFICATION_PROMPT` from `prompts.py`.
- Added prompt tests for date formatting, dining hall coverage, nutrition calculation rules, halal/dietary behavior, no-invention behavior, JSON-only classification output, shellfish handling, and classifier prompt reuse.

### Deviations from the spec and why
- Removed emoji symbols from the system prompt labels. The behavior is unchanged, and ASCII-only prompt text keeps the repo consistent with the editing constraints and avoids encoding friction in terminals/tests.
- The prompt constants are plain strings rather than helper functions. This keeps the implementation aligned with the spec and makes prompt tests straightforward.

### Updated vulnerability log
- Prompt drift can silently change model behavior. Mitigation: prompt tests assert the key nutrition, dietary, disclaimer, no-invention, JSON, and shellfish instructions remain present.
- Prompt injection risk remains for retrieved menu content because it is passed as context to the model. Mitigation for later app work: menu context will be supplied in a separate system message generated by trusted code, and user/page content will not be allowed to override system rules.
- Classification output is still model-generated for GPT fallback. Mitigation remains result coercion in `classifier.py`.

### Next part
- Build `app.py` with Chainlit startup, session state, deterministic staleness refresh, retrieval, history trimming, streaming response handling, MCP tool-call refresh support, and app-level tests with mocks.

## Part 6 - Chainlit App Flow

### What was built
- Added `app.py` with module-level `db` and `cache`, startup initialization, deterministic freshness checks, menu refresh, retrieval, context construction, message construction, history trimming, OpenAI streaming, Chainlit session handlers, and MCP refresh handling.
- Added a lightweight Chainlit fallback for unit tests and local imports when Chainlit is not installed.
- Added test seams for OpenAI client creation, menu refresh, retrieval, streaming, and tool handling.
- Added app tests for disabled test auto-init, chat start state reset, prompt message construction, history trimming, stale menu refresh, normal streaming responses, first halal disclaimer session state, fragmented tool-call parsing, and re-retrieval after a manual refresh tool call.

### Deviations from the spec and why
- Added `BEARGRUB_AUTO_INIT=0` support for tests. The default remains startup initialization, but tests can import `app.py` without making network/OpenAI calls.
- Added a Chainlit fallback object for tests because Chainlit is not installed in the current local environment. Real runtime still imports Chainlit when available.
- Added a second model call after an MCP refresh tool call so the assistant can answer from refreshed context instead of silently refreshing and returning no final content.
- Added deterministic first-halal-query disclaimer session tracking in app code. The prompt asks for first-session-only behavior; app state makes that reliable across turns.

### Updated vulnerability log
- Import-time startup can fail because Berkeley dining data, Chroma, or OpenAI dependencies are unavailable. Mitigation: startup exceptions are logged and the app falls back to an empty embedded store instead of crashing the process.
- Retrieved menu context is untrusted remote data. Mitigation: it is wrapped as generated menu context, while behavior rules remain in the system prompt and tests assert no-invention/dietary instructions stay present.
- Tool-call arguments are model-generated. Mitigation: app parses JSON and delegates validation to `mcp_tools.handle_tool_call()`.
- Streaming tool calls can be fragmented. Mitigation: `stream_completion()` accumulates names and JSON arguments by tool-call index before execution.
- Chat history can grow without bound. Mitigation: app trims history to the latest 10 messages before prompt construction and after saving each response.

### Next part
- Add PostHog session/event handling, `requirements.txt`, final Phase 1 verification tests, and run the full suite before the final Phase 1 commit.

## Part 7 - PostHog, Dependencies, And Final Phase 1 Metadata

### What was built
- Added PostHog configuration and event capture helpers in `app.py`.
- Added `session_started`, `message_received`, and `response_sent` events using `cl.user_session.get('id')` as the distinct ID.
- Added telemetry sanitization so raw user messages, prompts, responses, history, and retrieved context are not sent as analytics properties.
- Added `requirements.txt` for Phase 1 local runtime dependencies.
- Added `.env.example` with empty placeholders for OpenAI and PostHog keys plus `BEARGRUB_AUTO_INIT`.
- Added `VULNERABILITY_LOG.md` consolidating open Phase 1 risks and deferred Phase 2 hardening.
- Added tests for PostHog distinct ID usage, no-anonymous fallback, telemetry sanitization, session event capture, safe message/response metadata, requirements coverage, env placeholders, and vulnerability log coverage.

### Deviations from the spec and why
- Omitted `boto3` from Phase 1 `requirements.txt` even though it appears in the full spec dependency list. The user explicitly restricted this build to Phase 1 and asked not to touch AWS; boto3 should be introduced with the Phase 2 S3 work.
- Added `.env.example` instead of a real `.env`. This documents required keys without committing secrets.
- PostHog message events intentionally exclude raw query/response text. This is a privacy-preserving telemetry choice and reduces accidental leakage of sensitive user messages.

### Updated vulnerability log
- Analytics can leak sensitive user content if raw fields are sent. Mitigation: `sanitize_event_properties()` strips text-bearing keys and tests enforce safe event payloads.
- Missing Chainlit session IDs would make PostHog attribution ambiguous. Mitigation: events are skipped rather than using `"anonymous"`, matching the spec's requirement to use the session ID.
- Local runtime dependencies are not installed in this workspace. Mitigation: dependencies are declared in `requirements.txt`, while tests continue to use mocks/fallbacks without network installs.
- No AWS/Docker work was performed in Phase 1.

### Next part
- Phase 1 implementation is complete. Next work should be final manual runtime validation with installed dependencies, followed by Phase 2 only when Docker/AWS work is explicitly allowed.
